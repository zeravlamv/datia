import logging
import json
import re
import unicodedata
import hashlib
import datetime
from typing import Dict, Any, Optional, List, Tuple
from django.db import connections, models
from datia.factories import ServiceFactory
from datia.services.ai.datia_schema import DatiaSchema
from datia.models.semantic import BusinessContext, DataSource, DataRelation, DataField, StandardField
from datia.services.ai.intent_detector import IntentDetector
from datia.services.ai.sql_variation_generator import SQLVariationGenerator
from datia.services.ai.auto_training_limiter import AutoTrainingLimiter
from datia.services.cache_service import QueryCacheService

logger = logging.getLogger(__name__)

class QueryBuilder:
    """
    Next-Gen Query Builder for Datia AI (Refactored v2).
    
    Architecture:
    1. Intent Detection (Router)
    2. Specialized Handlers (Ranking, Evolution, Comparison) with Schema Awareness
    3. Memory/Auto-Training Fallback
    """

    # --- CONFIGURATION: ENTITY DEFINITIONS ---
    ENTITIES = {
        'cliente': {
            'table': 'datiadb_lineaspedidocliente',
            'alias': 'L',
            'label_candidates': [
                'Nombre','RazonSocial','NombreCliente','Cliente','CodigoCliente',
                'CodCliente','IdCliente','ClienteNombre','ClienteRazonSocial',
                'CodigoTercero','IdTercero','Tercero','Cuenta','CodigoCuenta','NombreFiscal',
                'CodigoDelCliente','CodigoClienteProveedor'
            ],
            'date_col': 'FechaPedido',
            'count_col': 'NumeroPedido',
            'metric_source': 'lineas'
        },
        'articulo': {
            'table': 'datiadb_lineaspedidocliente',
            'alias': 'L',
            'label_candidates': [
                'DescripcionArticulo', 'Articulo', 'Producto',
                'Descripcion', 'DescripcionLinea', 'ArticuloDescripcion',
                'NombreArticulo', 'CodigoArticulo'
            ],
            'date_col': 'FechaPedido', # Changed to FechaPedido to force JOIN with Header for safety
            'count_col': 'NumeroPedido',
            'metric_source': 'lineas'
        },
        'agente': {
            'table': 'datiadb_cabecerapedidocliente',
            'alias': 'C',
            'label_candidates': ['NombreAgente', 'Agente', 'Vendedor', 'Comercial'],
            'date_col': 'FechaPedido',
            'count_col': 'NumeroPedido',
            'metric_source': 'cabecera'
        },
        'zona': {
            'table': 'datiadb_cabecerapedidocliente',
            'alias': 'C',
            'label_candidates': ['Zona', 'Region', 'Provincia'],
            'date_col': 'FechaPedido',
            'count_col': 'NumeroPedido',
            'metric_source': 'cabecera'
        },
        'familia': {
            'table': 'datiadb_lineaspedidocliente',
            'alias': 'L',
            'label_candidates': ['Familia', 'CodigoFamilia'],
            'date_col': 'FechaPedido', # Changed to FechaPedido to force JOIN with Header for safety
            'count_col': 'NumeroPedido',
            'metric_source': 'lineas'
        },
        'proveedor': {
            'table': 'datiadb_cabeceraalbaranproveedor', # Default to Albaranes for Purchases
            'alias': 'C',
            'label_candidates': ['NombreProveedor', 'Nombre', 'RazonSocial'],
            'date_col': 'FechaAlbaran',
            'count_col': 'NumeroAlbaran',
            'metric_source': 'cabecera'
        }
    }
    _INTENT_LEXICON = (
        'ventas', 'compras', 'cliente', 'clientes', 'articulo', 'articulos', 'producto', 'productos',
        'proveedor', 'proveedores', 'familia', 'familias', 'agente', 'agentes', 'zona', 'zonas',
        'stock', 'existencias', 'existencia', 'inventario', 'unidades', 'ranking', 'mejores', 'mejor',
        'peores', 'peor', 'mayores', 'mayor', 'principales', 'vendidos', 'vendido', 'mensual',
        'mensuales', 'trimestre', 'trimestral', 'ultimo', 'ultimos', 'analisis', 'informe', 'resumen',
        'albaran', 'albaranes', 'pedido', 'pedidos', 'margen', 'presupuesto', 'presupuestos',
        'tesoreria', 'balance', 'balances', 'ejercicio', 'anual', 'evolucion', 'tendencia', 'gastos',
        'ingresos', 'resultado', 'top', 'popular', 'populares', 'famoso', 'famosos',
        'estrella', 'estrellas', 'consumido', 'consumidos', 'demandado', 'demandados', 'cafe', 'cafes',
    )
    _INTENT_SYNONYMS = {
        'item': 'articulos', 'items': 'articulos', 'itens': 'articulos', 'itemes': 'articulos',
        'venetes': 'ventas', 'vendes': 'ventas', 'ventes': 'ventas', 'bentas': 'ventas',
        'compres': 'compras', 'conpras': 'compras',
        'clienets': 'clientes', 'clietes': 'clientes', 'clienes': 'clientes',
        'porductos': 'productos', 'prodcutos': 'productos',
        'artiuclos': 'articulos', 'faimlias': 'familias',
        'probveedor': 'proveedor', 'proweedor': 'proveedor',
        'darrera': 'ultimo', 'ultimso': 'ultimos', 'trimesre': 'trimestre',
        'mensul': 'mensual', 'mesual': 'mensual',
    }

    @staticmethod
    def _edit_distance(left: str, right: str, limit: int) -> int:
        if left == right:
            return 0
        if abs(len(left) - len(right)) > limit:
            return limit + 1
        prev_prev = None
        prev = list(range(len(right) + 1))
        for i, ca in enumerate(left, 1):
            cur = [i]
            row_min = i
            for j, cb in enumerate(right, 1):
                best = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (0 if ca == cb else 1))
                if i > 1 and j > 1 and ca == right[j - 2] and left[i - 2] == cb:
                    best = min(best, prev_prev[j - 2] + 1)
                cur.append(best)
                if best < row_min:
                    row_min = best
            if row_min > limit:
                return limit + 1
            prev_prev = prev
            prev = cur
        return prev[-1]

    @staticmethod
    def _closest_intent_term(token: str):
        if len(token) < 5 or any(ch.isdigit() for ch in token):
            return None
        limit = 2 if len(token) >= 8 else 1
        best = None
        best_distance = limit + 1
        tied = False
        terms = list(QueryBuilder._INTENT_LEXICON) + list(QueryBuilder._INTENT_SYNONYMS.keys())
        for term in terms:
            if abs(len(term) - len(token)) > limit:
                continue
            distance = QueryBuilder._edit_distance(token, term, limit)
            if distance <= limit and distance < best_distance:
                best = term
                best_distance = distance
                tied = False
            elif distance == best_distance and term != best:
                tied = True
        if tied or best is None:
            return None
        return QueryBuilder._INTENT_SYNONYMS.get(best, best)

    @staticmethod
    def _normalize_tokens(text: str) -> str:
        """
        Quita tildes y corrige erratas cercanas al vocabulario del chat.
        """
        nf = unicodedata.normalize('NFD', text or '')
        folded = ''.join(ch for ch in nf if unicodedata.category(ch) != 'Mn').lower()
        parts = re.split(r'(\w+)', folded)
        out = []
        for part in parts:
            if not part or not part[:1].isalnum():
                out.append(part)
                continue
            if part in QueryBuilder._INTENT_SYNONYMS:
                out.append(QueryBuilder._INTENT_SYNONYMS[part])
                continue
            if part in QueryBuilder._INTENT_LEXICON:
                out.append(part)
                continue
            fixed = QueryBuilder._closest_intent_term(part)
            out.append(fixed or part)
        return ''.join(out)

    @staticmethod
    def _resolve_entity_semantics(entity_key: str, empresa: int) -> Dict[str, Any]:
        """
        Overlay base ENTITIES config using semantic catalog (DataSource/DataField).
        """
        base = QueryBuilder.ENTITIES.get(entity_key, {}).copy()
        if not base:
            return {}
        synonyms = {
            'articulo': ['articulo', 'producto'],
            'cliente': ['cliente'],
            'agente': ['agente', 'vendedor', 'comercial'],
            'zona': ['zona', 'region', 'provincia'],
            'familia': ['familia'],
            'proveedor': ['proveedor']
        }
        syns = synonyms.get(entity_key, [entity_key])
        ds = None
        for s in syns:
            try:
                ds = DataSource.objects.filter(is_active=True, keywords__contains=[s]).first()
            except Exception:
                ds = None
            if ds:
                break
        if ds:
            local_tbl = ds.get_local_table_name()
            if local_tbl:
                base['table'] = local_tbl
            # Try to resolve label field via DataField
            label_df = None
            for s in syns:
                try:
                    label_df = DataField.objects.filter(source=ds, is_active=True, usage_type='dimension', synonyms__contains=[s]).first()
                except Exception:
                    label_df = None
                if label_df:
                    break
            if label_df:
                fn = (label_df.field_name or '').lower()
                # Solo aceptar dimensiones con semántica de identificador o nombre
                if ('codigo' in fn) or ('id' in fn) or ('nombre' in fn) or ('razonsocial' in fn):
                    base['label_candidates'] = [label_df.field_name]
            else:
                try:
                    any_dim = DataField.objects.filter(source=ds, is_active=True, usage_type='dimension').first()
                    if any_dim:
                        fn = (any_dim.field_name or '').lower()
                        if ('codigo' in fn) or ('id' in fn) or ('nombre' in fn) or ('razonsocial' in fn):
                            base['label_candidates'] = [any_dim.field_name]
                except Exception:
                    pass
            # Date field if specified
            try:
                date_df = DataField.objects.filter(source=ds, is_active=True, usage_type='date').first()
                if date_df:
                    base['date_col'] = date_df.field_name
            except Exception:
                pass
            if not base.get('date_col'):
                try:
                    std_dates = StandardField.objects.filter(semantic_role='DATE')
                    cand = [sf.name for sf in std_dates]
                    best, _ = QueryBuilder._validate_table_columns(base['table'], cand)
                    if best:
                        base['date_col'] = best
                except Exception:
                    pass
            base['semantic_used'] = True
            base['_semantic_ds_id'] = ds.id
        else:
            base['semantic_used'] = False
        return base

    @staticmethod
    def _find_header_table_for_lines(source_table: str, empresa: int, semantic_ds_id: Optional[int] = None) -> Optional[str]:
        """
        Resolve header table using DataRelation if possible; else heuristic.
        """
        if semantic_ds_id:
            try:
                ds = DataSource.objects.filter(id=semantic_ds_id).first()
                if ds:
                    rel = DataRelation.objects.filter(source=ds).first()
                    if rel:
                        return rel.target.get_local_table_name()
            except Exception:
                pass
        if 'lineas' in source_table:
            return source_table.replace('lineas', 'cabecera')
        return None

    @staticmethod
    def _resolve_audit_cols(table_name: str) -> Dict[str, str]:
        """
        Resolves critical audit columns (Company, Year, Count) checking real DB casing.
        """
        candidates = {
            'company': ['CodigoEmpresa', 'codigoempresa', 'CompanyId', 'IdEmpresa', 'Empresa'],
            'year': ['Ejercicio', 'ejercicio', 'Year', 'Anyo'],
            'count': ['NumeroPedido', 'numeropedido', 'NumeroAlbaran', 'numeroalbaran', 'Id', 'id']
        }
        
        resolved = {}
        _, col_map = QueryBuilder._validate_table_columns(table_name, []) # Get all cols
        
        if not col_map:
            # Fallback to Title Case if schema check fails
            return {'company': 'CodigoEmpresa', 'year': 'EjercicioPedido', 'count': 'NumeroPedido'}

        for key, possible_names in candidates.items():
            match = next((col_map[c.lower()] for c in possible_names if c.lower() in col_map), None)
            resolved[key] = match
            
        return resolved


    @staticmethod
    def _validate_table_columns(table_name: str, candidates: list[str]) -> Tuple[Optional[str], Dict[str, str]]:
        """
        Verifies which candidate columns actually exist in the DB.
        Returns: (best_match_column, full_column_map)
        """
        clean_tbl = table_name.replace('"', '').lower()
        try:
            db_alias = 'analytics' if 'analytics' in connections.databases else 'default'
            with connections[db_alias].cursor() as cursor:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = %s AND table_schema = 'public'
                """, [clean_tbl])
                real_cols = {row[0] for row in cursor.fetchall()}
                real_cols_lower = {c.lower(): c for c in real_cols}
                
                best_match = None
                for cand in candidates:
                    if cand.lower() in real_cols_lower:
                        best_match = real_cols_lower[cand.lower()]
                        break
                
                return best_match, real_cols_lower
        except Exception as e:
            logger.error(f"Schema Validation Error for {table_name}: {e}")
            return None, {}

    @staticmethod
    def _resolve_metrics(col_map: Dict[str, str], intent_text: str, is_purchase: bool = False, alias: Optional[str] = None) -> Tuple[str, str, str]:
        """
        Resolves (ValCol, CostCol, MetricType) based on available columns and intent.
        """
        # 1. Define Candidates
        sales_cands = ['ImporteLiquido', 'ImporteNeto', 'ImporteBruto', 'TotalNeto', 'BaseImponible']
        cost_cands = ['ImporteCoste', 'ImporteCosDte', 'CosteTotal', 'TotalCoste', 'Coste']
        qty_cands = ['Cantidad', 'Unidades', 'UnidadesPedidas', 'UnidadesServidas', 'Qty']
        
        # 2. Find existing columns
        real_sales = next((col_map[c.lower()] for c in sales_cands if c.lower() in col_map), None)
        if not real_sales:
            # Heurística: elegir cualquier columna que contenga 'importe' o 'neto' o 'total'
            real_sales = next((col_map[k] for k in col_map.keys() if ('importe' in k) or ('neto' in k) or ('total' in k)), 'ImporteBruto')
        real_cost = next((col_map[c.lower()] for c in cost_cands if c.lower() in col_map), None)
        real_cost_expr = None
        qty_col = next((col_map[c.lower()] for c in qty_cands if c.lower() in col_map), None)
        if not real_cost:
            if ('preciocoste' in col_map) and qty_col:
                if alias:
                    real_cost_expr = f'COALESCE({alias}."{col_map["preciocoste"]}", 0) * COALESCE({alias}."{qty_col}", 0)'
                else:
                    real_cost_expr = f'COALESCE("{col_map["preciocoste"]}", 0) * COALESCE("{qty_col}", 0)'
            elif ('preciocoste' in col_map) and ('importebruto' in col_map) and ('precio' in col_map):
                if alias:
                    qty_expr = f'COALESCE(NULLIF({alias}."{col_map["importebruto"]}", 0) / NULLIF({alias}."{col_map["precio"]}", 0), 0)'
                    real_cost_expr = f'COALESCE({alias}."{col_map["preciocoste"]}", 0) * {qty_expr}'
                else:
                    qty_expr = f'COALESCE(NULLIF("{col_map["importebruto"]}", 0) / NULLIF("{col_map["precio"]}", 0), 0)'
                    real_cost_expr = f'COALESCE("{col_map["preciocoste"]}", 0) * {qty_expr}'
        
        # 3. Determine Intent
        metric_type = 'sales'
        if is_purchase:
            metric_type = 'purchase_amount'
            # Purchases usually don't have cost, just Net Amount
            val_col = real_sales
            cost_col = "0"
        elif 'coste' in intent_text or 'gasto' in intent_text:
            metric_type = 'cost'
            val_col = real_cost if real_cost else (real_cost_expr if real_cost_expr else "0")
            cost_col = "0"
        elif 'margen' in intent_text or 'beneficio' in intent_text or 'rentab' in intent_text:
            metric_type = 'margin'
            val_col = real_sales
            cost_col = real_cost if real_cost else (real_cost_expr if real_cost_expr else "0")
        else:
            # Default Sales
            val_col = real_sales
            cost_col = real_cost if real_cost else (real_cost_expr if real_cost_expr else "0")
            
        return val_col, cost_col, metric_type

    @staticmethod
    def _format_col(alias: str, col: str) -> str:
        """
        Formats a column safely. Handles "0" literal.
        """
        if col == "0":
            return "0"
        if (" " in col) or ("(" in col) or (")" in col) or ("*" in col) or ("/" in col) or ("+" in col) or ("-" in col) or ("COALESCE" in col) or ("NULLIF" in col):
            return col
        return f'{alias}."{col}"' if alias else f'"{col}"'

    @staticmethod
    def _is_code_like(col_name: Optional[str]) -> bool:
        if not col_name:
            return False
        c = (col_name or '').lower()
        if 'codigo' in c:
            return True
        if c.startswith('id') or c.startswith('id_') or c.endswith('_id') or c.endswith('id'):
            return True
        if c in {'cliente', 'clientes', 'proveedor', 'proveedores', 'articulo', 'articulos', 'producto', 'productos', 'tercero', 'cuenta'}:
            return True
        return False

    @staticmethod
    def _prefer_human_label(entity_key: str, col_map: Dict[str, str], current_label_col: str) -> str:
        prefs = {
            'cliente': ['razonsocial', 'nombrecliente', 'nombre_cliente', 'cliente_nombre', 'nombre', 'nombrefiscal'],
            'proveedor': ['razonsocial', 'nombreproveedor', 'nombre_proveedor', 'nombre', 'nombrefiscal'],
            'articulo': ['descripcionarticulo', 'descripcion', 'descripcionlinea', 'nombrearticulo', 'articulo', 'producto'],
            'familia': ['descripcionfamilia', 'descripcion', 'familia'],
            'agente': ['nombreagente', 'agente', 'vendedor', 'comercial', 'nombre'],
            'zona': ['zona', 'region', 'provincia'],
        }
        for p in prefs.get(entity_key, []):
            if p in col_map:
                return col_map[p]
        return current_label_col

    @staticmethod
    def _master_label_join(entity_key: str, alias: str, label_col: str, company_col: str) -> Tuple[str, str, str]:
        masters = {
            'cliente': {'table': 'datia_cliente', 'key': 'cliente', 'label': 'nombre', 'has_company': True},
            'proveedor': {'table': 'datia_proveedores', 'key': 'proveedor', 'label': 'nombre', 'has_company': True},
            'articulo': {'table': 'datia_articulos', 'key': 'articulo', 'label': 'descripcion', 'has_company': True},
            'familia': {'table': 'datia_familias', 'key': 'codigo_familia', 'label': 'descripcion', 'has_company': False},
        }
        m = masters.get(entity_key)
        if not m:
            return "", f'{alias}."{label_col}"', "1"
        parts = []
        if m.get('has_company'):
            parts.append(f'M."empresa" = {alias}."{company_col}"')
        parts.append(f'M."{m["key"]}" = {alias}."{label_col}"')
        join_sql = "LEFT JOIN " + f'"{m["table"]}"' + " M ON " + " AND ".join(parts)
        label_expr = f'COALESCE(M."{m["label"]}", ({alias}."{label_col}")::text)'
        group_by_expr = f'{alias}."{label_col}", M."{m["label"]}"'
        return join_sql, label_expr, group_by_expr

    @staticmethod
    def _ranking_period(question: str, ejercicio):
        folded = QueryBuilder._fold_party(question or '')
        month_range = None
        meses = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12, 'setiembre': 9,
        }

        def to_m(tok: str):
            tok = (tok or '').lower()
            if tok.isdigit():
                value = int(tok)
                return value if 1 <= value <= 12 else None
            return meses.get(tok)

        m_between = re.search(r'\b(entre|desde|de)\s+([a-z]+|\d{1,2})\s+(?:y|a|hasta)\s+([a-z]+|\d{1,2})\b', folded)
        if m_between:
            start = to_m(m_between.group(2))
            end = to_m(m_between.group(3))
            if start and end:
                month_range = (start, end)
        if not month_range:
            m_one = re.search(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|setiembre)\b', folded)
            if m_one:
                value = meses.get(m_one.group(1))
                if value:
                    month_range = (value, value)
        quarter = None
        m_q = re.search(r'\bq\s*([1-4])\b', folded) or re.search(r'\btrimestre\s*([1-4])\b', folded)
        if m_q:
            quarter = int(m_q.group(1))
        elif re.search(r'\bultimo trimestre\b', folded):
            quarter = 4
        semester = None
        m_s = re.search(r'\bsemestre\s*([12])\b', folded)
        if m_s:
            semester = int(m_s.group(1))
        last_three = bool(
            re.search(r'(los\s+)?(ultimos)\s+3\s+meses', folded)
            or re.search(r'(3|tres)\s+(ultimos)\s+meses', folded)
        )
        if quarter and not month_range:
            month_range = ((quarter - 1) * 3 + 1, quarter * 3)
        elif semester and not month_range:
            month_range = (1, 6) if semester == 1 else (7, 12)
        elif last_three and not month_range:
            now = datetime.datetime.now()
            try:
                year_now = int(ejercicio)
            except (TypeError, ValueError):
                year_now = now.year
            if year_now == now.year:
                end_m = now.month
                start_m = max(1, end_m - 2)
            else:
                start_m, end_m = 10, 12
            month_range = (start_m, end_m)
        return month_range

    @staticmethod
    def _ranking_from_metrics(question: str, empresa, ejercicio, entity_key: str):
        """Ranking de cliente o artículo con el neto ya calculado. No altera los ratios."""
        if entity_key not in ('cliente', 'articulo'):
            return None
        folded = QueryBuilder._fold_party(question or '')
        if entity_key == 'articulo' and re.search(r'\b(compra|compras|proveedor|proveedores)\b', folded):
            return None
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return None
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            target_year = datetime.datetime.now().year
        limit_match = re.search(r'\b(5|10|15|20|50|100)\b', folded)
        limit = int(limit_match.group(1)) if limit_match else 20
        if not limit_match:
            one = re.search(r'\b(mejor|peor|popular|famoso|estrella|vendido|consumido|demandado)\b', folded)
            many = re.search(r'\b(mejores|peores|populares|famosos|estrellas|vendidos|consumidos|demandados)\b', folded)
            one_thing = re.search(r'\b(cliente|producto|articulo|cafe)\b', folded)
            many_things = re.search(r'\b(clientes|productos|articulos|cafes)\b', folded)
            if one and not many and one_thing and not many_things:
                limit = 1
            elif re.search(r'\b(el|la)\s+mas\b', folded) and not many_things:
                limit = 1
        order_kw = 'ASC' if re.search(r'\b(peores|peor|menor|worst|menos)\b', folded) else 'DESC'
        month_range = QueryBuilder._ranking_period(question, ejercicio)
        if entity_key == 'articulo' and month_range:
            return None
        if order_kw == 'ASC':
            filtro_importe = 'importe_neto_total > 0'
            having_importe = 'SUM(importe_neto_total) > 0'
        else:
            filtro_importe = '(importe_neto_total <> 0 OR albaranes_count <> 0)'
            having_importe = 'SUM(importe_neto_total) <> 0 OR SUM(albaranes_count) <> 0'
        if entity_key == 'cliente' and month_range:
            start_m, end_m = month_range
            sql = (
                'SELECT COALESCE(NULLIF(BTRIM(MAX(nombre)), \'\'), cliente) AS label, '
                'SUM(importe_neto_total) AS val, SUM(importe_coste_total) AS coste, SUM(albaranes_count) AS ops '
                'FROM metrics_totales_empresa_ejercicio_cliente_mes '
                f'WHERE empresa = {empresa_id} AND ejercicio = {target_year} AND mes BETWEEN {int(start_m)} AND {int(end_m)} '
                'GROUP BY cliente '
                f'HAVING {having_importe} '
                f'ORDER BY 2 {order_kw} LIMIT {int(limit)}'
            )
        else:
            if entity_key == 'cliente':
                table = 'metrics_totales_empresa_ejercicio_cliente'
                label_col = 'nombre'
                code_col = 'cliente'
            else:
                table = 'metrics_totales_empresa_ejercicio_articulo'
                label_col = 'descripcion'
                code_col = 'articulo'
            sql = (
                f'SELECT COALESCE(NULLIF(BTRIM({label_col}), \'\'), {code_col}) AS label, '
                'importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops '
                f'FROM {table} '
                f'WHERE empresa = {empresa_id} AND ejercicio = {target_year} '
                f'AND {filtro_importe} '
                f'ORDER BY 2 {order_kw} LIMIT {int(limit)}'
            )
        return {
            'key': f'ranking_{entity_key}',
            'sql': ' '.join(sql.split()),
            'type': 'table',
            'chart_type': 'bar',
            'label': f'Top {entity_key.capitalize()}s {target_year}',
            'source': 'deterministic_v2',
            'intent_meta': {'metric': 'sales', 'ejercicio': target_year},
        }

    @staticmethod
    def _handle_ranking(question: str, empresa: int, ejercicio: int, entity_key: str) -> Optional[Dict[str, Any]]:
        """
        Handler for Top/Ranking queries.
        Refactored to ensure correct Date usage (Header vs Lines).
        """
        metrics_rank = QueryBuilder._ranking_from_metrics(question, empresa, ejercicio, entity_key)
        if metrics_rank:
            return metrics_rank

        config = QueryBuilder._resolve_entity_semantics(entity_key, empresa)
        if not config: return None
        
        alias = config['alias']
        
        q_tok = QueryBuilder._normalize_tokens(question)
        if entity_key == 'cliente':
            if ('albaran' in q_tok) or ('albaranes' in q_tok):
                config['table'] = 'datiadb_cabeceraalbarancliente'
                config['alias'] = 'C'
                config['metric_source'] = 'cabecera'
                config['date_col'] = 'FechaAlbaran'
                config['count_col'] = 'NumeroAlbaran'

        # 1. Schema Validation
        _, probe_map = QueryBuilder._validate_table_columns(config['table'], [])
        if not probe_map:
            try:
                vector_service = ServiceFactory.get_embedding_service()
                schema_hits = vector_service.search_schema(question, threshold=0.35, limit=3)
                best_tbl = next(((h.get('metadata') or {}).get('table') for h in schema_hits 
                                 if (((h.get('metadata') or {}).get('table') or '').lower().startswith('datiadb_'))),
                                None)
                if best_tbl:
                    config['table'] = best_tbl
            except Exception:
                pass
        if not probe_map and entity_key == 'articulo':
            # Fallback a líneas de albarán cuando líneas de pedido no existen
            config['table'] = 'datiadb_lineasalbarancliente'
            # Ajustar claves semánticas para albarán
            config['count_col'] = 'NumeroAlbaran'
            config['date_col'] = 'FechaAlbaran'
        label_col, col_map = QueryBuilder._validate_table_columns(config['table'], config['label_candidates'])
        if not label_col:
            fallback_labels = QueryBuilder.ENTITIES.get(entity_key, {}).get('label_candidates', [])
            label_col, col_map = QueryBuilder._validate_table_columns(config['table'], fallback_labels)
            if not label_col:
                for k in col_map.keys():
                    kk = k.lower()
                    if ('razonsocial' in kk) or ('nombrecliente' in kk) or (kk == 'nombre'):
                        label_col = col_map[k]
                        break
                    if (kk == 'cliente') or (kk == 'codigo_cliente') or (kk == 'nombre_cliente') or (kk == 'cliente_nombre') or (kk == 'cliente_razon_social'):
                        label_col = col_map[k]
                        break
                    if ('idcliente' in kk) or ('clienteid' in kk):
                        label_col = col_map[k]
                        break
                    if ('codigocliente' in kk) or ('codigo_cliente' in kk) or ('codcliente' in kk):
                        label_col = col_map[k]
                        break
                    if ('cliente' in kk) and (('nombre' in kk) or ('razon' in kk) or ('codigo' in kk) or ('id' in kk)):
                        label_col = col_map[k]
                        break
                if not label_col:
                    # Último recurso: cualquier columna que contenga 'cliente'
                    for k in col_map.keys():
                        kk = k.lower()
                        if 'cliente' in kk:
                            label_col = col_map[k]
                            break
                    # Probar con StandardField (DIMENSION) que contenga el nombre de la entidad
                    if not label_col:
                        try:
                            std_dims = StandardField.objects.filter(semantic_role='DIMENSION')
                            entity_token = entity_key.lower()
                            cand_std = next((sf.name for sf in std_dims if entity_token in (sf.name or '').lower()), None)
                            if cand_std and (cand_std.lower() in col_map):
                                label_col = col_map[cand_std.lower()]
                        except Exception:
                            pass
                    if not label_col:
                        logger.warning(f"Ranking Handler: Could not resolve label column for {entity_key}")
                        return None
        # Si la tabla no tiene columna de empresa, cambiar a líneas
        audit_probe = QueryBuilder._resolve_audit_cols(config['table'])
        if not audit_probe.get('company') and entity_key == 'cliente':
            alt_table = 'datiadb_lineasalbarancliente' if (('albaran' in q_tok) or ('albaranes' in q_tok)) else 'datiadb_lineaspedidocliente'
            _, alt_map = QueryBuilder._validate_table_columns(alt_table, [])
            if alt_map:
                config['table'] = alt_table
                config['alias'] = 'L'
                config['metric_source'] = 'lineas'
                config['date_col'] = 'FechaAlbaran' if alt_table == 'datiadb_lineasalbarancliente' else 'FechaPedido'
                config['count_col'] = 'NumeroAlbaran' if alt_table == 'datiadb_lineasalbarancliente' else 'NumeroPedido'
                # Revalidar label_col con nuevo mapa
                label_col, col_map = QueryBuilder._validate_table_columns(config['table'], config['label_candidates'])
                if not label_col:
                    # Buscar por tokens estándar en líneas
                    for k in col_map.keys():
                        kk = k.lower()
                        if ('codigodelcliente' in kk) or ('idcliente' in kk) or ('cliente' in kk):
                            label_col = col_map[k]
                            break
                if not label_col:
                    logger.warning("Ranking Handler: Fallback a líneas sin label_col")
                    return None
                # Alinear alias para el resto del handler
                alias = config['alias']
            
        # 2. Metric Resolution
        is_purchase = (entity_key == 'proveedor')
        val_col, cost_col, metric_type = QueryBuilder._resolve_metrics(col_map, question.lower(), is_purchase, alias)
        # Si no hay columna de valor en la tabla actual y es 'cliente', forzar fallback a Líneas
        if entity_key == 'cliente':
            missing_val = (val_col is None) or (val_col.lower() not in col_map)
            if missing_val:
                alt_table = 'datiadb_lineasalbarancliente' if (('albaran' in q_tok) or ('albaranes' in q_tok)) else 'datiadb_lineaspedidocliente'
                _, alt_map = QueryBuilder._validate_table_columns(alt_table, [])
                if alt_map:
                    config['table'] = alt_table
                    config['alias'] = 'L'
                    config['metric_source'] = 'lineas'
                    config['date_col'] = 'FechaAlbaran' if alt_table == 'datiadb_lineasalbarancliente' else 'FechaPedido'
                    config['count_col'] = 'NumeroAlbaran' if alt_table == 'datiadb_lineasalbarancliente' else 'NumeroPedido'
                    # Resetear candidatos de etiqueta al patrón base para evitar contaminación semántica
                    try:
                        base_cands = QueryBuilder.ENTITIES.get('cliente', {}).get('label_candidates') or []
                        if base_cands:
                            config['label_candidates'] = base_cands
                    except Exception:
                        pass
                    alias = config['alias']
                    # Recalcular mapa y métricas
                    label_col, col_map = QueryBuilder._validate_table_columns(config['table'], config['label_candidates'])
                    if not label_col:
                        for k in col_map.keys():
                            kk = k.lower()
                            if ('codigodelcliente' in kk) or ('idcliente' in kk) or ('cliente' in kk):
                                label_col = col_map[k]
                                break
                    val_col, cost_col, metric_type = QueryBuilder._resolve_metrics(col_map, question.lower(), False, alias)
                    if not label_col:
                        logger.warning("Ranking Handler: Fallback a líneas sin label_col")
                        return None
        
        # 3. Year Resolution
        years = re.findall(r'\b(20\d{2})\b', question)
        target_year = int(years[0]) if years else (int(ejercicio) if ejercicio else datetime.datetime.now().year)
        
        # 4. Date Column Resolution & Join Injection (Rule: Lines need Cabecera for Date Safety)
        date_col_name = None
        join_clause = ""
        
        # Determine if we need to join with Cabecera
        needs_join = False
        if config['metric_source'] == 'lineas':
            # Check if DateCol exists in Lines table
            found_in_lines, _ = QueryBuilder._validate_table_columns(config['table'], [config['date_col']])
            if not found_in_lines:
                # Si existe alguna columna con token 'fecha' en la tabla de líneas, no forzar JOIN
                has_any_date = any('fecha' in k.lower() for k in col_map.keys())
                needs_join = not has_any_date
        
        if needs_join:
            # JOIN STRATEGY
            # Try semantic relation first, fallback to naming heuristic
            cabecera_table = QueryBuilder._find_header_table_for_lines(config['table'], empresa, config.get('_semantic_ds_id')) or config['table'].replace('lineas', 'cabecera')
            
            # Verify Cabecera exists
            _, _ = QueryBuilder._validate_table_columns(cabecera_table, []) # Just check if valid table
            
            # Build JOIN
            # Check standard keys vs resolved
            audit_cols = QueryBuilder._resolve_audit_cols(cabecera_table)
            company_hdr = audit_cols.get('company', 'CodigoEmpresa')
            # Resolve alias-side columns and header-side equivalents
            alias_cols = col_map
            # Year
            ej_alias, _ = QueryBuilder._validate_table_columns(config['table'], ['EjercicioPedido', 'EjercicioDocumento', 'Ejercicio'])
            ej_hdr, _ = QueryBuilder._validate_table_columns(cabecera_table, ['EjercicioPedido', 'EjercicioDocumento', 'Ejercicio'])
            # Serie
            serie_alias, _ = QueryBuilder._validate_table_columns(config['table'], ['SeriePedido', 'SerieDocumento', 'SerieAlbaran', 'Serie'])
            serie_hdr, _ = QueryBuilder._validate_table_columns(cabecera_table, ['SeriePedido', 'SerieDocumento', 'SerieAlbaran', 'Serie'])
            # Numero
            num_alias, _ = QueryBuilder._validate_table_columns(config['table'], ['NumeroPedido', 'NumeroDocumento', 'NumeroAlbaran', 'Numero'])
            num_hdr, _ = QueryBuilder._validate_table_columns(cabecera_table, ['NumeroPedido', 'NumeroDocumento', 'NumeroAlbaran', 'Numero'])
            # Company alias
            company_alias = QueryBuilder._resolve_audit_cols(config['table']).get('company', 'CodigoEmpresa')
            join_parts = []
            if company_alias.lower() in alias_cols and company_hdr.lower() in audit_cols:
                join_parts.append(f'H.\"{audit_cols[company_hdr.lower()]}\" = {alias}.\"{alias_cols[company_alias.lower()]}\"')
            else:
                join_parts.append(f'H.\"{company_hdr}\" = {alias}.\"{company_alias}\"')
            if ej_alias and ej_hdr:
                join_parts.append(f'H.\"{ej_hdr}\" = {alias}.\"{ej_alias}\"')
            if serie_alias and serie_hdr:
                join_parts.append(f'H.\"{serie_hdr}\" = {alias}.\"{serie_alias}\"')
            if num_alias and num_hdr:
                join_parts.append(f'H.\"{num_hdr}\" = {alias}.\"{num_alias}\"')
            join_on = " AND ".join(join_parts) if join_parts else "1=1"
            join_clause = f'JOIN \"{cabecera_table}\" H ON {join_on}'
            
            # Use Header Date
            # Check for FechaPedido or FechaAlbaran in Header
            date_candidates = ['FechaPedido', 'FechaAlbaran', 'Fecha', 'FechaDocumento']
            date_col_name, _ = QueryBuilder._validate_table_columns(cabecera_table, date_candidates)
            if not date_col_name:
                # Si la cabecera actual no tiene fecha, intentar cabecera de pedido (join por numeropedido/codigoempresa)
                alt_header = 'datiadb_cabecerapedidocliente'
                _, alt_cols = QueryBuilder._validate_table_columns(alt_header, [])
                if alt_cols:
                    # Construir JOIN alternativo
                    audit_alt = QueryBuilder._resolve_audit_cols(alt_header)
                    company_alt = audit_alt.get('company', 'CodigoEmpresa')
                    join_parts_alt = []
                    if ('numeropedido' in alt_cols) and ('numeropedido' in alias_cols):
                        join_parts_alt.append(f'H."{alt_cols["numeropedido"]}" = {alias}."{alias_cols["numeropedido"]}"')
                    if (company_alt.lower() in alt_cols) and ('codigoempresa' in alias_cols):
                        join_parts_alt.append(f'H."{alt_cols[company_alt.lower()]}" = {alias}."{alias_cols["codigoempresa"]}"')
                    join_on_alt = " AND ".join(join_parts_alt) if join_parts_alt else "1=1"
                    join_clause = f'JOIN \"{alt_header}\" H ON {join_on_alt}'
                    # Resolver fecha en cabecera alternativa
                    date_col_name, _ = QueryBuilder._validate_table_columns(alt_header, date_candidates)
                if not date_col_name:
                    # Fallback determinístico según tipo
                    date_col_name = 'FechaPedido'
            
            # Update date expression to use Header Alias (H)
            date_expr = f'H."{date_col_name}"'
            logger.info(f"Ranking Handler: Injected JOIN with {cabecera_table} for Date Safety")
            
        else:
            # NO JOIN - Use Table's own date
            date_col_name, _ = QueryBuilder._validate_table_columns(config['table'], [config['date_col'], 'Fecha', 'FechaDocumento'])
            if not date_col_name:
                # Buscar primera columna que contenga 'fecha'
                for k in col_map.keys():
                    if 'fecha' in k.lower():
                        date_col_name = col_map[k]
                        break
            if not date_col_name:
                date_col_name = config['date_col']
            date_expr = f'{alias}."{date_col_name}"'

        # 5. Build Query
        table = f'"{config["table"]}"'
        
        limit_match = re.search(r'\b(5|10|15|20|50|100)\b', question)
        limit = int(limit_match.group(1)) if limit_match else 20
        
        val_expr = QueryBuilder._format_col(alias, val_col)
        cost_expr = QueryBuilder._format_col(alias, cost_col)
        q_lower = QueryBuilder._normalize_tokens(question)
        is_asc = bool(re.search(r'\b(peores|peor|menor|worst|menos)\b', q_lower))
        order_kw = "ASC" if is_asc else "DESC"
        
        # Si es singular ("el mejor", "el peor"), limit = 1. Si es plural ("mejores", "peores"), limit = 20 por defecto.
        if not limit_match:
            if re.search(r'\b(el mejor|el peor|la mejor|la peor)\b', q_lower):
                limit = 1
            elif re.search(r'\b(mejor|peor)\b', q_lower) and not re.search(r'\b(mejores|peores)\b', q_lower):
                # heurística: si dice 'mejor cliente' singular
                if re.search(r'\b(cliente|producto|articulo|proveedor|agente|zona|familia)\b', q_lower) and not re.search(r'\b(clientes|productos|articulos|proveedores|agentes|zonas|familias)\b', q_lower):
                    limit = 1
        quarter = None
        m_q = re.search(r'\bq\s*([1-4])\b', q_lower)
        if m_q:
            quarter = int(m_q.group(1))
        else:
            m_t = re.search(r'\btrimestre\s*([1-4])\b', q_lower)
            if m_t:
                quarter = int(m_t.group(1))
            elif re.search(r'último trimestre|ultimo trimestre', q_lower):
                quarter = 4
        semester = None
        m_s = re.search(r'\bsemestre\s*([12])\b', q_lower)
        if m_s:
            semester = int(m_s.group(1))
        
        month_range = None
        m_between = re.search(r'\b(entre|desde|de)\s+([a-záéíóú]+|\d{1,2})\s+(?:y|a|hasta)\s+([a-záéíóú]+|\d{1,2})\b', q_lower)
        if m_between:
            start_tok = m_between.group(2)
            end_tok = m_between.group(3)
            meses = {
                'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
                'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12,'setiembre':9
            }
            def to_m(tok:str)->Optional[int]:
                tok = tok.lower()
                if tok.isdigit():
                    v = int(tok)
                    return v if 1<=v<=12 else None
                return meses.get(tok)
            s = to_m(start_tok)
            e = to_m(end_tok)
            if s and e:
                month_range = (s,e)
        if not month_range:
            meses = {
                'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
                'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12,'setiembre':9
            }
            m_one = re.search(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|setiembre)\b', q_lower)
            if m_one:
                mv = meses.get(m_one.group(1))
                if mv:
                    month_range = (mv, mv)
        
        last_three = False
        if re.search(r'(los\s+)?(últimos|ultimos)\s+3\s+meses', q_lower) or re.search(r'(3|tres)\s+(últimos|ultimos)\s+meses', q_lower):
            last_three = True

        # Resolve Audit Cols for WHERE
        audit_cols = QueryBuilder._resolve_audit_cols(config['table'])
        company_col = audit_cols.get('company', 'CodigoEmpresa')
        count_col = audit_cols.get('count', None)
        label_col = QueryBuilder._prefer_human_label(entity_key, col_map, label_col)
        label_join = ""
        label_expr = f'{alias}."{label_col}"'
        group_by_expr = "1"
        if QueryBuilder._is_code_like(label_col):
            lj, le, gb = QueryBuilder._master_label_join(entity_key, alias, label_col, company_col)
            if lj:
                label_join = lj
                label_expr = le
                group_by_expr = gb
        # Fallback robusto para contar operaciones
        if not count_col:
            # Buscar cualquier columna que contenga 'numero' y 'pedido' o 'albaran'
            cand = next((col_map[k] for k in col_map.keys() if (('numero' in k.lower()) and (('pedido' in k.lower()) or ('albaran' in k.lower())))), None)
            count_col = cand if cand else None
        # Expresión de conteo
        if count_col:
            ops_expr = f'COUNT(DISTINCT {alias}."{count_col}")'
        else:
            ops_expr = 'COUNT(*)'

        month_filter = ""
        if month_range:
            month_filter = f" AND EXTRACT(MONTH FROM {date_expr}) BETWEEN {month_range[0]} AND {month_range[1]}"
        elif last_three:
            now = datetime.datetime.now()
            if int(ejercicio) == now.year:
                end_m = now.month
                start_m = max(1, end_m-2)
            else:
                start_m, end_m = 10, 12
            month_filter = f" AND EXTRACT(MONTH FROM {date_expr}) BETWEEN {start_m} AND {end_m}"
        quarter_filter = f" AND EXTRACT(QUARTER FROM {date_expr}) = {quarter}" if quarter and not month_filter else ""
        semester_filter = f" AND (((EXTRACT(MONTH FROM {date_expr})::int - 1) / 6) + 1) = {semester}" if semester and not month_filter else ""
        sql = f"""
            SELECT 
                {label_expr} as label, 
                (SUM({val_expr}) - SUM({cost_expr})) as val, 
                SUM({cost_expr}) as coste, 
                {ops_expr} as ops 
            FROM {table} {alias}
            {join_clause}
            {label_join}
            WHERE {alias}."{company_col}" = {empresa} 
              AND EXTRACT(YEAR FROM {date_expr}) = {target_year}{month_filter}{quarter_filter}{semester_filter}
            GROUP BY {group_by_expr} 
            ORDER BY 2 {order_kw} 
            LIMIT {limit}
        """
        
        return {
            'key': f'ranking_{entity_key}',
            'sql': " ".join(sql.split()),
            'type': 'table',
            'chart_type': 'bar',
            'label': f'Top {entity_key.capitalize()}s {target_year}',
            'source': 'deterministic_v2',
            'intent_meta': {'metric': metric_type}
        }

    @staticmethod
    def _handle_company_figure(question: str, empresa, ejercicio):
        """Importe medio, número de albaranes o ventas del ejercicio, desde el total ya calculado."""
        folded = QueryBuilder._fold_party(question or '')
        if re.search(r'\b(compra|compras|proveedor|proveedores)\b', folded):
            return None
        if re.search(r'\b(cliente|clientes|articulo|articulos|producto|productos)\b', folded):
            return None
        if not re.search(r'\balbaran|\bventas?\b|\bfacturacion|\bticket\b', folded):
            return None
        asks_average = bool(re.search(r'\b(medio|media|promedio)\b', folded) or re.search(r'\bticket\b', folded))
        asks_count = bool(re.search(r'\b(cuantos|cuantas|numero)\b', folded) and re.search(r'\balbaran', folded))
        asks_year_total = bool(
            re.search(r'\b(total|totales|ejercicio|ano)\b', folded)
            and not re.search(r'\b(mensual|mensuales|evolucion|tendencia)\b', folded)
        )
        if not (asks_average or asks_count or asks_year_total):
            return None
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return QueryBuilder._party_reply('Elige la empresa y el ejercicio antes de preguntar.')
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            return QueryBuilder._party_reply('Elige la empresa y el ejercicio antes de preguntar.')
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        try:
            with connections[alias].cursor() as cur:
                cur.execute(
                    '''
                    SELECT importe_neto_total, albaranes_count
                    FROM metrics_totales_empresa_ejercicio
                    WHERE empresa = %s AND ejercicio = %s
                    ''',
                    [empresa_id, target_year],
                )
                row = cur.fetchone()
        except Exception:
            logger.exception('QueryBuilder: no se pudieron leer los totales de la empresa')
            return QueryBuilder._party_reply(f'No he podido leer las ventas de {target_year}.')
        if not row:
            return QueryBuilder._party_reply(f'No hay totales de ventas cargados para {target_year}.')
        neto = float(row[0] or 0)
        ops = int(row[1] or 0)
        ops_txt = f'{ops:,}'.replace(',', '.')
        if asks_average:
            medio = (neto / ops) if ops else 0
            titulo = 'Precio medio de venta' if re.search(r'\bprecio\b', folded) else 'Importe medio de albarán'
            text = (
                f'{titulo} en {target_year}: {QueryBuilder._eur_es(medio)} por albarán. '
                f'El total de ventas es {QueryBuilder._eur_es(neto)} netos en {ops_txt} albaranes.'
            )
        elif asks_count:
            text = f'Albaranes en {target_year}: {ops_txt}. Importe neto {QueryBuilder._eur_es(neto)}.'
        else:
            text = f'Ventas de {target_year}: {QueryBuilder._eur_es(neto)} netos en {ops_txt} albaranes.'
        return QueryBuilder._party_reply(text)

    @staticmethod
    def _sales_evolution_from_metrics(question: str, empresa, ejercicio):
        """Evolución de ventas por mes, trimestre o semestre con el neto ya calculado."""
        folded = QueryBuilder._fold_party(question or '')
        if re.search(r'\b(semana|semanal|dia|diario)\b', folded):
            return None
        if len(re.findall(r'\b(20\d{2})\b', question or '')) >= 2:
            return None
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return None
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            target_year = datetime.datetime.now().year
        if re.search(r'\b(trimestre|trimestral)\b', folded):
            label_sql = '((mes - 1) / 3) + 1'
            group = f'GROUP BY {label_sql} '
            select_val = f'{label_sql} AS label, SUM(importe_neto_total) AS val, SUM(importe_coste_total) AS coste, SUM(albaranes_count) AS ops'
        elif re.search(r'\b(semestre|semestral)\b', folded):
            label_sql = '((mes - 1) / 6) + 1'
            group = f'GROUP BY {label_sql} '
            select_val = f'{label_sql} AS label, SUM(importe_neto_total) AS val, SUM(importe_coste_total) AS coste, SUM(albaranes_count) AS ops'
        else:
            group = ''
            select_val = 'mes AS label, importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops'
        sql = (
            f'SELECT {select_val} FROM metrics_totales_empresa_ejercicio_mes '
            f'WHERE empresa = {empresa_id} AND ejercicio = {target_year} {group}ORDER BY 1'
        )
        return {
            'key': 'evolution_single',
            'sql': ' '.join(sql.split()),
            'type': 'chart',
            'chart_type': 'bar',
            'label': f'Evolución {target_year}',
            'source': 'deterministic_v2',
            'intent_meta': {'metric': 'sales', 'ejercicio': target_year},
        }

    @staticmethod
    def _handle_evolution(question: str, empresa: int, ejercicio: int, is_purchase: bool = False) -> Dict[str, Any]:
        """
        Handler for Monthly Evolution (Ventas/Compras).
        """
        # Determine Table
        if is_purchase:
            table = "datiadb_cabeceraalbaranproveedor"
            # Check if user asked for Orders specifically
            if 'pedido' in question.lower():
                table = "datiadb_cabecerapedidoproveedor"
        else:
            metrics_chart = QueryBuilder._sales_evolution_from_metrics(question, empresa, ejercicio)
            if metrics_chart:
                return metrics_chart
            # Sales -> Prefer Cabecera for speed, unless Lineas needed?
            # Actually, previous optimization used Join. Let's stick to Cabecera if possible for simplicity/speed
            # UNLESS we need deep metrics. 
            # For robustness, Cabecera is safer if it has ImporteCoste.
            table = "datiadb_cabecerapedidocliente"
            
        # Validate Schema
        _, col_map = QueryBuilder._validate_table_columns(table, [])
        if not col_map:
            return {'error': 'Schema validation failed for evolution'}

        # Resolve Metrics
        val_col, cost_col, metric_type = QueryBuilder._resolve_metrics(col_map, question.lower(), is_purchase, None)
        
        # Resolve Date
        date_candidates = ['FechaPedido', 'FechaAlbaran', 'Fecha', 'FechaDocumento']
        date_col = next((col_map[c.lower()] for c in date_candidates if c.lower() in col_map), 'FechaPedido')
        
        # Resolve Year
        years = re.findall(r'\b(20\d{2})\b', question)
        
        # Time grouping
        tg = 'month'
        if re.search(r'\bsemana|semanal\b', question):
            tg = 'week'
        elif re.search(r'\bd[ií]a|diario\b', question):
            tg = 'day'
        elif re.search(r'\bsemestre|semestral\b', question):
            tg = 'semester'
        elif re.search(r'\btrimestre|trimestral\b', question):
            tg = 'quarter'
        label_expr_map = {
            'month': f'EXTRACT(MONTH FROM "{date_col}")',
            'week': f'EXTRACT(WEEK FROM "{date_col}")',
            'day': f'EXTRACT(DAY FROM "{date_col}")',
            'quarter': f'EXTRACT(QUARTER FROM "{date_col}")',
            'semester': f'(((EXTRACT(MONTH FROM "{date_col}")::int - 1) / 6) + 1)'
        }
        label_expr = label_expr_map[tg]
        if len(years) >= 2:
            # COMPARISON (Multi-Year)
            years_sql = ", ".join(years)
            val_expr = QueryBuilder._format_col(None, val_col)
            cost_expr = QueryBuilder._format_col(None, cost_col)

            # Resolve Audit Cols
            audit_cols = QueryBuilder._resolve_audit_cols(table)
            company_col = audit_cols.get('company', 'CodigoEmpresa')
            count_col = audit_cols.get('count', 'NumeroPedido')

            sql = f"""
                SELECT 
                    {label_expr} as label, 
                    EXTRACT(YEAR FROM "{date_col}") as serie, 
                    SUM({val_expr}) as val, 
                    SUM({cost_expr}) as coste,
                    COUNT(DISTINCT "{count_col}") as ops 
                FROM "{table}" 
                WHERE "{company_col}" = {empresa} 
                  AND EXTRACT(YEAR FROM "{date_col}") IN ({years_sql})
                GROUP BY 1, 2 
                ORDER BY 2, 1
            """
            return {
                'key': 'evolution_comparison',
                'sql': " ".join(sql.split()),
                'type': 'chart',
                'chart_type': 'line',
                'label': f'Comparativa {years[0]} vs {years[-1]}',
                'source': 'deterministic_v2',
                'intent_meta': {'metric': metric_type, 'is_comparison': True}
            }
        else:
            # SINGLE YEAR
            target_year = years[0] if years else ejercicio
            val_expr = QueryBuilder._format_col(None, val_col)
            cost_expr = QueryBuilder._format_col(None, cost_col)

            # Resolve Audit Cols
            audit_cols = QueryBuilder._resolve_audit_cols(table)
            company_col = audit_cols.get('company', 'CodigoEmpresa')
            count_col = audit_cols.get('count', 'NumeroPedido')

            sql = f"""
                SELECT 
                    {label_expr} as label, 
                    SUM({val_expr}) as val, 
                    SUM({cost_expr}) as coste,
                    COUNT(DISTINCT "{count_col}") as ops 
                FROM "{table}" 
                WHERE "{company_col}" = {empresa} 
                  AND EXTRACT(YEAR FROM "{date_col}") = {target_year}
                GROUP BY label 
                ORDER BY label
            """
            return {
                'key': 'evolution_single',
                'sql': " ".join(sql.split()),
                'type': 'chart',
                'chart_type': 'bar',
                'label': f'Evolución {tg.capitalize()} {target_year}',
                'source': 'deterministic_v2',
                'intent_meta': {'metric': metric_type}
            }

    @staticmethod
    def _handle_grouping(question: str, empresa: int, ejercicio: int, entity_key: str) -> Optional[Dict[str, Any]]:
        config = QueryBuilder._resolve_entity_semantics(entity_key, empresa)
        if not config:
            return None
        alias = config['alias']
        label_col, col_map = QueryBuilder._validate_table_columns(config['table'], config['label_candidates'])
        if not label_col:
            probe = None
            for k in (col_map or {}).keys():
                kk = k.lower()
                if ('razonsocial' in kk) or ('nombrecliente' in kk) or (kk == 'nombre'):
                    probe = col_map[k]
                    break
                if (kk == 'cliente') or (kk == 'codigo_cliente') or (kk == 'nombre_cliente') or (kk == 'cliente_nombre') or (kk == 'cliente_razon_social'):
                    probe = col_map[k]
                    break
                if ('idcliente' in kk) or ('clienteid' in kk):
                    probe = col_map[k]
                    break
                if ('codigocliente' in kk) or ('codigo_cliente' in kk) or ('codcliente' in kk):
                    probe = col_map[k]
                    break
            label_col = probe
            if not label_col:
                return None
        is_purchase = (entity_key == 'proveedor')
        val_col, cost_col, metric_type = QueryBuilder._resolve_metrics(col_map, QueryBuilder._normalize_tokens(question), is_purchase, alias)
        years = re.findall(r'\b(20\d{2})\b', question)
        target_year = int(years[0]) if years else (int(ejercicio) if ejercicio else datetime.datetime.now().year)
        date_col_name = None
        join_clause = ""
        needs_join = False
        ej_alias = None
        ej_hdr = None
        if config['metric_source'] == 'lineas':
            found_in_lines, _ = QueryBuilder._validate_table_columns(config['table'], [config['date_col']])
            if not found_in_lines:
                needs_join = True
        if needs_join:
            cabecera_table = QueryBuilder._find_header_table_for_lines(config['table'], empresa, config.get('_semantic_ds_id')) or config['table'].replace('lineas', 'cabecera')
            _, header_cols = QueryBuilder._validate_table_columns(cabecera_table, [])
            if not header_cols:
                cabecera_table = "datiadb_cabecerapedidocliente"
                _, header_cols = QueryBuilder._validate_table_columns(cabecera_table, [])
            date_col_name, _ = QueryBuilder._validate_table_columns(cabecera_table, ['FechaPedido', 'FechaAlbaran', 'Fecha', 'FechaDocumento'])
            if not date_col_name:
                date_col_name = 'FechaPedido'
            alias_cols = col_map
            audit_header = QueryBuilder._resolve_audit_cols(cabecera_table)
            company_hdr = audit_header.get('company', 'CodigoEmpresa')
            company_alias = QueryBuilder._resolve_audit_cols(config['table']).get('company', 'CodigoEmpresa')
            join_parts = []
            if 'numeropedido' in alias_cols and 'numeropedido' in header_cols:
                join_parts.append(f'H."{header_cols["numeropedido"]}" = {alias}."{alias_cols["numeropedido"]}"')
            if company_alias.lower() in alias_cols and company_hdr.lower() in header_cols:
                join_parts.append(f'H."{header_cols[company_hdr.lower()]}" = {alias}."{alias_cols[company_alias.lower()]}"')
            ej_alias, _ = QueryBuilder._validate_table_columns(config['table'], ['EjercicioPedido', 'EjercicioDocumento', 'Ejercicio'])
            ej_hdr, _ = QueryBuilder._validate_table_columns(cabecera_table, ['EjercicioPedido', 'EjercicioDocumento', 'Ejercicio'])
            if ej_alias and ej_hdr:
                join_parts.append(f'H."{ej_hdr}" = {alias}."{ej_alias}"')
            serie_alias, _ = QueryBuilder._validate_table_columns(config['table'], ['SeriePedido', 'SerieDocumento', 'Serie'])
            serie_hdr, _ = QueryBuilder._validate_table_columns(cabecera_table, ['SeriePedido', 'SerieDocumento', 'Serie'])
            if serie_alias and serie_hdr:
                join_parts.append(f'H."{serie_hdr}" = {alias}."{serie_alias}"')
            join_clause = f'JOIN "{cabecera_table}" H ON ' + " AND ".join(join_parts) if join_parts else f'JOIN "{cabecera_table}" H ON 1=1'
            date_expr = f'H."{date_col_name}"'
        else:
            date_col_name, _ = QueryBuilder._validate_table_columns(config['table'], [config['date_col'], 'Fecha', 'FechaDocumento'])
            if not date_col_name:
                date_col_name = config['date_col']
            date_expr = f'{alias}."{date_col_name}"'
        table = f'"{config["table"]}"'
        val_expr = QueryBuilder._format_col(alias, val_col)
        cost_expr = QueryBuilder._format_col(alias, cost_col)
        q_lower = QueryBuilder._normalize_tokens(question)
        quarter = None
        m_q = re.search(r'\bq\s*([1-4])\b', q_lower)
        if m_q:
            quarter = int(m_q.group(1))
        else:
            m_t = re.search(r'\btrimestre\s*([1-4])\b', q_lower)
            if m_t:
                quarter = int(m_t.group(1))
            elif re.search(r'último trimestre|ultimo trimestre', q_lower):
                quarter = 4
        month_range = None
        m_between = re.search(r'\b(entre|desde|de)\s+([a-záéíóú]+|\d{1,2})\s+(?:y|a|hasta)\s+([a-záéíóú]+|\d{1,2})\b', q_lower)
        if m_between:
            start_tok = m_between.group(2)
            end_tok = m_between.group(3)
            meses = {
                'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
                'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12,'setiembre':9
            }
            def to_m(tok:str)->Optional[int]:
                tok = tok.lower()
                if tok.isdigit():
                    v = int(tok)
                    return v if 1<=v<=12 else None
                return meses.get(tok)
            s = to_m(start_tok)
            e = to_m(end_tok)
            if s and e:
                month_range = (s,e)
        if not month_range:
            meses = {
                'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12,
                'ene':1,'feb':2,'mar':3,'abr':4,'may':5,'jun':6,'jul':7,'ago':8,'sep':9,'oct':10,'nov':11,'dic':12,'setiembre':9
            }
            m_one = re.search(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|setiembre)\b', q_lower)
            if m_one:
                mv = meses.get(m_one.group(1))
                if mv:
                    month_range = (mv, mv)
        last_three = False
        if re.search(r'(los\s+)?(últimos|ultimos)\s+3\s+meses', q_lower) or re.search(r'(3|tres)\s+(últimos|ultimos)\s+meses', q_lower):
            last_three = True
        audit_cols = QueryBuilder._resolve_audit_cols(config['table'])
        company_col = audit_cols.get('company', 'CodigoEmpresa')
        count_col = audit_cols.get('count', config['count_col'])
        label_col = QueryBuilder._prefer_human_label(entity_key, col_map, label_col)
        label_join = ""
        label_expr = f'{alias}."{label_col}"'
        group_by_expr = "1"
        if QueryBuilder._is_code_like(label_col):
            lj, le, gb = QueryBuilder._master_label_join(entity_key, alias, label_col, company_col)
            if lj:
                label_join = lj
                label_expr = le
                group_by_expr = gb
        # Orden y límite dinámicos para frases como "peores 10" o "top 20"
        is_asc = bool(re.search(r'\b(peores|peor|menor|worst|menos)\b', q_lower))
        order_kw = "ASC" if is_asc else "DESC"
        m_top = re.search(r'\btop\s+(\d{1,3})\b', q_lower)
        limit = int(m_top.group(1)) if m_top else 100
        month_filter = ""
        if month_range:
            month_filter = f" AND EXTRACT(MONTH FROM {date_expr}) BETWEEN {month_range[0]} AND {month_range[1]}"
        elif last_three:
            now = datetime.datetime.now()
            if int(ejercicio) == now.year:
                end_m = now.month
                start_m = max(1, end_m-2)
            else:
                start_m, end_m = 10, 12
            month_filter = f" AND EXTRACT(MONTH FROM {date_expr}) BETWEEN {start_m} AND {end_m}"
        quarter_filter = f" AND EXTRACT(QUARTER FROM {date_expr}) = {quarter}" if quarter and not month_filter else ""
        year_filter = ""
        if needs_join and ej_hdr:
            year_filter = f' AND H."{ej_hdr}" = {target_year}'
        elif ej_alias:
            year_filter = f' AND {alias}."{ej_alias}" = {target_year}'
        else:
            year_filter = f' AND EXTRACT(YEAR FROM {date_expr}) = {target_year}'
        sql = f"""
            SELECT 
                {label_expr} as label, 
                (SUM({val_expr}) - SUM({cost_expr})) as val, 
                SUM({cost_expr}) as coste, 
                COUNT(DISTINCT {alias}."{count_col}") as ops 
            FROM {table} {alias}
            {join_clause}
            {label_join}
            WHERE {alias}."{company_col}" = {empresa} 
              {year_filter}{month_filter}{quarter_filter}
            GROUP BY {group_by_expr} 
            ORDER BY 2 {order_kw} 
            LIMIT {limit}
        """
        return {
            'key': f'group_{entity_key}',
            'sql': " ".join(sql.split()),
            'type': 'table',
            'chart_type': 'bar',
            'label': f'{metric_type.capitalize()} por {entity_key}',
            'source': 'deterministic_v2',
            'intent_meta': {'metric': metric_type}
        }

    _PARTY_FOLD_FROM = 'áéíóúüñàèìòùäëïöâêîôûç'
    _PARTY_FOLD_TO = 'aeiouunaeiouaeioaeiouc'
    _PARTY_STOP = {
        'a', 'al', 'de', 'del', 'para', 'por', 'y', 'e', 'en', 'el', 'la', 'los', 'las', 'un', 'una',
        'cliente', 'clientes', 'proveedor', 'proveedores', 'mes', 'meses', 'ano', 'ejercicio',
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'setiembre',
        'octubre', 'noviembre', 'diciembre', 'ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'sept', 'oct', 'nov', 'dic',
        'todos', 'todas', 'todo', 'empresa', 'total', 'totales', 'mensual', 'mensuales', 'anual', 'anuales',
        'general', 'resumen', 'evolucion', 'tendencia', 'comparativa', 'albaran', 'albaranes', 'pedido', 'pedidos',
        'neto', 'neta', 'netas', 'bruto', 'bruta', 'brutos', 'ultimo', 'ultima', 'ultimos', 'ultimas',
        'hoy', 'ayer', 'semana', 'semanas', 'trimestre', 'trimestres', 'semestre', 'semestres',
        'grafico', 'informe', 'detalle', 'detallado', 'articulo', 'articulos', 'producto', 'productos',
        'familia', 'familias', 'agente', 'agentes', 'vendedor', 'vendedores', 'comercial', 'comerciales',
        'zona', 'zonas',
    }

    @staticmethod
    def _fold_party(text: str) -> str:
        raw = unicodedata.normalize('NFD', text or '')
        raw = ''.join(ch for ch in raw if unicodedata.category(ch) != 'Mn')
        raw = raw.lower().replace('ñ', 'n')
        raw = re.sub(r'[^a-z0-9]+', ' ', raw)
        return re.sub(r'\s+', ' ', raw).strip()

    @staticmethod
    def _extract_named_party(question: str) -> Optional[Dict[str, str]]:
        q = QueryBuilder._fold_party(question)
        if not q:
            return None
        patterns = (
            (r'(?:^|.*\b)(?:ventas?|facturacion|albaranes?|pedidos?)\s+(?:a|al|de|del|para)\s+(?:el cliente|cliente|los clientes)\s+(.+)$', 'cliente'),
            (r'(?:^|.*\b)(?:compras?|gastos?)\s+(?:a|al|de|del|para)\s+(?:el proveedor|proveedor|los proveedores)\s+(.+)$', 'proveedor'),
            (r'(?:^|.*\b)(?:ventas?|facturacion|albaranes?|pedidos?)\s+(?:a|al|de|del|para)\s+(.+)$', 'cliente'),
            (r'(?:^|.*\b)(?:compras?|gastos?)\s+(?:a|al|de|del|para)\s+(.+)$', 'proveedor'),
            (r'^(?:ventas?|facturacion)\s+(?!por\b)(.+)$', 'cliente'),
            (r'^(?:compras?)\s+(?!por\b)(.+)$', 'proveedor'),
        )
        kind = None
        name = None
        for pattern, party_kind in patterns:
            found = re.search(pattern, q)
            if found:
                kind = party_kind
                name = found.group(1)
                break
        if not name:
            return None
        name = re.sub(r'\b20\d{2}\b', ' ', name)
        name = re.sub(r'\s+', ' ', name).strip()
        tokens = [tok for tok in name.split() if tok not in QueryBuilder._PARTY_STOP]
        tokens = [tok for tok in tokens if len(tok) >= 3 or tok.isdigit()]
        if not tokens:
            return None
        return {'kind': kind, 'name': ' '.join(tokens)}

    @staticmethod
    def _party_reply(text: str, suggestions: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        if suggestions:
            return {
                'reply': {
                    'type': 'ambiguity_alert',
                    'text': text,
                    'answer': text,
                    'suggestions': suggestions,
                }
            }
        return {'reply': {'type': 'text', 'text': text, 'answer': text}}

    @staticmethod
    def _is_catalog_miss(result) -> bool:
        reply = (result or {}).get('reply') or {}
        if reply.get('suggestions'):
            return False
        text = reply.get('text') or ''
        return text.startswith('No encuentro')

    @staticmethod
    def _token_is_code(name: str) -> bool:
        tokens = (name or '').split()
        if len(tokens) != 1:
            return False
        return bool(re.fullmatch(r'[A-Za-z0-9._\-]+', tokens[0]) and re.search(r'\d', tokens[0]))

    @staticmethod
    def _contains_article_code(stock_query: Dict[str, str]) -> bool:
        for token in (stock_query.get('name') or '').split():
            if re.fullmatch(r'[A-Za-z0-9._\-]+', token) and re.search(r'\d', token):
                return True
        return False

    @staticmethod
    def _medida_pedida(question: str) -> Optional[str]:
        """Kilos o unidades pedidas en la frase. El stock sigue por su propia regla."""
        folded = QueryBuilder._fold_party(question or '')
        if not folded or re.search(r'\b(stock|existencias|existencia|inventario)\b', folded):
            return None
        if re.search(r'\b(kilos?|kg|kilogramos?)\b', folded):
            return 'kilos'
        if re.search(r'\b(unidades|unidad|bultos|bulto)\b', folded) and re.search(
            r'\b(vendid|venta|ventas|albaran|factura|compr)\b', folded
        ):
            return 'unidades'
        return None

    @staticmethod
    def _es_ranking(question: str) -> bool:
        """Un ranking pide el mayor o el mejor. «se han vendido» no basta."""
        folded = QueryBuilder._fold_party(question or '')
        if not folded or QueryBuilder._medida_pedida(folded):
            return False
        return bool(re.search(
            r'\b(top|ranking|mejor|mejores|peor|peores|mayor|mayores|popular|populares|famoso|famosos|estrella|estrellas)\b'
            r'|\b(el|la|los|las)\s+mas\b'
            r'|\b(mas|menos)\s+(vendid|consumid|demandad)',
            folded,
        ))

    @staticmethod
    def _handle_cantidad(question: str, empresa, ejercicio, medida: str):
        """Suma las unidades de las líneas. El kilo es el importe neto de la línea dividido entre el precio."""
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return None
        folded = QueryBuilder._fold_party(question or '')
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            target_year = datetime.datetime.now().year
        compras = bool(re.search(r'\b(compra|compras|comprad|proveedor|proveedores)\b', folded))
        tabla = 'datiadb_lineasalbaranproveedor' if compras else 'datiadb_lineasalbarancliente'
        ano = 'ejerciciopedido' if 'pedido' in tabla else 'ejercicioalbaran'
        producto = None
        if re.search(r'\b(cafes|cafe)\b', folded):
            producto = 'café'
            patron = 'cafe'
        else:
            hallado = re.search(r'\b(?:kilos?|kg|kilogramos?|unidades|unidad|bultos|bulto)\s+(?:de|del)\s+([a-z0-9 ]+)', folded)
            if hallado:
                resto = re.split(r'\b(se|han|en|durante|del|ejercicio|ano|vendid|compr)\b', hallado.group(1))[0]
                resto = re.sub(r'[^a-z0-9 ]', '', resto).strip()
                if resto and resto not in ('la', 'el', 'los', 'las'):
                    producto = resto
                    patron = resto
            else:
                patron = None
        pide_producto, pide_cliente = QueryBuilder._pide_corte_cantidad(folded)
        if pide_producto or pide_cliente:
            cortado = QueryBuilder._respuesta_cantidad_cortada(
                empresa_id, target_year, medida, pide_producto, pide_cliente, folded,
            )
            if cortado:
                return cortado
        filtro = ''
        if patron:
            filtro = f" AND A.descripcion ILIKE '%{patron}%'"
        join = ''
        if patron:
            join = ' JOIN datia_articulos A ON A.empresa = L.codigoempresa AND A.articulo = L.codigoarticulo'
        sql = (
            'SELECT COALESCE(SUM(CASE WHEN L.precio <> 0 THEN L.importeneto / L.precio END), 0) AS cantidad '
            f'FROM {tabla} L{join} '
            f'WHERE L.codigoempresa = {empresa_id} AND L.{ano} = {target_year}{filtro}'
        )
        return {
            'key': f'cantidad_{medida}',
            'sql': ' '.join(sql.split()),
            'type': 'cantidad',
            'label': medida,
            'keep_label': True,
            'source': 'deterministic_v2',
            'intent_meta': {
                'metric': 'cantidad',
                'unidad': medida,
                'producto': producto or '',
                'ejercicio': target_year,
                'compras': compras,
            },
        }

    @staticmethod
    def _pide_corte_cantidad(folded: str):
        producto = bool(re.search(r'\b(producto|productos|articulo|articulos)\b', folded or ''))
        cliente = bool(re.search(r'\b(cliente|clientes|a quien|al que|quien)\b', folded or ''))
        return producto, cliente

    @staticmethod
    def _kilos_sql():
        return 'COALESCE(SUM(CASE WHEN L.precio <> 0 THEN L.importeneto / L.precio END), 0)'

    @staticmethod
    def _numero_cantidad(valor):
        return f"{float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    @staticmethod
    def _leer_cantidad(sql, params):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        with connections[alias].cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    @staticmethod
    def _respuesta_cantidad_cortada(empresa, year, medida, pide_producto, pide_cliente, folded):
        """El artículo o el cliente con más kilos, leído en las líneas. No es el total de la empresa."""
        orden = 'ASC' if re.search(r'\b(peor|peores|menos)\b', folded or '') and not re.search(
            r'\b(mas|mayor|mejor)\b', folded or '',
        ) else 'DESC'
        kilos = QueryBuilder._kilos_sql()
        try:
            if pide_producto:
                filas = QueryBuilder._leer_cantidad(
                    f'''
                    SELECT COALESCE(NULLIF(BTRIM(MAX(A.descripcion)), ''), L.codigoarticulo) AS nombre,
                           L.codigoarticulo AS codigo,
                           {kilos} AS kilos
                    FROM datiadb_lineasalbarancliente L
                    LEFT JOIN datia_articulos A
                      ON A.empresa = L.codigoempresa AND A.articulo = L.codigoarticulo
                    WHERE L.codigoempresa = %s AND L.ejercicioalbaran = %s
                    GROUP BY L.codigoarticulo
                    HAVING {kilos} <> 0
                    ORDER BY kilos {orden}
                    LIMIT 1
                    ''',
                    [empresa, year],
                )
            else:
                filas = QueryBuilder._leer_cantidad(
                    f'''
                    SELECT COALESCE(NULLIF(BTRIM(MAX(C.razonsocial)), ''), C.codigocliente) AS nombre,
                           {kilos} AS kilos
                    FROM datiadb_lineasalbarancliente L
                    JOIN datiadb_cabeceraalbarancliente C
                      ON C.codigoempresa = L.codigoempresa
                     AND C.ejercicioalbaran = L.ejercicioalbaran
                     AND C.seriealbaran = L.seriealbaran
                     AND C.numeroalbaran = L.numeroalbaran
                    WHERE L.codigoempresa = %s AND L.ejercicioalbaran = %s
                    GROUP BY C.codigocliente
                    HAVING {kilos} <> 0
                    ORDER BY kilos {orden}
                    LIMIT 8
                    ''',
                    [empresa, year],
                )
        except Exception:
            logger.exception('QueryBuilder: no se pudo leer la cantidad por producto o cliente')
            return None
        if not filas:
            return None
        if pide_producto:
            nombre, codigo, total = filas[0]
            nombre = str(nombre or codigo).strip()
            total = float(total or 0)
            clientes = []
            if pide_cliente and codigo:
                try:
                    clientes = QueryBuilder._leer_cantidad(
                        f'''
                        SELECT COALESCE(NULLIF(BTRIM(MAX(C.razonsocial)), ''), C.codigocliente) AS nombre,
                               {kilos} AS kilos
                        FROM datiadb_lineasalbarancliente L
                        JOIN datiadb_cabeceraalbarancliente C
                          ON C.codigoempresa = L.codigoempresa
                         AND C.ejercicioalbaran = L.ejercicioalbaran
                         AND C.seriealbaran = L.seriealbaran
                         AND C.numeroalbaran = L.numeroalbaran
                        WHERE L.codigoempresa = %s AND L.ejercicioalbaran = %s AND L.codigoarticulo = %s
                        GROUP BY C.codigocliente
                        HAVING {kilos} <> 0
                        ORDER BY kilos {orden}
                        LIMIT 8
                        ''',
                        [empresa, year, codigo],
                    )
                except Exception:
                    logger.exception('QueryBuilder: no se pudo leer el cliente de la cantidad')
                    clientes = []
            texto = (
                f"En {year} el producto con más {medida} es {nombre}, "
                f"con {QueryBuilder._numero_cantidad(total)} {medida}."
            )
            filas_tabla = [[nombre, round(total, 2)]]
            columnas = ['Producto', medida.capitalize()]
            if clientes:
                cliente, kilos_cliente = clientes[0]
                cliente = str(cliente or '').strip()
                texto += (
                    f" El cliente al que más se le vende ese producto es {cliente}, "
                    f"con {QueryBuilder._numero_cantidad(kilos_cliente)} {medida}."
                )
                columnas = ['Cliente', medida.capitalize()]
                filas_tabla = [[str(fila[0] or '').strip(), round(float(fila[1] or 0), 2)] for fila in clientes]
            return {
                'reply': {
                    'type': 'report',
                    'key': 'cantidad_producto_cliente',
                    'text': texto,
                    'answer': texto,
                    'source': 'lineas_albaran',
                    'kpis': [{
                        'label': medida.capitalize(),
                        'value': round(total, 2),
                        'suffix': '',
                        'color': '#34d399',
                    }],
                    'table': {
                        'title': f'{medida.capitalize()} por cliente' if clientes else f'{medida.capitalize()} por producto',
                        'columns': columnas,
                        'rows': filas_tabla,
                    },
                }
            }
        primero = str(filas[0][0] or '').strip()
        total = float(filas[0][1] or 0)
        texto = (
            f"En {year} el cliente al que más se le venden {medida} es {primero}, "
            f"con {QueryBuilder._numero_cantidad(total)} {medida}."
        )
        return {
            'reply': {
                'type': 'report',
                'key': 'cantidad_producto_cliente',
                'text': texto,
                'answer': texto,
                'source': 'lineas_albaran',
                'kpis': [{
                    'label': medida.capitalize(),
                    'value': round(total, 2),
                    'suffix': '',
                    'color': '#34d399',
                }],
                'table': {
                    'title': f'{medida.capitalize()} por cliente',
                    'columns': ['Cliente', medida.capitalize()],
                    'rows': [[str(fila[0] or '').strip(), round(float(fila[1] or 0), 2)] for fila in filas],
                },
            }
        }

    @staticmethod
    def _colloquial_ranking(question: str, empresa, ejercicio):
        """«el café más popular» se responde con el ranking de artículos, sin pasar por el modelo."""
        folded = QueryBuilder._fold_party(question or '')
        if not folded or not QueryBuilder._es_ranking(folded):
            return None
        if re.search(r'\b(cliente|clientes)\b', folded):
            entity = 'cliente'
        elif re.search(r'\b(articulo|articulos|producto|productos|cafe|cafes|referencia|referencias)\b', folded):
            entity = 'articulo'
        elif re.search(r'\b(popular|populares|famoso|famosos|estrella|estrellas|vendido|vendidos|consumido|consumidos|demandado|demandados)\b', folded):
            entity = 'articulo'
        else:
            return None
        return QueryBuilder._handle_ranking(question, empresa, ejercicio, entity)

    @staticmethod
    def _looks_like_ranking(question: str) -> bool:
        return QueryBuilder._es_ranking(question)

    @staticmethod
    def _semantic_clase(question: str) -> Optional[str]:
        if re.search(r'\b(cuenta|cuentas|saldo)\b', question or ''):
            return 'cuenta'
        if re.search(r'\b(stock|existencias|existencia|inventario|articulo|articulos|producto|productos)\b', question or ''):
            return 'articulo'
        if re.search(r'\b(cliente|clientes|ventas|venta)\b', question or ''):
            return 'cliente'
        return None

    @staticmethod
    def _semantic_followup(entidad) -> str:
        identificador = entidad.identificador
        if entidad.clase == 'articulo':
            return f'stock del {identificador}'
        if entidad.clase == 'cuenta':
            return f'saldo de la cuenta {identificador}'
        return f'ventas al cliente {identificador}'

    @staticmethod
    def _semantic_if_entity(question, q_lower, empresa, ejercicio):
        if QueryBuilder._looks_like_ranking(q_lower) or QueryBuilder._is_year_analysis(q_lower):
            return None
        clase = QueryBuilder._semantic_clase(q_lower)
        if not clase:
            return None
        return QueryBuilder._semantic_answer(question, empresa, ejercicio, clase)

    @staticmethod
    def _semantic_answer(question, empresa, ejercicio, clase):
        if empresa in (None, '') or ejercicio in (None, ''):
            return QueryBuilder._party_reply('Elige la empresa y el ejercicio antes de preguntar.')
        from datia.services.significado_service import SignificadoService
        found = SignificadoService.buscar(question, empresa, clase=clase)
        status = found.get('status')
        if status == 'sin_empresa':
            return QueryBuilder._party_reply('Elige la empresa y el ejercicio antes de preguntar.')
        if status == 'preparando':
            return QueryBuilder._party_reply('La búsqueda por significado se está preparando.')
        if status == 'ninguna':
            return QueryBuilder._party_reply('No encuentro esa entidad en el catálogo de esta empresa.')
        if status == 'ambiguo':
            suggestions = [
                {'label': f"{item.texto_indexado} ({item.identificador})", 'query': QueryBuilder._semantic_followup(item)}
                for item in found.get('opciones') or []
            ][:5]
            return QueryBuilder._party_reply('Hay varias entidades parecidas. Elige una.', suggestions)
        entidad = found.get('entidad')
        if not entidad:
            return QueryBuilder._party_reply('No encuentro esa entidad en el catálogo de esta empresa.')
        return QueryBuilder._figure_for_entity(question, empresa, ejercicio, entidad)

    @staticmethod
    def _figure_for_entity(question, empresa, ejercicio, entidad):
        if entidad.clase == 'cliente':
            return QueryBuilder._handle_named_party(
                question, empresa, ejercicio, {'kind': 'cliente', 'name': entidad.identificador}
            )
        if entidad.clase == 'articulo':
            return QueryBuilder._handle_stock_query(
                question, empresa, ejercicio, {'name': entidad.identificador}
            )
        if entidad.clase == 'cuenta':
            return QueryBuilder._handle_cuenta_saldo(empresa, ejercicio, entidad.identificador, entidad.texto_indexado)
        return QueryBuilder._party_reply('No encuentro esa entidad en el catálogo de esta empresa.')

    @staticmethod
    def _handle_cuenta_saldo(empresa, ejercicio, identificador, nombre):
        try:
            empresa_id = int(empresa)
            target_year = int(ejercicio)
        except (TypeError, ValueError):
            return QueryBuilder._party_reply('Elige la empresa y el ejercicio antes de preguntar.')
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        shown = (nombre or identificador).replace('<', '').replace('>', '')
        try:
            with connections[alias].cursor() as cur:
                cur.execute(
                    '''
                    SELECT saldo
                    FROM datia_financial_acumulados
                    WHERE empresa = %s AND ejercicio = %s AND cuenta = %s
                    ORDER BY periodo DESC
                    LIMIT 1
                    ''',
                    [empresa_id, target_year, identificador],
                )
                row = cur.fetchone()
        except Exception:
            logger.exception('QueryBuilder: no se pudo leer el saldo de la cuenta')
            return QueryBuilder._party_reply(
                f'La cuenta {shown} ({identificador}) está en el catálogo, pero no he podido leer el saldo.'
            )
        if not row:
            return QueryBuilder._party_reply(
                f'La cuenta {shown} ({identificador}) está en el catálogo. El saldo no está cargado para el ejercicio {target_year}.'
            )
        return QueryBuilder._party_reply(
            f'Cuenta {shown} ({identificador}): saldo {QueryBuilder._eur_es(row[0])}.'
        )

    @staticmethod
    def _eur_es(value) -> str:
        try:
            amount = f"{float(value):,.2f}"
        except (TypeError, ValueError):
            amount = "0.00"
        return amount.replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'

    @staticmethod
    def _qty_es(value) -> str:
        try:
            amount = f"{float(value):,.2f}"
        except (TypeError, ValueError):
            amount = "0.00"
        return amount.replace(',', 'X').replace('.', ',').replace('X', '.')

    @staticmethod
    def _extract_stock_query(question: str) -> Optional[Dict[str, str]]:
        q = QueryBuilder._fold_party(question)
        stock_word = re.search(r'\b(stock|existencias|existencia|inventario|unidades)\b', q)
        if not stock_word:
            return None
        found = re.search(
            r'\b(?:stock|existencias|existencia|inventario|unidades)\b(?:\s+\w+){0,6}\s+(?:de|del|para)\s+(.+)$',
            q,
        )
        if not found and stock_word.group(1) != 'unidades':
            found = re.search(r'\b(?:stock|existencias|existencia|inventario)\s+([a-z0-9][\w.\-]{1,40})$', q)
        if not found:
            return None
        raw = re.sub(r'\b20\d{2}\b', ' ', found.group(1))
        stop = {
            'articulo', 'articulos', 'producto', 'productos', 'codigo', 'referencia',
            'tengo', 'hay', 'actual', 'disponible', 'unidades', 'unidad', 'almacen',
        }
        tokens = [tok for tok in raw.split() if tok not in stop and tok not in QueryBuilder._PARTY_STOP]
        if not tokens:
            return None
        if stock_word.group(1) == 'unidades' and not any(any(ch.isdigit() for ch in tok) for tok in tokens):
            return None
        return {'name': ' '.join(tokens)}

    @staticmethod
    def _handle_stock_query(question: str, empresa, ejercicio, stock_query: Dict[str, str]) -> Dict[str, Any]:
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return QueryBuilder._party_reply("No puedo buscar el stock sin empresa.")
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            target_year = datetime.datetime.now().year

        name = stock_query['name']
        tokens = name.split()
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        try:
            with connections[alias].cursor() as cur:
                if len(tokens) == 1 and re.fullmatch(r'[A-Za-z0-9._\-]{1,40}', tokens[0]):
                    cur.execute(
                        "SELECT articulo, descripcion FROM datia_articulos WHERE empresa = %s AND lower(articulo) = lower(%s) LIMIT 5",
                        [empresa_id, tokens[0]],
                    )
                else:
                    where = []
                    params: List[Any] = [empresa_id]
                    fold_from = QueryBuilder._PARTY_FOLD_FROM
                    fold_to = QueryBuilder._PARTY_FOLD_TO
                    desc_expr = f"translate(lower(descripcion), '{fold_from}', '{fold_to}')"
                    for tok in tokens:
                        safe = tok.replace('%', '').replace('_', '')
                        if not safe:
                            continue
                        where.append(f"({desc_expr} LIKE %s OR lower(articulo) = %s)")
                        params.extend([f"%{safe}%", safe])
                    if not where:
                        return QueryBuilder._party_reply("Dime el código o el nombre del artículo.")
                    cur.execute(
                        "SELECT articulo, descripcion FROM datia_articulos WHERE empresa = %s AND "
                        + " AND ".join(where)
                        + " LIMIT 8",
                        params,
                    )
                articles = cur.fetchall()
        except Exception:
            logger.exception("QueryBuilder: no se pudo buscar el artículo")
            return QueryBuilder._party_reply("No he podido consultar el catálogo de artículos.")

        if not articles:
            return QueryBuilder._party_reply(f"No encuentro el artículo «{name}» en esta empresa.")
        if len(articles) > 1:
            suggestions = [
                {'label': f"{row[0]} {row[1] or ''}".strip(), 'query': f"stock del {row[0]}"}
                for row in articles
            ]
            return QueryBuilder._party_reply(
                "Hay varios artículos con ese nombre. Indica el código.",
                suggestions,
            )

        code, description = articles[0][0], (articles[0][1] or '').replace('<', '').replace('>', '')
        label = f"{code} {description}".strip()
        try:
            with connections[alias].cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(NULLIF(almacen_name, ''), NULLIF(almacen, ''), 'Sin almacén'),
                           SUM(unidadsaldo),
                           SUM(importesaldo),
                           MAX(periodo)
                    FROM datia_acumulados_stocks
                    WHERE empresa = %s AND ejercicio = %s AND articulo = %s
                      AND periodo = (
                          SELECT MAX(periodo) FROM datia_acumulados_stocks
                          WHERE empresa = %s AND ejercicio = %s AND articulo = %s AND periodo BETWEEN 0 AND 12
                      )
                    GROUP BY 1
                    ORDER BY 2 DESC
                    """,
                    [empresa_id, target_year, code, empresa_id, target_year, code],
                )
                rows = cur.fetchall()
        except Exception:
            logger.exception("QueryBuilder: no se pudo leer el stock")
            return QueryBuilder._party_reply(
                f"El artículo {label} está en el catálogo, pero no he podido leer las existencias."
            )

        if not rows:
            return QueryBuilder._party_reply(
                f"El artículo {label} está en el catálogo. No hay existencias cargadas para el ejercicio {target_year}."
            )

        total_units = sum(float(row[1] or 0) for row in rows)
        total_value = sum(float(row[2] or 0) for row in rows)
        period = rows[0][3]
        lines = [
            f"Stock de {label} en {target_year}, período {period}: {QueryBuilder._qty_es(total_units)} unidades, {QueryBuilder._eur_es(total_value)}."
        ]
        for almacen, units, value, _period in rows:
            lines.append(f"- {almacen}: {QueryBuilder._qty_es(units)} uds, {QueryBuilder._eur_es(value)}")
        return QueryBuilder._party_reply("\n".join(lines))

    @staticmethod
    def _handle_named_party(question: str, empresa, ejercicio, party: Dict[str, str]) -> Dict[str, Any]:
        kind = party['kind']
        tokens = party['name'].split()
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return QueryBuilder._party_reply("No puedo buscar el tercero sin empresa.")
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            target_year = datetime.datetime.now().year

        if kind == 'proveedor':
            master = 'datia_proveedores'
            code_col = 'proveedor'
            year_table = 'metrics_totales_empresa_ejercicio_proveedor'
            month_table = 'metrics_totales_empresa_ejercicio_proveedor_mes'
            verb = 'compras'
            missing = 'proveedor'
            missing_plural = 'proveedores'
            metric = 'purchase'
        else:
            master = 'datia_cliente'
            code_col = 'cliente'
            year_table = 'metrics_totales_empresa_ejercicio_cliente'
            month_table = 'metrics_totales_empresa_ejercicio_cliente_mes'
            verb = 'ventas'
            missing = 'cliente'
            missing_plural = 'clientes'
            metric = 'sales'

        fold_from = QueryBuilder._PARTY_FOLD_FROM
        fold_to = QueryBuilder._PARTY_FOLD_TO
        name_expr = f"translate(lower(nombre), '{fold_from}', '{fold_to}')"
        fiscal_expr = f"translate(lower(COALESCE(nombre_fiscal, '')), '{fold_from}', '{fold_to}')"
        where = []
        params: List[Any] = [empresa_id]
        for tok in tokens:
            safe = tok.replace('%', '').replace('_', '')
            if not safe:
                continue
            where.append(
                f"({name_expr} LIKE %s OR {fiscal_expr} LIKE %s OR lower({code_col}) = %s)"
            )
            params.extend([f"%{safe}%", f"%{safe}%", safe])
        if not where:
            return QueryBuilder._party_reply(f"No encuentro un {missing} con ese nombre.")

        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        sql_master = (
            f'SELECT {code_col}, nombre, COALESCE(nombre_fiscal, \'\') '
            f'FROM {master} WHERE empresa = %s AND ' + ' AND '.join(where) + ' LIMIT 15'
        )
        try:
            with connections[alias].cursor() as cur:
                cur.execute(sql_master, params)
                rows = cur.fetchall()
        except Exception:
            logger.exception("QueryBuilder: no se pudo buscar el tercero")
            return QueryBuilder._party_reply(f"No he podido consultar los {missing_plural} de esta empresa.")

        if not rows:
            shown = party['name']
            return QueryBuilder._party_reply(f"No encuentro un {missing} llamado «{shown}» en esta empresa.")

        codes = [str(row[0]) for row in rows if row[0] is not None]
        amounts: Dict[str, Dict[str, Any]] = {}
        if codes:
            try:
                with connections[alias].cursor() as cur:
                    cur.execute(
                        f'''
                        SELECT {code_col}, importe_neto_total, importe_coste_total, albaranes_count
                        FROM {year_table}
                        WHERE empresa = %s AND ejercicio = %s AND {code_col} = ANY(%s)
                        ''',
                        [empresa_id, target_year, codes],
                    )
                    for code, neto, coste, ops in cur.fetchall():
                        amounts[str(code)] = {
                            'neto': float(neto or 0),
                            'coste': float(coste or 0),
                            'ops': int(ops or 0),
                        }
            except Exception:
                logger.exception("QueryBuilder: no se pudieron leer los totales del tercero")
                amounts = {}

        folded_query = party['name']
        pool = []
        for code, nombre, fiscal in rows:
            code_s = str(code)
            folded_name = QueryBuilder._fold_party(nombre)
            folded_fiscal = QueryBuilder._fold_party(fiscal)
            exact = folded_query in (folded_name, folded_fiscal) or folded_query == code_s.lower()
            figures = amounts.get(code_s) or {'neto': 0.0, 'coste': 0.0, 'ops': 0}
            pool.append({
                'code': code_s,
                'nombre': (nombre or fiscal or code_s).strip(),
                'exact': exact,
                **figures,
            })

        exact_rows = [item for item in pool if item['exact']]
        if exact_rows:
            pool = exact_rows
        with_amount = [item for item in pool if item['neto'] != 0 or item['ops'] != 0]
        chosen = None
        if len(with_amount) == 1:
            chosen = with_amount[0]
        elif len(with_amount) > 1:
            pool = with_amount
        elif len(pool) == 1:
            chosen = pool[0]

        if chosen is None:
            suggestions = []
            for item in pool[:8]:
                label = item['nombre']
                if item['neto'] or item['ops']:
                    label = f"{label} · {QueryBuilder._eur_es(item['neto'])}"
                suggestions.append({
                    'label': label,
                    'query': f"{verb} al {missing} {item['code']}",
                })
            text = f"Hay varios {missing_plural} que encajan con «{party['name']}». Elige uno."
            return QueryBuilder._party_reply(text, suggestions)

        display = chosen['nombre'].replace('<', '').replace('>', '')
        if chosen['neto'] == 0 and chosen['ops'] == 0:
            text = f"{display} no tiene {verb} en {target_year}."
            return QueryBuilder._party_reply(text)

        code_sql = chosen['code']
        if not re.fullmatch(r'[A-Za-z0-9._\-]+', code_sql):
            text = f"{verb.capitalize()} a {display} en {target_year}: {QueryBuilder._eur_es(chosen['neto'])}."
            return QueryBuilder._party_reply(text)

        month_sql = (
            f'SELECT mes AS label, importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops '
            f'FROM {month_table} '
            f'WHERE empresa = {empresa_id} AND ejercicio = {target_year} AND {code_col} = \'{code_sql}\' '
            f'ORDER BY mes'
        )
        has_months = False
        try:
            with connections[alias].cursor() as cur:
                cur.execute(
                    f'SELECT COUNT(*) FROM {month_table} WHERE empresa = %s AND ejercicio = %s AND {code_col} = %s',
                    [empresa_id, target_year, code_sql],
                )
                has_months = int(cur.fetchone()[0] or 0) > 0
        except Exception:
            has_months = False

        if has_months:
            sql = month_sql
            response_type = 'chart'
            chart_type = 'bar'
        else:
            sql = (
                f'SELECT importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops, '
                f'nombre AS label FROM {year_table} '
                f'WHERE empresa = {empresa_id} AND ejercicio = {target_year} AND {code_col} = \'{code_sql}\''
            )
            response_type = 'card'
            chart_type = None

        label = f"{verb.capitalize()} a {display} en {target_year}: {QueryBuilder._eur_es(chosen['neto'])}"
        result = {
            'key': f'named_{kind}',
            'sql': ' '.join(sql.split()),
            'type': response_type,
            'label': label,
            'keep_label': True,
            'source': 'deterministic_v2',
            'intent_meta': {
                'metric': metric,
                'entity': kind,
                'party': display,
                'party_code': code_sql,
                'title': label,
            },
        }
        if chart_type:
            result['chart_type'] = chart_type
        return result

    @staticmethod
    def build_from_nl(question: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Resuelve la pregunta. Si la consulta anterior no tenía importe, la salta y entrena otra."""
        resultado = QueryBuilder._construir_consulta(question, context)
        sql = (resultado or {}).get('sql') or ''
        prohibida = context.get('_sql_descartada') or ''
        if prohibida and sql and QueryBuilder._sql_igual(sql, prohibida):
            logger.info("QueryBuilder: se descarta la consulta que no dio un importe válido")
            resultado = None
        if resultado:
            return resultado
        if context.get('training_enabled'):
            return QueryBuilder._autoentrenar(question, context, prohibida)
        return None

    @staticmethod
    def _sql_igual(izquierda: str, derecha: str) -> bool:
        return ' '.join((izquierda or '').split()).casefold() == ' '.join((derecha or '').split()).casefold()

    @staticmethod
    def _autoentrenar(question: str, context: Dict[str, Any], prohibida: str = ''):
        """Aprende una consulta que pasa la prueba en seco y no es la que acaba de fallar."""
        empresa = context.get('empresa')
        ejercicio = context.get('ejercicio')
        logger.info("QueryBuilder: autoentreno tras un resultado sin importe válido")
        import hashlib
        q_hash = hashlib.md5((question or '').encode('utf-8')).hexdigest()
        if not AutoTrainingLimiter.should_attempt(q_hash):
            return None
        AutoTrainingLimiter.record_attempt(q_hash)
        detector = IntentDetector()
        intent = detector.detect(question, empresa)
        if not intent.get('tables'):
            return None
        generator = SQLVariationGenerator()
        for sql in generator.generate(intent, empresa):
            if prohibida and QueryBuilder._sql_igual(sql, prohibida):
                continue
            if not QueryBuilder.validate_sql_dry_run(sql).get('valid'):
                continue
            try:
                ServiceFactory.get_embedding_service().learn_template(
                    text=question,
                    sql=sql,
                    type='table',
                    label='Generada',
                    empresa=empresa,
                    ejercicio=ejercicio,
                    scope='generated',
                )
            except Exception:
                pass
            return {
                'key': 'auto_gen',
                'sql': sql,
                'type': 'table',
                'label': 'Auto-Generated',
                'source': 'auto_training',
            }
        return None

    @staticmethod
    def _construir_consulta(question: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Main Entry Point. Routes to specific handlers.
        """
        empresa = context.get('empresa')
        ejercicio = context.get('ejercicio')
        training_enabled = context.get('training_enabled', False)
        training_enabled = context.get('training_enabled', False)
        # 0. NORMALIZE TYPOS
        q_lower = QueryBuilder._normalize_tokens(question)
        
        logger.info(f"QueryBuilder v2: Processing '{question}'")

        from datia.services.ai.open_question import OpenQuestion
        abierta = OpenQuestion.plantilla(question, empresa, ejercicio, context.get('limit') or 10)
        if abierta:
            logger.info("QueryBuilder: la pregunta encaja en una plantilla de métricas")
            return abierta

        medida = QueryBuilder._medida_pedida(q_lower)
        if medida:
            cantidad = QueryBuilder._handle_cantidad(q_lower, empresa, ejercicio, medida)
            if cantidad:
                logger.info("QueryBuilder: la pregunta pide %s, no un ranking en euros", medida)
                return cantidad

        colloquial = QueryBuilder._colloquial_ranking(q_lower, empresa, ejercicio)
        if colloquial:
            logger.info("QueryBuilder: ranking en lenguaje llano, sin entrenamiento")
            return colloquial

        learned = QueryBuilder._memory_hit(question, empresa, ejercicio, 0.82, scopes=['learned'])
        if learned:
            logger.info("QueryBuilder: consulta aprendida de esta empresa")
            return learned

        party = QueryBuilder._extract_named_party(q_lower)
        if party:
            logger.info("QueryBuilder: ventas o compras de un tercero concreto")
            party_result = QueryBuilder._handle_named_party(q_lower, empresa, ejercicio, party)
            if party['kind'] != 'cliente' or not QueryBuilder._is_catalog_miss(party_result) or QueryBuilder._token_is_code(party['name']):
                return party_result
            semantic = QueryBuilder._semantic_answer(question, empresa, ejercicio, 'cliente')
            return semantic or party_result

        stock_query = QueryBuilder._extract_stock_query(q_lower)
        if stock_query:
            logger.info("QueryBuilder: stock de un artículo concreto")
            stock_result = QueryBuilder._handle_stock_query(q_lower, empresa, ejercicio, stock_query)
            if QueryBuilder._contains_article_code(stock_query) or not QueryBuilder._is_catalog_miss(stock_result):
                return stock_result
            semantic = QueryBuilder._semantic_answer(question, empresa, ejercicio, 'articulo')
            return semantic or stock_result

        # --- STEP 1: INTENT ROUTING ---
        
        # A. RANKING INTENT
        ranking_triggers = ['top', 'ranking', 'mejores', 'mejor', 'peor', 'best', 'mayores', 'principales']
        sold_rank = bool(re.search(r'\b(mas|menos)\s+vendid', q_lower)) and not QueryBuilder._medida_pedida(q_lower)
        if (any(t in q_lower for t in ranking_triggers) or sold_rank) and not QueryBuilder._medida_pedida(q_lower):
            # Identify Entity
            for entity_key in QueryBuilder.ENTITIES.keys():
                # Check singular and plural
                if entity_key in q_lower or entity_key + 's' in q_lower:
                    logger.info(f"Router: Detected RANKING for {entity_key}")
                    result = QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, entity_key)
                    if result: return result
                    
            # Synonym checks
            if 'producto' in q_lower or 'articulo' in q_lower:
                return QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, 'articulo')
            if 'vendedor' in q_lower or 'comercial' in q_lower:
                return QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, 'agente')
            if 'region' in q_lower:
                return QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, 'zona')
            if sold_rank and 'cliente' not in q_lower and 'proveedor' not in q_lower:
                logger.info("Router: Detected RANKING for articulo (mas vendidos)")
                result = QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, 'articulo')
                if result:
                    return result

        # A.1 RANKING HEURÍSTICO (Clientes que más ...)
        if (('cliente' in q_lower or 'clientes' in q_lower) and 
            ((' mas ' in q_lower) or ('más' in q_lower) or ('mayor' in q_lower) or ('compr' in q_lower))):
            result = QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, 'cliente')
            if result: 
                return result
        
        # A.2 GROUPING HEURÍSTICO (Métrica por Cliente, p.ej. Margen por cliente ...)
        # Hace falta una métrica comercial. La palabra cliente sola no es un ranking de ventas.
        if ('cliente' in q_lower or 'clientes' in q_lower) and QueryBuilder._pide_desglose_comercial(q_lower):
            result = QueryBuilder._handle_grouping(q_lower, empresa, ejercicio, 'cliente')
            if result:
                return result
 
        # B. EVOLUTION/SALES/PURCHASE INTENT
        # Check Purchase first (more specific)
        purchase_triggers = ['compras', 'compra', 'proveedor', 'gastos']
        exclude_entities = ['cliente','clientes','producto','productos','articulo','articulos','familia','familias','agente','agentes','vendedor','vendedores','comercial','comerciales']
        if (
            any(t in q_lower for t in purchase_triggers)
            and 'pedido' not in q_lower
            and not any(x in q_lower for x in exclude_entities)
            and OpenQuestion.clasificar_ranking_proveedor(q_lower) is None
        ):
             logger.info("Router: Detected PURCHASE EVOLUTION")
             return QueryBuilder._handle_evolution(q_lower, empresa, ejercicio, is_purchase=True)
             
        # Check Purchase Orders
        if 'pedido' in q_lower and ('compra' in q_lower or 'proveedor' in q_lower):
             logger.info("Router: Detected PURCHASE ORDERS")
             # Use evolution handler but with is_purchase=True and it handles 'pedido' logic
             return QueryBuilder._handle_evolution(q_lower, empresa, ejercicio, is_purchase=True)

        # Check Sales
        figure = QueryBuilder._handle_company_figure(q_lower, empresa, ejercicio)
        if figure:
            return figure
        sales_triggers = ['ventas', 'pedidos', 'sales', 'evolucion', 'tendencia', 'mensual', 'albaran', 'albaranes']
        if any(t in q_lower for t in sales_triggers):
             logger.info("Router: Detected SALES EVOLUTION")
             return QueryBuilder._handle_evolution(q_lower, empresa, ejercicio, is_purchase=False)

        detector = IntentDetector()
        intent = detector.detect(question, empresa)
        grouping = intent.get('grouping')
        if grouping and QueryBuilder._pide_desglose_comercial(q_lower):
            mapping = {'product': 'articulo', 'client': 'cliente', 'agent': 'agente', 'zone': 'zona', 'family': 'familia'}
            target_entity = mapping.get(grouping)
            if target_entity:
                result = QueryBuilder._handle_grouping(q_lower, empresa, ejercicio, target_entity)
                if result:
                    return result

        if QueryBuilder._is_year_analysis(q_lower):
            logger.info("QueryBuilder: análisis del ejercicio")
            return QueryBuilder._handle_year_analysis(q_lower, empresa, ejercicio)

        semantic = QueryBuilder._semantic_if_entity(question, q_lower, empresa, ejercicio)
        if semantic is not None:
            return semantic

        # --- STEP 2: MEMORY FALLBACK ---
        memory = QueryBuilder._memory_hit(question, empresa, ejercicio, 0.5)
        if memory:
            logger.info("QueryBuilder: respuesta recuperada de la memoria de la empresa")
            return memory

        return None

    @staticmethod
    def _pide_desglose_comercial(question: str) -> bool:
        """Un desglose de ventas exige una métrica o un «por cliente». Deuda y la palabra suelta no bastan."""
        folded = QueryBuilder._fold_party(question)
        from datia.services.ai.open_question import OpenQuestion
        if OpenQuestion.clasificar_deuda(folded):
            return False
        if re.search(r'\bpor\b', folded):
            return True
        hints = (
            'margen', 'rentabil', 'beneficio', 'ganancia', 'venta', 'ventas',
            'importe', 'pedido', 'pedidos', 'coste', 'gasto', 'factura', 'facturacion',
        )
        return any(hint in folded for hint in hints)

    @staticmethod
    def _apply_sql_placeholders(sql, empresa, ejercicio):
        text = sql or ''
        return text.replace('{empresa}', str(empresa)).replace('{ejercicio}', str(ejercicio))

    @staticmethod
    def _is_year_analysis(question: str) -> bool:
        folded = QueryBuilder._fold_party(question)
        if not folded:
            return False
        if re.search(r'\b(top|ranking|mejores|peores|peor|mejor)\b', folded):
            return False
        has_intent = bool(re.search(r'\b(analisis|informe|resumen|balance|situacion)\b', folded))
        has_period = bool(re.search(r'\b(ano|ejercicio|anual)\b', folded)) or bool(re.search(r'\b20\d{2}\b', question or ''))
        return has_intent and has_period

    @staticmethod
    def _handle_year_analysis(question: str, empresa, ejercicio) -> Dict[str, Any]:
        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return QueryBuilder._party_reply("No puedo analizar el ejercicio sin empresa.")
        years = re.findall(r'\b(20\d{2})\b', question or '')
        try:
            target_year = int(years[0]) if years else int(ejercicio)
        except (TypeError, ValueError):
            target_year = datetime.datetime.now().year
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        neto = coste = ops = None
        months = 0
        try:
            with connections[alias].cursor() as cur:
                cur.execute(
                    '''
                    SELECT importe_neto_total, importe_coste_total, albaranes_count
                    FROM metrics_totales_empresa_ejercicio
                    WHERE empresa = %s AND ejercicio = %s
                    ''',
                    [empresa_id, target_year],
                )
                row = cur.fetchone()
                if row:
                    neto, coste, ops = float(row[0] or 0), float(row[1] or 0), int(row[2] or 0)
                cur.execute(
                    '''
                    SELECT COUNT(*) FROM metrics_totales_empresa_ejercicio_mes
                    WHERE empresa = %s AND ejercicio = %s
                    ''',
                    [empresa_id, target_year],
                )
                months = int(cur.fetchone()[0] or 0)
        except Exception:
            logger.exception("QueryBuilder: no se pudieron leer las métricas del ejercicio")
            return QueryBuilder._party_reply(f"No he podido leer las métricas de {target_year}.")
        if neto is None and months == 0:
            return QueryBuilder._party_reply(f"No hay métricas de ventas para {target_year}.")
        label = f"Análisis {target_year}: {QueryBuilder._eur_es(neto or 0)}"
        if months:
            sql = (
                f'SELECT mes AS label, importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops '
                f'FROM metrics_totales_empresa_ejercicio_mes '
                f'WHERE empresa = {empresa_id} AND ejercicio = {target_year} ORDER BY mes'
            )
            return {
                'key': 'year_analysis',
                'sql': sql,
                'type': 'chart',
                'chart_type': 'bar',
                'label': label,
                'keep_label': True,
                'source': 'deterministic_v2',
                'intent_meta': {'metric': 'sales', 'title': label, 'ejercicio': target_year},
            }
        sql = (
            f'SELECT importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops '
            f'FROM metrics_totales_empresa_ejercicio '
            f'WHERE empresa = {empresa_id} AND ejercicio = {target_year}'
        )
        return {
            'key': 'year_analysis',
            'sql': sql,
            'type': 'card',
            'label': label,
            'keep_label': True,
            'source': 'deterministic_v2',
            'intent_meta': {'metric': 'sales', 'title': label, 'ejercicio': target_year},
        }

    @staticmethod
    def _memory_hit(question, empresa, ejercicio, threshold, scopes=None):
        try:
            from datia.models import MetricsEmbeddings
            if scopes == ['learned']:
                if not MetricsEmbeddings.objects.filter(kind='template', metadata__contains={'scope': 'learned'}).exists():
                    return None
            match = ServiceFactory.get_embedding_service().search_template(
                question,
                threshold=threshold,
                empresa=empresa,
                scopes=scopes,
            )
        except Exception:
            logger.info("QueryBuilder: la memoria vectorial no está disponible")
            return None
        if not match or not match.get('sql'):
            return None
        plan = match.get('plan')
        compilado = None
        if isinstance(plan, dict):
            from datia.services.ai.semantic_plan import SemanticPlan
            compilado = SemanticPlan.compilar(plan, empresa, ejercicio, SemanticPlan.dialecto_actual())
        sql_text = compilado or QueryBuilder._apply_sql_placeholders(match.get('sql') or '', empresa, ejercicio)
        folded = QueryBuilder._fold_party(question)
        asks_count = bool(re.search(r'\b(contar|cuantos|cuantas|numero de|cantidad de)\b', folded))
        is_count_only = bool(re.search(r'\bcount\s*\(', sql_text, re.I)) and not re.search(r'\b(sum|avg|min|max)\s*\(', sql_text, re.I)
        if is_count_only and not asks_count:
            logger.info("QueryBuilder: se descarta un entreno que solo cuenta registros")
            return None
        return {
            'key': match.get('key'),
            'sql': sql_text,
            'plan': plan if isinstance(plan, dict) else None,
            'type': match.get('type') or 'table',
            'label': match.get('label') or 'Memoria',
            'source': 'ai_memory',
        }

    @staticmethod
    def validate_sql_dry_run(sql: str) -> Dict[str, Any]:
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"EXPLAIN {sql}")
                return {'valid': True}
        except Exception as e:
            return {'valid': False, 'error': str(e)}
