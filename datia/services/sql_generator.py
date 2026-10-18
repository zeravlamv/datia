"""
SQL Example Generator Service
Generates diverse SQL queries for tpl_ingest_* tables to train the AI knowledge base.
"""
from typing import List, Dict, Optional
import json
import datetime
import hashlib
from datia.models import DataSource, DataField, MetricsEmbeddings
from datia.factories import ServiceFactory



class SQLExampleGenerator:
    """Generates SQL training examples for migrated tables"""
    
    QUERY_TYPES = {
        'simple': 5,      # Basic filters and projections
        'aggregation': 5,  # GROUP BY with SUM, COUNT, AVG
        'temporal': 3,     # Date ranges, BETWEEN
        'complex': 2,      # Multiple conditions, CASE WHEN
    }
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def generate_for_table(self, datasource: DataSource, count: int = 15, model: str = None) -> List[Dict]:
        """
        Generate 'count' diverse SQL examples for a single table.
        
        Args:
            datasource: The DataSource object
            count: Number of examples to generate
            model: Optional model name override
        """
        if not datasource.is_active:
             # Just a warning or check, but let's allow generation if passed
             pass
        
        fields = datasource.fields.filter(is_active=True)
        
        if not fields.exists():
            return []
        
        # Build prompt
        prompt = self.build_prompt(datasource, fields, count)
        
        # Call LLM
        # Increase timeout to 5 minutes (300s) for batch generation
        response_text = self.llm.generate_text(prompt, timeout=300, model=model)
        
        # Parse response
        queries = self.parse_response(response_text)
        
        return queries[:count]  # Ensure we don't exceed requested count

    def generate_single_query(self, datasource: DataSource, model: str = None) -> Optional[Dict]:
        """Generates exactly ONE query for the table"""
        fields = list(datasource.fields.filter(is_active=True))
        prompt = self.build_prompt(datasource, fields, count=1)
        
        try:
            # Increased timeout for local LLM (120s)
            response_text = self.llm.generate_text(prompt, timeout=120, model=model)
            queries = self.parse_response(response_text)
            return queries[0] if queries else None
        except Exception as e:
            print(f"Error generating single query: {e}")
            return None
    
    def build_prompt(self, datasource: DataSource, fields, count: int) -> str:
        """Build LLM prompt with table schema and instructions"""
        
        # [FIXED] Use the physical table name (DatiaDB_...) for the SQL prompt
        table_name = datasource.get_local_table_name()
        table_context = datasource.table_context or "Tabla de datos empresariales"
        
        # Build fields description
        fields_desc = []
        for field in fields:
            field_type = "Métrica numérica" if field.usage_type == 'metric' else "Dimensión descriptiva"
            # NOTE: Postgres columns are Case Sensitive if created with quotes. 
            # We explicitly tell AI to use double quotes.
            semantic = field.description or field.business_name or "Sin descripción"
            fields_desc.append(f'- "{field.field_name}" ({field.data_type}): {semantic} [{field_type}]')
        
        fields_text = "\n".join(fields_desc)
        
        
        # Specific Business Logic Injection
        specific_rules = ""
        if "albaran" in table_name.lower():
             specific_rules += "\n6. REGLA DE NEGOCIO: En tablas de ALBARANES, usa SIEMPRE 'FechaAlbaran' (o similar) como fecha principal en lugar de 'FechaPedido'. La fecha de pedido no es relevante para el albarán."

        prompt = f"""Eres un experto en SQL y análisis de datos empresariales.

Tabla: {table_name}
Contexto: {table_context}

Campos disponibles:
{fields_text}

Genera {count} preguntas de negocio REALISTAS que un usuario haría sobre esta tabla y el SQL correspondiente.

VARIEDAD OBLIGATORIA:
- {self.QUERY_TYPES['simple']} queries simples (filtros básicos: WHERE, ORDER BY)
- {self.QUERY_TYPES['aggregation']} queries con agregaciones (GROUP BY, SUM, COUNT, AVG)
- {self.QUERY_TYPES['temporal']} queries temporales (si hay campos de fecha: BETWEEN, DATE_TRUNC)
- {self.QUERY_TYPES['complex']} queries complejas (múltiples condiciones, subqueries)

REGLAS CRÍTICAS:
1. Usa SOLO nombres de campos que existen en la lista anterior
2. El SQL debe ser válido para PostgreSQL
3. La descripción debe ser en lenguaje natural español, como si un usuario la escribiera
4. Varía la complejidad: mezcla queries simples y avanzadas
5. IMPORTANTE: PostgreSQL es case-sensitive. Usa SIEMPRE comillas dobles para el nombre de la tabla y las columnas. Ej: SELECT "Campo" FROM "Tabla"{specific_rules}

Formato de salida JSON (CRÍTICO: devuelve SOLO el JSON, sin texto adicional):
[
  {{
    "description": "¿Cuál es el total de ventas del mes pasado?",
    "sql": "SELECT SUM(importe_total) FROM {table_name} WHERE fecha BETWEEN..."
  }},
  ...
]
"""
        return prompt
    
    def parse_response(self, response_text: str) -> List[Dict]:
        """Parse LLM JSON response"""
        try:
            # Remove markdown code blocks if present
            cleaned = response_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            
            queries = json.loads(cleaned.strip())
            
            # Validate structure
            if not isinstance(queries, list):
                raise ValueError("Response is not a list")
            
            for q in queries:
                if 'description' not in q or 'sql' not in q:
                    raise ValueError("Invalid query structure")
            
            return queries
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing LLM response: {e}")
            # FALBACK: Try to find a JSON list in the text using Regex
            import re
            try:
                # Find valid JSON array pattern [...]
                match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if match:
                    potential_json = match.group(0)
                    queries = json.loads(potential_json)
                    return queries
            except Exception as e2:
                print(f"Regex fallback failed: {e2}")

            print(f"Response was: {response_text[:500]}")
            return []

    def rewrite_descriptions(self, queries: List[Dict], datasource: DataSource, model: str = None) -> List[Dict]:
        """Pide al modelo frases de negocio para los primeros SQL ya validados."""
        if not model or not queries:
            return queries
        sample = queries[:12]
        lines = []
        for index, item in enumerate(sample, start=1):
            lines.append(f"{index}. {item.get('sql', '')}")
        prompt = (
            "Escribe una pregunta corta en español, como la haría un usuario de negocio, "
            f"para cada SQL de la tabla {datasource.name}. "
            "Devuelve solo un JSON con una lista de textos, en el mismo orden.\n"
            + "\n".join(lines)
        )
        try:
            raw = self.llm.generate_text(prompt, timeout=90, model=model)
            cleaned = (raw or '').strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
            parsed = json.loads(cleaned.strip())
            if isinstance(parsed, list):
                for index, description in enumerate(parsed):
                    if index < len(queries) and isinstance(description, str) and description.strip():
                        queries[index]['description'] = description.strip()
        except Exception as exc:
            print(f"No se reescribieron las descripciones con el modelo: {exc}")
        return queries
    
    def save_to_knowledge_base(self, queries: List[Dict], table_name: str, empresa_id=None, model_name: str = '') -> int:
        """
        Save generated queries to MetricsEmbeddings table.
        
        Args:
            queries: List of {description, sql} dicts
            table_name: Source table name for reference
            
        Returns:
            Number of queries successfully saved
        """
        saved_count = 0
        self.last_error = ''
        
        for idx, query in enumerate(queries):
            try:
                # Generate embedding for the description
                embedding_service = ServiceFactory.get_embedding_service()
                
                if not embedding_service:
                    self.last_error = 'No hay servicio de vectores.'
                    print("❌ ERROR: No Embedding Service available (Check Providers/Keys)")
                    continue

                description_text = query.get('description', '')
                if isinstance(description_text, list):
                    description_text = " ".join([str(x) for x in description_text])
                elif not isinstance(description_text, str):
                    description_text = str(description_text)
                description_text = description_text.strip() or f'Consulta de {table_name}'
                query['description'] = description_text

                embedding = embedding_service.embed_text(description_text)
                
                if not embedding:
                     self.last_error = 'El modelo de vectores no devolvió un vector.'
                     continue

                digest = hashlib.sha256(
                    f"{empresa_id}:{table_name}:{description_text}:{query.get('sql', '')}".encode('utf-8')
                ).hexdigest()[:20]
                unique_key = f"auto_{digest}"
                
                metadata = {
                    'sql_template': query['sql'],
                    'sql': query['sql'],
                    'source_table': table_name,
                    'scope': 'auto_training',
                    'generated_at': str(datetime.datetime.now()),
                    'llm_description': query.get('description', ''),
                    'model': model_name or '',
                }
                if empresa_id is not None and empresa_id != '':
                    try:
                        metadata['empresa_id'] = int(empresa_id)
                    except Exception:
                        metadata['empresa_id'] = empresa_id

                obj, created = MetricsEmbeddings.objects.update_or_create(
                    kind='qa',
                    key=unique_key,
                    defaults={
                        'text': query['description'],
                        'vector': embedding,
                        'metadata': metadata,
                    }
                )
                
                saved_count += 1
                
            except Exception as e:
                self.last_error = str(e)
                import traceback
                print(f"❌ CRITICAL ERROR saving query to knowledge base: {e}")
                print(traceback.format_exc())
                continue
        
        return saved_count

