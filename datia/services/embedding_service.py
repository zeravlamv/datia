from typing import List, Dict, Optional
from datia.models import MetricsEmbeddings
from django.db import connections
from django.utils import timezone
from django.conf import settings
import json
import numpy as np
import os
import requests
import hashlib

# Lazy placeholder
SentenceTransformer = None

class EmbeddingService:
    """
    Manages vector generation (Local SentenceTransformers) and retrieval for RAG.
    Strictly for Postgres 'metrics_*' tables.
    """
    _model = None
    _warned_missing_st = False

    # --- SQL TEMPLATES REGISTRY ---
    # These act as the "Documents" we search against.
    # The 'text' is the natural language intent.
    # The 'sql' is the template.
    SQL_TEMPLATES = [
        {
            "key": "sales_report",
            "text": "informe ventas ventas anuales reporte comercial resumen general balance situacion",
            "sql": "SELECT 'REPORT' as mode",
            "type": "report",
            "label": "Informe Comercial"
        },
        {
            "key": "sales_map",
            "key": "sales_map",
            "text": "mapa ventas por zona geografia provincias comunidades donde vendemos mas mapa geografico",
            "sql": "SELECT cod_postal, importe_neto_total FROM metrics_totales_empresa_ejercicio_codigo_postal WHERE empresa = {empresa} AND ejercicio = {ejercicio}",
            "type": "chart",
            "chart_type": "bar",
            "label": "Mapa de Ventas"
        },
        {
            "key": "top_clients",
            "text": "mejores clientes top clientes ranking facturacion quienes compran mas clientela",
            "sql": "SELECT nombre as label, SUM(importe_neto_total) as val, SUM(importe_coste_total) as coste FROM metrics_totales_empresa_ejercicio_cliente WHERE empresa = {empresa} AND ejercicio = {ejercicio} GROUP BY nombre, cliente ORDER BY val DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Top Clientes"
        },
        {
            "key": "top_articles",
            "text": "mejores articulos productos mas vendidos top ranking ventas producto estrella",
            "sql": "SELECT descripcion as label, SUM(importe_neto_total) as val, SUM(importe_coste_total) as coste FROM metrics_totales_empresa_ejercicio_articulo WHERE empresa = {empresa} AND ejercicio = {ejercicio} GROUP BY descripcion, articulo ORDER BY val DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Top Artículos"
        },
        {
            "key": "sales_summary",
            "text": "resumen comercial ventas totales margen beneficio rentabilidad estado general",
            "sql": "SELECT SUM(importe_neto_total) as neto, SUM(importe_coste_total) as coste, SUM(albaranes_count) as ops FROM metrics_totales_empresa_ejercicio WHERE empresa = {empresa} AND ejercicio = {ejercicio}",
            "type": "card",
            "label": "Resumen"
        },
        {
            "key": "sales_evolution_monthly",
            "text": "evolucion ventas mensual pedidos mensuales meses año anual comparativa trayectoria 2024 2025 2023 ejercicio",
            "sql": "SELECT mes as label, SUM(importe_neto_total) as val, SUM(importe_coste_total) as coste FROM metrics_totales_empresa_ejercicio_mes WHERE empresa = {empresa} AND ejercicio = {ejercicio} GROUP BY mes ORDER BY mes",
            "type": "chart",
            "chart_type": "line",
            "label": "Evolución Mensual"
        },
        {
            "key": "orders_top_clients",
            "text": "top clientes pedidos ranking pedidos quienes compran mas pedidos clientes",
            "sql": "SELECT H.\"NombreCliente\" AS label, SUM(L.\"ImporteNeto\") AS val FROM \"DatiaDB_LineasPedidoCliente\" L JOIN \"DatiaDB_CabeceraPedidoCliente\" H ON L.\"NumeroPedido\" = H.\"NumeroPedido\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} GROUP BY H.\"NombreCliente\" ORDER BY val DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Top Clientes por Pedidos"
        },
        {
            "key": "orders_top_products",
            "text": "top productos pedidos ranking articulos mas vendidos pedidos productos",
            "sql": "SELECT L.\"DescripcionArticulo\" AS label, SUM(L.\"ImporteNeto\") AS val FROM \"DatiaDB_LineasPedidoCliente\" L JOIN \"DatiaDB_CabeceraPedidoCliente\" H ON L.\"NumeroPedido\" = H.\"NumeroPedido\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} GROUP BY L.\"DescripcionArticulo\" ORDER BY val DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Top Productos por Pedidos"
        },
        {
            "key": "orders_margin_clients_q4",
            "text": "margen por cliente del último trimestre margen clientes pedidos Q4",
            "sql": "SELECT H.\"NombreCliente\" AS label, SUM(L.\"ImporteNeto\" - L.\"ImporteCoste\") AS margen FROM \"DatiaDB_LineasPedidoCliente\" L JOIN \"DatiaDB_CabeceraPedidoCliente\" H ON L.\"NumeroPedido\" = H.\"NumeroPedido\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} AND EXTRACT(QUARTER FROM H.\"FechaPedido\") = 4 GROUP BY H.\"NombreCliente\" ORDER BY margen DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Margen por Cliente (Q4)"
        },
        {
            "key": "orders_monthly_evolution",
            "text": "evolucion pedidos mensual tendencia pedidos meses ejercicio clientes",
            "sql": "SELECT DATE_TRUNC('month', H.\"FechaPedido\") AS label, SUM(L.\"ImporteNeto\") AS val FROM \"DatiaDB_LineasPedidoCliente\" L JOIN \"DatiaDB_CabeceraPedidoCliente\" H ON L.\"NumeroPedido\" = H.\"NumeroPedido\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} GROUP BY DATE_TRUNC('month', H.\"FechaPedido\") ORDER BY label",
            "type": "chart",
            "chart_type": "line",
            "label": "Evolución Mensual Pedidos"
        },
        {
            "key": "delivery_top_clients",
            "text": "top clientes albaranes ranking quienes reciben mas albaranes clientes",
            "sql": "SELECT H.\"NombreCliente\" AS label, SUM(L.\"ImporteNeto\") AS val FROM \"DatiaDB_LineasAlbaranCliente\" L JOIN \"DatiaDB_CabeceraAlbaranCliente\" H ON L.\"NumeroAlbaran\" = H.\"NumeroAlbaran\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} GROUP BY H.\"NombreCliente\" ORDER BY val DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Top Clientes por Albaranes"
        },
        {
            "key": "delivery_monthly_evolution",
            "text": "evolucion albaranes mensual tendencia albaranes meses ejercicio",
            "sql": "SELECT DATE_TRUNC('month', H.\"FechaAlbaran\") AS label, SUM(L.\"ImporteNeto\") AS val FROM \"DatiaDB_LineasAlbaranCliente\" L JOIN \"DatiaDB_CabeceraAlbaranCliente\" H ON L.\"NumeroAlbaran\" = H.\"NumeroAlbaran\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} GROUP BY DATE_TRUNC('month', H.\"FechaAlbaran\") ORDER BY label",
            "type": "chart",
            "chart_type": "line",
            "label": "Evolución Mensual Albaranes"
        },
        {
            "key": "delivery_margin_clients_q4",
            "text": "margen por cliente del último trimestre margen clientes albaranes Q4",
            "sql": "SELECT H.\"NombreCliente\" AS label, SUM(L.\"ImporteNeto\" - L.\"ImporteCoste\") AS margen FROM \"DatiaDB_LineasAlbaranCliente\" L JOIN \"DatiaDB_CabeceraAlbaranCliente\" H ON L.\"NumeroAlbaran\" = H.\"NumeroAlbaran\" AND L.\"Ejercicio\" = H.\"Ejercicio\" WHERE H.\"CodigoEmpresa\" = {empresa} AND H.\"Ejercicio\" = {ejercicio} AND EXTRACT(QUARTER FROM H.\"FechaAlbaran\") = 4 GROUP BY H.\"NombreCliente\" ORDER BY margen DESC LIMIT {limit}",
            "type": "table",
            "chart_type": "bar",
            "label": "Margen por Cliente (Q4, Albaranes)"
        }
    ]

    def __init__(self):
        # Lazy load model only when needed
        pass


    def _get_model(self):
        if self._model:
            return self._model
            
        global SentenceTransformer
        if SentenceTransformer is None:
             try:
                 from sentence_transformers import SentenceTransformer as ST
                 SentenceTransformer = ST
             except ImportError:
                 if not EmbeddingService._warned_missing_st:
                     EmbeddingService._warned_missing_st = True
                 SentenceTransformer = None
        
        if SentenceTransformer:
            try:
                self._model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            except Exception as e:
                self._model = None

        return self._model

    def _provider(self) -> str:
        configured = None
        try:
            from django.conf import settings
            configured = getattr(settings, 'DATIA_EMBED_PROVIDER', None)
        except Exception:
            configured = None
        provider = os.environ.get('DATIA_EMBED_PROVIDER') or configured or 'ollama'
        return str(provider).lower()

    def _embed_model_name(self) -> str:
        configured = None
        try:
            from django.conf import settings
            configured = getattr(settings, 'OLLAMA_EMBED_MODEL', None)
        except Exception:
            configured = None
        return os.environ.get('OLLAMA_EMBED_MODEL') or configured or 'nomic-embed-text'

    def embed_text(self, text: str) -> List[float]:
        provider = self._provider()
        if provider == 'sentence':
            model = self._get_model()
            if model:
                v = model.encode(text, convert_to_numpy=True)
                return v.tolist()
            return self._hash_embed(text)
        if provider == 'ollama':
            v = self._embed_with_ollama(text)
            if v:
                return v
            # La huella solo mantiene plantillas y esquemas ya guardados.
            # El índice de entidades llama a _embed_with_ollama y no acepta esta huella.
            return self._hash_embed(text)
        return self._hash_embed(text)

    def _embed_with_ollama(self, text: str) -> List[float]:
        """Vector nativo de Ollama. No recorta a 384 ni rellena con ceros. None si Ollama no responde."""
        try:
            base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            model = self._embed_model_name()
            res = requests.post(f"{base}/api/embeddings", json={"model": model, "prompt": text}, timeout=(3, 8))
            if res.status_code != 200:
                return None
            data = res.json()
            vec = data.get("embedding") or []
            if not isinstance(vec, list) or len(vec) == 0:
                return None
            return [float(x) for x in vec]
        except Exception:
            return None

    def _hash_embed(self, text: str) -> List[float]:
        b = hashlib.sha256((text or "").encode("utf-8")).digest()
        arr = list(b) * (384 // len(b)) + list(b)[:(384 % len(b))]
        v = np.array(arr, dtype=np.float32) / 255.0
        n = float(np.linalg.norm(v))
        if n == 0.0:
            return [0.0] * 384
        v = v / n
        return v.tolist()


    def index_templates(self):
        """
        Creates embeddings for the SQL Templates and stores them in Postgres 'metrics_embeddings'.
        """
        print("Indexing SQL Templates...")
        for tpl in self.SQL_TEMPLATES:
            # Upsert into Postgres (using 'analytics' db router or explicit connection if needed)
            self.add_embedding(
                text=tpl['text'],
                sql=tpl['sql'],
                metadata={
                    'sql': tpl['sql'],
                    'type': tpl['type'],
                    'chart_type': tpl.get('chart_type'),
                    'label': tpl['label']
                },
                kind='template',
                key=tpl['key']
            )
        print("Templates Indexed.")

    def add_embedding(self, text: str, sql: str, metadata: Dict = {}, kind: str = 'qa', key: Optional[str] = None):
        """
        Adds a single embedding entry to the database.
        Used by Auto-Training and Seed/Index processes.
        """
        vector = self.embed_text(text)
        if not vector:
            return

        # Ensure key exists or generate one
        if not key:
            key = f"auto_{abs(hash(text))}_{int(timezone.now().timestamp())}"
            
        # Ensure metadata contains the SQL if not explicitly set
        if 'sql' not in metadata:
            metadata['sql'] = sql
            
        MetricsEmbeddings.objects.update_or_create(
            kind=kind,
            key=key,
            defaults={
                'text': text,
                'metadata': json.dumps(metadata) if isinstance(metadata, dict) else metadata,
                'vector': vector,
                'updated_at': timezone.now()
            }
        )

    def _meta_dict(self, item) -> Dict:
        meta = item.metadata
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                return {}
        return meta if isinstance(meta, dict) else {}

    def _sql_is_readable(self, sql: str) -> bool:
        import re
        text = (sql or '').strip().lower()
        if not (text.startswith('select') or text.startswith('with')):
            return False
        if re.search(r'\b(drop|delete|insert|update|alter|truncate|grant|execute)\b', text):
            return False
        return True

    def _belongs_to_empresa(self, meta: Dict, empresa) -> bool:
        if empresa is None or empresa == '':
            return True
        try:
            empresa_id = int(empresa)
        except Exception:
            return True
        raw = meta.get('empresa_id')
        if raw is None or raw == '':
            source_name = (meta.get('source_table') or '').strip()
            if not source_name:
                return True
            from datia.models.semantic import DataSource
            return DataSource.objects.filter(name=source_name).exists()
        try:
            return int(raw) == empresa_id
        except Exception:
            return False

    def uses_semantic_vectors(self) -> bool:
        """La huella por hash no distingue frases. Sin modelo semántico no hay búsqueda."""
        cached = getattr(self, '_semantic_ready', None)
        if cached is not None:
            return cached
        provider = self._provider()
        ready = False
        if provider == 'sentence':
            ready = self._get_model() is not None
        elif provider == 'ollama':
            ready = bool(self._embed_with_ollama('datia'))
        self._semantic_ready = ready
        return ready

    def search_template(self, query: str, threshold: float = 0.35, empresa=None, scopes: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Finds the best matching SQL Template for a user query.
        Respects RLHF Feedback (MetricsFeedback) and the company scope.
        """
        from datia.models import MetricsFeedback

        if not self.uses_semantic_vectors():
            return None

        query_vec = self.embed_text(query)
        if not query_vec:
            return None
        
        feedbacks = MetricsFeedback.objects.filter(query=query)
        rejected_keys = list(feedbacks.filter(is_positive=False).values_list('rejected_key', flat=True))
        boosted_keys = list(feedbacks.filter(is_positive=True).values_list('rejected_key', flat=True))
        
        candidates = MetricsEmbeddings.objects.filter(kind__in=['template', 'qa']).exclude(key__in=rejected_keys)
        allowed_scopes = None if not scopes else {str(s).lower() for s in scopes}
        
        filtered = []
        for item in candidates:
            try:
                meta = self._meta_dict(item)
                sql_meta = meta.get('sql') or meta.get('sql_template') or ''
                scope_meta = (meta.get('scope') or '').lower()
                if allowed_scopes is not None and scope_meta not in allowed_scopes:
                    continue
                if not self._sql_is_readable(sql_meta):
                    continue
                if not self._belongs_to_empresa(meta, empresa):
                    continue
                filtered.append(item)
            except Exception:
                continue
        
        best_score = -1
        best_match = None
        
        for item in filtered:
            # Cosine Similarity: (A . B) / (||A|| * ||B||)
            stored_vec = np.array(item.vector, dtype=np.float64)
            q_vec = np.array(query_vec, dtype=np.float64)
            if stored_vec.shape != q_vec.shape:
                continue
            
            norm_stored = np.linalg.norm(stored_vec)
            norm_q = np.linalg.norm(q_vec)
            
            if norm_stored == 0 or norm_q == 0:
                score = 0
            else:
                score = np.dot(stored_vec, q_vec) / (norm_stored * norm_q)
            
            # [FIX] Ensure score is a scalar float, not a numpy array
            if isinstance(score, (np.ndarray, np.generic)):
                if score.size == 1:
                    score = float(score.item())
                else:
                    # Handle unexpected shape (e.g. if vector was 2D)
                    score = float(score.flatten()[0])

            # [NF-039] Apply RLHF Boost
            if item.key in boosted_keys:
                score += 0.25 # Significant boost for verified answers
                print(f"DEBUG: Boosting score for {item.key} due to positive feedback.")

            if score > best_score:
                best_score = score
                best_match = item
        
        print(f"Best match (Filtered): {best_match.key if best_match else 'None'} (Score: {best_score:.4f})")

        
        if best_match and best_score >= threshold:
            meta = best_match.metadata if isinstance(best_match.metadata, dict) else json.loads(best_match.metadata)
            return {
                "key": best_match.key,
                "sql": meta.get('sql') or meta.get('sql_template'),
                "type": meta.get('type'),
                "chart_type": meta.get('chart_type'),
                "label": meta.get('label'),
                "score": best_score
            }
        
        return None

    def find_similar_examples(self, query: str, k: int = 3, threshold: float = 0.25) -> List[Dict]:
        """
        Retrieves the top-k most similar SQL examples (Few-Shot) to guide the LLM.
        """
        query_vec = self.embed_text(query)
        if not query_vec:
            return []
        candidates = MetricsEmbeddings.objects.filter(kind='qa')
        
        results = []
        for item in candidates:
            # Cosine Similarity
            stored_vec = np.array(item.vector, dtype=np.float64)
            q_vec = np.array(query_vec, dtype=np.float64)
            if stored_vec.shape != q_vec.shape:
                continue
            
            norm_stored = np.linalg.norm(stored_vec)
            norm_q = np.linalg.norm(q_vec)
            
            if norm_stored == 0 or norm_q == 0:
                score = 0
            else:
                score = np.dot(stored_vec, q_vec) / (norm_stored * norm_q)
            
            # [FIX] Ensure score is a scalar float, not a numpy array
            if isinstance(score, np.ndarray):
                score = float(score.item())

            if score >= threshold:
                meta = self._meta_dict(item)
                results.append({
                    'text': item.text,
                    'sql': meta.get('sql') or meta.get('sql_template') or '',
                    'score': score
                })
        
        # Sort and Top-K
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:k]


    def learn_template(self, text: str, sql: str, type: str = 'card', label: str = 'Resultado', chart_type: Optional[str] = None, empresa=None, ejercicio=None, scope: str = 'learned'):
        """
        Guarda una consulta enseñada. La clave es estable entre reinicios
        y queda ligada a la empresa.
        """
        vector = self.embed_text(text)
        empresa_part = '' if empresa is None else str(empresa)
        digest = hashlib.sha256(f"{empresa_part}:{text.strip().lower()}".encode('utf-8')).hexdigest()[:24]
        key = f"learned_{digest}"
        metadata = {
            'sql': sql,
            'sql_template': sql,
            'type': type,
            'chart_type': chart_type,
            'label': label,
            'scope': scope or 'learned',
        }
        if empresa is not None and empresa != '':
            try:
                metadata['empresa_id'] = int(empresa)
            except Exception:
                metadata['empresa_id'] = empresa
        if ejercicio is not None and ejercicio != '':
            try:
                metadata['ejercicio'] = int(ejercicio)
            except Exception:
                metadata['ejercicio'] = ejercicio

        MetricsEmbeddings.objects.update_or_create(
            kind='template',
            key=key,
            defaults={
                'text': text,
                'metadata': metadata,
                'vector': vector,
                'updated_at': timezone.now()
            }
        )
    def index_schema(self, table_name: Optional[str] = None):
        """
        Indexes the database schema (DataFields) into the Vector DB.
        If table_name is provided, only re-indexes that table.
        """
        from datia.models.semantic import DataSource, DataField
        
        print(f"Indexing Schema (Table: {table_name or 'ALL'})...")
        
        # 1. Fetch DataSources
        query = DataSource.objects.filter(is_active=True)
        if table_name:
            query = query.filter(source_table=table_name)
            
        sources = list(query)
        
        for source in sources:
            # 2. Build Text Representation
            # We point the AI to the LOCAL Postgres table, which is 'datia_' + sanitized source_name
            # UPDATE: Now using 'DatiaDB_' prefix via model method
            local_table = source.get_local_table_name()
            
            active_fields = DataField.objects.filter(source=source, is_active=True)
            
            field_texts = []
            field_names = []
            
            for f in active_fields:
                role = "Dimension" if f.usage_type == 'dimension' else "Model Metric"
                field_desc = f"{f.business_name} ({f.field_name}) [{role}]"
                if f.description:
                    field_desc += f": {f.description}"
                field_texts.append(field_desc)
                field_names.append(f.field_name) # Keep original name for consistency or use business name if we renamed columns? 
                # In AutoTrainingService we currently create columns as sanitized business_names? 
                # Let's check AutoTrainingService again. 
                # Yes: col_name = f.business_name.lower().replace(' ', '_')
                # So we must tell the AI the COLUMN NAMES are these sanitized business names.
            
            # Correction: The actual PG columns are business_name based.
            # So we must index the PG column names.
            
            pg_field_texts = []
            pg_field_names = []
            for f in active_fields:
                pg_col = f.business_name.lower().replace(' ', '_')
                role = "Dimension" if f.usage_type == 'dimension' else "Metric"
                
                # Description: "Client ID (sql: client_id) [Dimension]: Unique identifier..."
                desc = f"{f.business_name} (SQL: {pg_col}) [{role}]"
                if f.description:
                    desc += f" - {f.description}"
                
                pg_field_texts.append(desc)
                pg_field_names.append(pg_col)

            
            # Master Text for Embedding
            text_block = (
                f"Table: {source.name} (SQL Table: {local_table}).\n"
                f"Description: {source.description or 'Auto-trained business data'}\n"
                f"Columns:\n" + "\n".join([f"- {t}" for t in pg_field_texts])
            )
            
            # 3. Embed & Store
            vector = self.embed_text(text_block)
            
            MetricsEmbeddings.objects.update_or_create(
                kind='schema',
                key=source.source_table, # Keep original key to avoid dups/orphans easily
                defaults={
                    'text': text_block,
                    'metadata': json.dumps({
                        'table': local_table, # Metadata points to LOCAL table
                        'name': source.name,
                        'fields': pg_field_names
                    }),
                    'vector': vector,
                    'updated_at': timezone.now()
                }
            )
            print(f"Indexed schema for {source.source_table} -> {local_table}")
            
    def search_schema(self, query: str, threshold: float = 0.35, limit: int = 3) -> List[Dict]:
        """
        Finds relevant tables based on user question.
        """
        query_vec = self.embed_text(query)
        if not query_vec:
            return []
        candidates = MetricsEmbeddings.objects.filter(kind='schema')
        
        results = []
        for item in candidates:
            # Cosine Similarity
            stored_vec = np.array(item.vector, dtype=np.float64)
            q_vec = np.array(query_vec, dtype=np.float64)
            if stored_vec.shape != q_vec.shape:
                continue
            norm_stored = np.linalg.norm(stored_vec)
            norm_q = np.linalg.norm(q_vec)
            
            if norm_stored == 0 or norm_q == 0: score = 0
            else: 
                score = np.dot(stored_vec, q_vec) / (norm_stored * norm_q)
                if hasattr(score, 'item'):
                    score = float(score.item())
                else:
                    score = float(score)
            
            if score >= threshold:
                results.append({
                    'table': item.key,
                    'score': score,
                    'metadata': json.loads(item.metadata) if isinstance(item.metadata, str) else item.metadata,
                    'text': item.text
                })
                
        # Sort by score DESC
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]
    def index_internal_stats(self):
        """
        Indexes the internal aggregation tables (metrics_totales_*) as "Summary Tables".
        This teaches the AI about the available pre-calculated statistics.
        """
        print("Indexing Internal Statistics (Summary Tables)...")
        
        # 1. Define Knowledge Map
        # Describes WHAT each table contains (Granularity & Dimensions)
        summary_tables = [
            {
                "table": "metrics_totales_empresa_ejercicio",
                "label": "Resumen General (Total Sales)",
                "description": "Contains the grand total of sales (neto, coste, margen) for the whole company and year. Use this for general questions like 'How much did we sell?', 'Total margin', 'Global Status'.",
                "fields": ["importe_neto_total", "importe_coste_total", "albaranes_count"]
            },
            {
                "table": "metrics_totales_empresa_ejercicio_mes",
                "label": "Evolución Mensual (Monthly Sales)",
                "description": "Contains sales broken down by MONTH. Use this for 'evolution', 'trend', 'best month', 'seasonal analysis', 'monthly sales'.",
                "fields": ["mes", "importe_neto_total"]
            },
            {
                "table": "metrics_totales_empresa_ejercicio_cliente",
                "label": "Ventas por Cliente (Sales by Client)",
                "description": "Contains aggregated sales for each CLIENT. Use this for 'top clients', 'who bought the most', 'ranking of customers', 'client margin'.",
                "fields": ["cliente", "nombre", "importe_neto_total"]
            },
            {
                "table": "metrics_totales_empresa_ejercicio_articulo",
                "label": "Ventas por Artículo (Sales by Product)",
                "description": "Contains aggregated sales for each ARTICLE/PRODUCT. Use this for 'top products', 'best sellers', 'ranking of items', 'product margin'.",
                "fields": ["articulo", "descripcion", "importe_neto_total"]
            },
             {
                "table": "metrics_totales_empresa_ejercicio_cliente_mes",
                "label": "Ventas Cliente/Mes (Client Details)",
                "description": "Granular data of Client sales per specific Month. Use this for 'How much did Client X buy in January?'. Very detailed.",
                "fields": ["cliente", "mes", "importe_neto_total"]
            },
            {
                "table": "metrics_totales_empresa_ejercicio_codigo_postal",
                "label": "Ventas por Ubicación (PostCode/Provincia)",
                "description": "Geographical sales breakdown. Use this for 'ventas en Barcelona', 'sales by province', 'provincia', 'poblacion', 'codigo postal'.",
                "fields": ["codigo_postal", "poblacion", "provincia", "importe_neto_total"]
            }
        ]
        
        # 2. Index each definition
        for item in summary_tables:
            # Create a rich text representation for the vector DB
            text_block = (
                f"Table: {item['label']} (SQL: {item['table']}).\n"
                f"Description: {item['description']}\n"
                f"Fields: {', '.join(item['fields'])}"
            )
            
            vector = self.embed_text(text_block)
            
            MetricsEmbeddings.objects.update_or_create(
                kind='schema', # reused kind schema, or could be 'stats'
                key=item['table'],
                defaults={
                    'text': text_block,
                    'metadata': json.dumps({
                        'table': item['table'],
                        'name': item['label'],
                        'is_summary': True
                    }),
                    'vector': vector,
                    'updated_at': timezone.now()
                }
            )
            print(f"Indexed summary definition for {item['table']}")

    def ensure_cfo_guide_indexed(self):
        """
        Ensures the CFO guide templates are present in MetricsEmbeddings (kind='template').
        Idempotent via update_or_create with stable keys.
        """
        guides = [
            ("cfo_solvencia", "Guía CFO: Solvencia. Interpretar Solvencia = Activo Total / Pasivo Total. Objetivo > 1.5. Evaluar estructura del balance, capitalización y garantías para acreedores."),
            ("cfo_liquidez", "Guía CFO: Liquidez. Interpretar Liquidez (Razón corriente) = Activo Corriente / Pasivo Corriente. Objetivo > 1.2. Revisar fondo de maniobra y rotación de cobros/pagos."),
            ("cfo_margen", "Guía CFO: Margen Operativo. Analizar EBITDA y margen operativo. Señal crítica si margen < 5%. Plan de mejora de precios, mix y costes directos."),
            ("cfo_dupont", "Guía CFO: DuPont. Descomponer ROE en margen, rotación de activos y apalancamiento. Identificar palancas de mejora de rentabilidad."),
            ("cfo_costes", "Guía CFO: Estructura de Costes. Analizar peso de costes fijos vs variables, eficiencia operativa y compras. Foco en racionalización y negociación."),
            ("cfo_action_plan", "Guía CFO: Plan de Acción. Definir acciones a corto (choque) y medio plazo (estructurales): precios, mix, eficiencia, refinanciación, gestión de caja.")
        ]
        for key, text in guides:
            vector = self.embed_text(text)
            MetricsEmbeddings.objects.update_or_create(
                kind='template',
                key=key,
                defaults={
                    'text': text,
                    'metadata': json.dumps({
                        'sql': '',
                        'type': 'guide',
                        'label': 'Guía CFO'
                    }),
                    'vector': vector,
                    'updated_at': timezone.now()
                }
            )

    def get_cfo_guides(self) -> list:
        """
        Returns CFO guide templates with text and vectors for similarity scoring.
        """
        items = MetricsEmbeddings.objects.filter(kind='template').filter(key__startswith='cfo_')
        results = []
        for it in items:
            try:
                results.append({
                    'key': it.key,
                    'text': it.text,
                    'vector': it.vector
                })
            except Exception:
                continue
        return results
