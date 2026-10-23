import re
from typing import List, Dict

class SQLGuard:
    """
    Validador de alcance para consultas SQL.
    Restringe estrictamente a tablas de Postgres del dominio Pedidos y Albaranes (datiadb_*)
    y permite lectura sobre tablas de métricas (metrics_*).
    """
    # Esquemas prohibidos
    _FORBIDDEN_SCHEMAS = {'information_schema', 'pg_catalog'}

    # Lista explícita de tablas permitidas (nombres en minúscula)
    _EXPLICIT_ALLOW = {
        'datiadb_cabecerapedidocliente',
        'datiadb_lineaspedidocliente',
        'datiadb_cabecerapedidoproveedor',
        'datiadb_lineaspedidoproveedor',
        'datiadb_cabeceraalbarancliente',
        'datiadb_lineasalbarancliente',
        'datiadb_cabeceraalbaranproveedor',
        'datiadb_lineasalbaranproveedor',
        # Posibles nombres estandarizados
        'datiadb_order_headers',
        'datiadb_order_lines',
        'datiadb_order_status',
        'datiadb_order_history',
        'datiadb_delivery_notes',
        'datiadb_delivery_lines',
        'datiadb_delivery_status',
        # Dominio maestro (Postgres)
        'datia_acumulados_stocks',
        'datia_almacenes',
        'datia_articulos',
        'datia_cliente',
        'datia_comisionistas',
        'datia_empresa',
        'datia_familias',
        'datia_proveedores',
    }

    @staticmethod
    def _normalize_table(token: str) -> str:
        """
        Normaliza el nombre de tabla a minúsculas, sin comillas ni esquema.
        """
        if not token:
            return ''
        t = token.strip().strip('(),;')
        t = t.split()[0]
        if '.' in t:
            t = t.split('.')[-1]
        t = t.strip().strip('"').strip("'").strip().strip('(),;')
        return t.lower()

    @staticmethod
    def _extract_tables(sql: str) -> List[str]:
        """
        Extrae nombres de tablas desde cláusulas FROM y JOIN.
        """
        if not sql:
            return []
        s = re.sub(r'\s+', ' ', sql)
        s = re.sub(r'EXTRACT\s*\(\s*[^)]*?\)', 'EXTRACT()', s, flags=re.IGNORECASE)
        # Capturar tokens tras FROM y JOIN
        tables = []
        for m in re.finditer(r'\bFROM\s+([^\s,;]+)', s, flags=re.IGNORECASE):
            tables.append(SQLGuard._normalize_table(m.group(1)))
        for m in re.finditer(r'\bJOIN\s+([^\s,;]+)', s, flags=re.IGNORECASE):
            tables.append(SQLGuard._normalize_table(m.group(1)))
        # Unicos conservando orden
        seen = set()
        out = []
        for t in tables:
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    @staticmethod
    def _is_allowed_table(table: str) -> bool:
        """
        Regla de autorización:
        - Permite lectura sobre metrics_*
        - Para datiadb_*: debe contener 'pedido' o 'albaran' (o estar en lista explícita)
        """
        if not table:
            return False
        tl = table.lower()
        # Bloquear si la cadena contiene esquemas prohibidos
        if any(s in tl for s in SQLGuard._FORBIDDEN_SCHEMAS):
            return False
        if tl.startswith('metrics_'):
            return True
        if tl.startswith('datia_financial_'):
            return True
        if tl.startswith('datia_banking_'):
            return True
        if tl in SQLGuard._EXPLICIT_ALLOW:
            return True
        if not tl.startswith('datiadb_'):
            return False
        # Palabras clave de dominio
        domain_hits = ('pedido' in tl) or ('pedidocliente' in tl) or ('pedidoproveedor' in tl) \
                      or ('albaran' in tl) or ('albarancliente' in tl) or ('albaranproveedor' in tl) \
                      or ('delivery' in tl) or ('order' in tl)
        if domain_hits:
            return True
        return tl in SQLGuard._tablas_mapeadas()

    @staticmethod
    def _tablas_mapeadas():
        """Nombres locales de las fichas activas. Una tabla mapeada se puede leer."""
        try:
            from datia.models.semantic import DataSource
            nombres = set()
            for origen in DataSource.objects.filter(is_active=True):
                local = origen.get_local_table_name()
                if local:
                    nombres.add(local.lower())
            return nombres
        except Exception:
            return set()

    @staticmethod
    def check_sql(sql: str) -> Dict[str, List[str] | bool]:
        """
        Devuelve {'allowed': bool, 'blocked': [tablas_no_permitidas]}
        """
        if not sql:
            return {'allowed': True, 'blocked': []}
        s = re.sub(r'\s+', ' ', sql)
        if re.search(r'\b(INSERT|UPDATE|DELETE|TRUNCATE|ALTER|DROP|CREATE|GRANT|REVOKE)\b', s, flags=re.IGNORECASE):
            return {'allowed': False, 'blocked': ['<write_operation>']}
        tables = SQLGuard._extract_tables(sql)
        blocked = []
        for t in tables:
            # Si viene con esquema explícito prohibido
            if t.startswith(tuple(SQLGuard._FORBIDDEN_SCHEMAS)):
                blocked.append(t)
                continue
            if not SQLGuard._is_allowed_table(t):
                blocked.append(t)
        return {'allowed': len(blocked) == 0, 'blocked': blocked}

    @staticmethod
    def ensure_allowed(sql: str):
        """
        Lanza PermissionError si el SQL usa tablas fuera del dominio permitido.
        """
        res = SQLGuard.check_sql(sql)
        if not res['allowed']:
            details = ', '.join(res['blocked'])
            raise PermissionError(f'Acceso SQL no permitido a tablas fuera de Pedidos/Albaranes/Métricas: {details}')

