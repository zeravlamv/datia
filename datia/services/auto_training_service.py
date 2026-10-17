
import logging
import decimal
import json
from types import SimpleNamespace
from django.db import connections, transaction
from datia.models import DataSource, DataField
from datia.services.etl_service import ETLService

logger = logging.getLogger('datia')

class AutoTrainingService:
    """
    Service responsible for 'Auto Training' (Data Synchronization).
    It migrates data from remote MSSQL to local Postgres 'datia_{table}'
    based on the semantic definition (DataFields).
    """

    def get_postgres_table_name(self, datasource: DataSource) -> str:
        """
        Generates a safe local table name.
        Now delegates to DataSource model logic for consistency.
        """
        return datasource.get_local_table_name()

    def sync_datasource_generator(self, datasource_id: int, empresa_code: str, ejercicio_year: int):
        """
        Generator to sync a specific Datasource for a given Company/Year.
        Yields progress updates.
        """
        try:
            datasource = DataSource.objects.get(pk=datasource_id)
            # 1. Fetch Configuration (DataFields + Campos Estándar)
            fields_qs = DataField.objects.filter(source=datasource, is_active=True)
            if not fields_qs.exists():
                # Permitimos continuar: completaremos con StandardFields si existen
                fields_qs = DataField.objects.filter(source=datasource)

            etl = ETLService()
            conn = etl.get_connection()
            cursor_mssql = conn.cursor()

            # Cargar columnas reales de la tabla origen en MSSQL
            try:
                cursor_mssql.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
                    (datasource.source_table,),
                )
                available_cols = [str(r[0]) for r in cursor_mssql.fetchall()]
            except Exception:
                available_cols = []

            # Cargar Campos Estándar globales
            try:
                from datia.models.semantic import StandardField  # type: ignore

                std_list = list(StandardField.objects.all())
                std_by_name = {str(s.name): s for s in std_list}
            except Exception:
                std_by_name = {}

            # Completar campos con todos los StandardFields presentes en MSSQL pero no definidos aún
            existing_field_names = {str(f.field_name) for f in fields_qs}
            extra_fields = []
            for col in available_cols:
                if col in existing_field_names:
                    continue
                std = std_by_name.get(col)
                if not std:
                    continue
                dt = "text"
                role = (std.semantic_role or "").upper()
                name_lower = col.lower()
                if role == "METRIC" or name_lower in (
                    "importe",
                    "importeneto",
                    "importecoste",
                    "cantidad",
                    "unidades",
                    "precio",
                    "preciounitario",
                    "coste",
                ):
                    dt = "number"
                elif role == "DATE" or name_lower.startswith("fecha"):
                    dt = "date"
                elif role in ("PK", "FK"):
                    dt = "int"

                extra_fields.append(
                    SimpleNamespace(
                        field_name=col,
                        business_name=std.business_name or col,
                        data_type=dt,
                    )
                )

            fields = list(fields_qs) + extra_fields
            if not fields:
                yield self._progress("Error", 0, f"No fields available for {datasource.name}")
                conn.close()
                return

            table_name = self.get_postgres_table_name(datasource)

            yield self._progress("Setup", 5, f"Configuring local table {table_name}...")
            
            # PATTERN IMPLEMENTATION: Sync for the Company and ALL Exercises
            # 1. Fetch available exercises from MSSQL (assuming standard Ejercicio table or column)
            yield self._progress("Setup", 5, "Fetching available exercises...")
            
            years_to_sync = []
            
            # Try to get years from the source table itself if it has 'Ejercicio' column?
            # Or use a generic query if we know the 'Ejercicios' table?
            # Usually we query distinct 'Ejercicio' from the table we are training.
            
            col_ejercicio = next((f.field_name for f in fields if 'ejercicio' in f.field_name.lower() or 'year' in f.field_name.lower()), 'Ejercicio')
            col_empresa = next((f.field_name for f in fields if 'empresa' in f.field_name.lower()), 'CodigoEmpresa')

            try:
                # Query distinct years for this company in this table
                sql_years = f"SELECT DISTINCT {col_ejercicio} FROM {datasource.source_table} WHERE {col_empresa} = ?"
                try:
                    empresa_id = int(str(empresa_code).strip())
                except:
                    empresa_id = 0
                cursor_mssql.execute(sql_years, (empresa_id,))
                years_rows = cursor_mssql.fetchall()
                years_to_sync = [row[0] for row in years_rows if row[0]]
                years_to_sync.sort()
            except Exception as e:
                # Fallback if query fails (maybe no Ejercicio column?)
                # If no Ejercicio column, we just sync everything once?
                years_to_sync = [ejercicio_year] # Just try the current requested one as fallback or None
                logger.warning(f"Could not fetch years: {e}")

            # 2. Loop through each Year
            total_years = len(years_to_sync)
            current_year_idx = 0
            
            # We recreate the table ONCE at the start (drop and create)
            # Then we append data for each year.
            
            # 3. Create/Update Local Table Schema (Once)
            # Fetch types first (using just one year or top 1)
            mssql_columns = [f.field_name for f in fields]
            params_types = [datasource.source_table] + mssql_columns
            placeholders = ", ".join(["?"] * len(mssql_columns))
            sql_types = f"""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = ? AND COLUMN_NAME IN ({placeholders})
            """
            
            mssql_type_map = {}
            try:
                cursor_mssql.execute(sql_types, params_types)
                type_rows = cursor_mssql.fetchall()
                mssql_type_map = {row[0]: row[1] for row in type_rows}
            except Exception as e:
                pass
                
            self._ensure_local_table(table_name, fields, mssql_type_map)
            
            # 4. Data Import Loop
            joined_cols = ", ".join([f"[{col}]" for col in mssql_columns])
            sql_select = f"SELECT {joined_cols} FROM {datasource.source_table} WHERE {col_empresa} = ? AND {col_ejercicio} = ?"
            
            # Usar nombres originales de columnas (MSSQL) para coincidir con el esquema creado
            pg_cols = [f.field_name for f in fields]
            pg_cols_str = ", ".join([f'"{c}"' for c in pg_cols])
            placeholders_pg = ", ".join(["%s"] * len(pg_cols))
            insert_sql = f'INSERT INTO "{table_name}" ({pg_cols_str}) VALUES ({placeholders_pg})'

            with connections['analytics'].cursor() as pg_cursor:
                for year in years_to_sync:
                    current_year_idx += 1
                    yield self._progress("Syncing", int((current_year_idx/total_years)*20), f"Syncing Year {year} ({current_year_idx}/{total_years})...")
                    
                    try:
                        try:
                            empresa_id = int(str(empresa_code).strip())
                        except:
                            empresa_id = 0
                        self._clean_local_data(table_name, col_empresa, col_ejercicio, empresa_id, year)
                        cursor_mssql.execute(sql_select, (empresa_id, year))
                    except Exception as e:
                        logger.error(f"Error querying MSSQL year {year}: {e}")
                        continue

                    insert_batch = []
                    batch_size = 5000
                    
                    while True:
                        rows = cursor_mssql.fetchmany(batch_size)
                        if not rows:
                            break
                        
                        for row in rows:
                            cleaned_row = []
                            for val in row:
                                if isinstance(val, decimal.Decimal):
                                    cleaned_row.append(float(val))
                                else:
                                    cleaned_row.append(val)
                            insert_batch.append(tuple(cleaned_row))
                            
                        pg_cursor.executemany(insert_sql, insert_batch)
                        insert_batch = []
            
            conn.close()
            yield self._progress("Done", 100, f"Training complete. Synced {total_years} years.")

        except Exception as e:
            logger.error(f"Auto Training Error: {e}")
            yield self._progress("Error", 0, f"Critical Error: {str(e)}")


    def _ensure_local_table(self, table_name: str, fields, mssql_type_map: dict = None):
        """
        Creates or updates the table schema in Postgres.
        Uses ALTER TABLE for existing tables to preserve data.
        """
        if mssql_type_map is None:
            mssql_type_map = {}
            
        def map_mssql_to_pg(mssql_type):
            mssql_type = mssql_type.lower()
            if mssql_type in ['nvarchar', 'varchar', 'char', 'nchar', 'text', 'ntext']:
                return 'TEXT'
            if mssql_type in ['int', 'smallint', 'tinyint', 'bigint']:
                return 'INTEGER' # BigInt if needed, but Integer covers most
            if mssql_type == 'bigint':
                return 'BIGINT'
            if mssql_type in ['decimal', 'numeric', 'money', 'smallmoney']:
                return 'DECIMAL'
            if mssql_type in ['float', 'real']:
                return 'FLOAT'
            if mssql_type in ['date']:
                return 'DATE'
            if mssql_type in ['datetime', 'datetime2', 'smalldatetime']:
                return 'TIMESTAMP'
            if mssql_type in ['bit']:
                return 'BOOLEAN'
            return 'TEXT' # Default fallback

        with connections['analytics'].cursor() as cursor:
            # Check if table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, [table_name])
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                # CREATE NEW TABLE
                cols_def = []
                for f in fields:
                    # USE ORIGINAL FIELD NAME from MSSQL (not business_name)
                    col_name = f.field_name
                    mssql_type = mssql_type_map.get(f.field_name)
                    
                    if mssql_type:
                        pg_type = map_mssql_to_pg(mssql_type)
                    else:
                        fallback_map = {
                            'text': 'TEXT',
                            'number': 'NUMERIC',
                            'date': 'DATE',
                            'boolean': 'BOOLEAN'
                        }
                        pg_type = fallback_map.get(f.data_type, 'TEXT')
                    
                    cols_def.append(f'"{col_name}" {pg_type}')
                    
                create_sql = f'CREATE TABLE "{table_name}" ({", ".join(cols_def)});'
                cursor.execute(create_sql)
                logger.info(f"Created table {table_name} with {len(fields)} columns")
            else:
                # TABLE EXISTS - SCHEMA EVOLUTION
                # Get existing columns
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                """, [table_name])
                existing_cols = {row[0] for row in cursor.fetchall()}
                
                # Prepare expected columns (USE ORIGINAL FIELD NAMES)
                expected_cols = {}
                for f in fields:
                    col_name = f.field_name  # FIXED: Use original name
                    mssql_type = mssql_type_map.get(f.field_name)
                    
                    if mssql_type:
                        pg_type = map_mssql_to_pg(mssql_type)
                    else:
                        fallback_map = {
                            'text': 'TEXT',
                            'number': 'NUMERIC',
                            'date': 'DATE',
                            'boolean': 'BOOLEAN'
                        }
                        pg_type = fallback_map.get(f.data_type, 'TEXT')
                    
                    expected_cols[col_name] = pg_type
                
                # ADD missing columns
                for col_name, pg_type in expected_cols.items():
                    if col_name not in existing_cols:
                        logger.info(f"Schema Evolution: Adding column {col_name} to {table_name}")
                        try:
                            cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {pg_type}')
                        except Exception as e:
                            logger.error(f"Failed to add column {col_name}: {e}")
                
                # DROP removed columns (if a field was unmarked/removed)
                for exist_col in existing_cols:
                    if exist_col not in expected_cols:
                        logger.info(f"Schema Evolution: Dropping column {exist_col} from {table_name}")
                        try:
                            cursor.execute(f'ALTER TABLE "{table_name}" DROP COLUMN "{exist_col}"')
                        except Exception as e:
                            logger.error(f"Failed to drop column {exist_col}: {e}")


    def _clean_local_data(self, table_name: str, col_empresa: str, col_ejercicio: str, empresa: int, ejercicio: int):
        try:
            with connections['analytics'].cursor() as cursor:
                cursor.execute(f'DELETE FROM "{table_name}" WHERE "{col_empresa}" = %s AND "{col_ejercicio}" = %s', [empresa, ejercicio])
        except Exception:
            return

    def _progress(self, step, percent, msg):
        return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\n\n"
