from django.db import connection, connections
from datia.models.semantic import DataSource, DataField

class DatiaSchema:
    """
    Strict Schema Provider for Datia AI.
    Only exposes tables starting with 'DatiaDB_' to the QueryBuilder.
    Supports both PostgreSQL (Production) and SQLite (Development).
    """

    @staticmethod
    def get_authorized_schema_string(empresa: int):
        """
        Returns a DDL-like string describing ONLY the datiadb_* tables
        found in the database.
        """
        schema_desc = []
        
        # FIX: Use 'analytics' DB for data introspection (Postgres), fallback to default
        db_alias = 'analytics' if 'analytics' in connections else 'default'
        conn = connections[db_alias]

        with conn.cursor() as cursor:
            target_tables = []
            
            
            # --- STRATEGY: SQLite vs PostgreSQL ---
            if conn.vendor == 'sqlite':
                # SQLite Introspection
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'datiadb_%'")
                target_tables = [row[0] for row in cursor.fetchall()]
                
                if not target_tables:
                     # Try case-insensitive manually if no strict match
                     cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                     all_t = [row[0] for row in cursor.fetchall()]
                     target_tables = [t for t in all_t if t.lower().startswith('datiadb_')]

                # Build Definitions
                for table in target_tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    # PRAGMA returns: (cid, name, type, notnull, dflt_value, pk)
                    cols = cursor.fetchall()
                    col_defs = [f"{col[1]} ({col[2]})" for col in cols]
                    schema_desc.append(f"TABLE {table} (\n  {', '.join(col_defs)}\n);")

            else:
                # PostgreSQL / Standard SQL Introspection
                # 1. Get Tables
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                all_tables = [row[0] for row in cursor.fetchall()]

                # 2. Filter Strict (Case Insensitive startswith) + Dominio Pedidos/Albaranes
                explicit_allow = {
                    'datiadb_cabecerapedidocliente',
                    'datiadb_lineaspedidocliente',
                    'datiadb_cabecerapedidoproveedor',
                    'datiadb_lineaspedidoproveedor',
                    'datiadb_cabeceraalbarancliente',
                    'datiadb_lineasalbarancliente',
                    'datiadb_cabeceraalbaranproveedor',
                    'datiadb_lineasalbaranproveedor',
                    'datiadb_order_headers',
                    'datiadb_order_lines',
                    'datiadb_order_status',
                    'datiadb_order_history',
                    'datiadb_delivery_notes',
                    'datiadb_delivery_lines',
                    'datiadb_delivery_status',
                }
                def _is_allowed(t: str) -> bool:
                    tl = (t or '').lower()
                    if not tl.startswith('datiadb_'):
                        return False
                    if tl in explicit_allow:
                        return True
                    return ('pedido' in tl) or ('albaran' in tl) or ('delivery' in tl) or ('order' in tl)
                target_tables = [t for t in all_tables if _is_allowed(t)]
                
                # 3. Build Definitions with Semantic Metadata
                for table in target_tables:
                    # Get column definitions
                    cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
                    cols = cursor.fetchall()
                    
                    ds = DataSource.objects.filter(is_active=True).extra(
                        where=["source_table = %s OR 'datiadb_' || LOWER(source_table) = %s"],
                        params=[table, table.lower()]
                    ).first()
                    
                    table_comment = f" -- {ds.description}" if ds and ds.description else ""
                    schema_desc.append(f"TABLE {table} ({table_comment}")
                    
                    for col in cols:
                        col_name = col[0]
                        data_type = col[1]
                        
                        # Find field metadata
                        field_desc = ""
                        if ds:
                            df = DataField.objects.filter(source=ds).extra(
                                where=["LOWER(REPLACE(business_name, ' ', '_')) = %s OR field_name = %s"],
                                params=[col_name, col_name]
                            ).first()
                            if df and df.description:
                                field_desc = f" -- {df.description}"
                            elif df and df.business_name:
                                field_desc = f" -- {df.business_name}"

                        schema_desc.append(f"  {col_name} ({data_type}),{field_desc}")
                    
                    schema_desc.append(");")

        if not schema_desc:
            return "No authorized tables found (Tables must start with 'datiadb_').", []

        return "\n\n".join(schema_desc), target_tables

    @staticmethod
    def is_table_authorized(table_name: str) -> bool:
        """
        Validates if a table name is ALLOWED.
        """
        return table_name.lower().startswith('datiadb_')
