import re
import random
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from django.db import connection
from datia.models import DataSource, DataField, MetricsEmbeddings, DataRelation
from datia.factories import ServiceFactory
import itertools
import logging
logger = logging.getLogger(__name__)

class SyntheticSQLGenerator:
    """
    Generates deterministic, syntactically valid SQL queries based on table schema.
    Validates queries against the database using EXPLAIN.
    """

    def __init__(self):
        pass

    def _extract_context_concepts(self, text: Optional[str]) -> str:
        """
        Extracts concepts marked with ** from table_context.
        Example: "Datos de **Pedidos, ordenes de venta**..." -> "(Pedidos, ordenes de venta)"
        """
        if not text:
            return ""
            
        matches = re.findall(r'\*\*(.*?)\*\*', text)
        if matches:
            # Join all matches found
            concepts = ", ".join(matches)
            return f"({concepts})"
        return ""

    def generate_batch(self, datasource: DataSource, count: int = 150) -> List[Dict]:
        """
        Generates BI-focused SQL queries based on dimensions and metrics.
        Strictly follows: Combinations of Dimensions + Mandatory Company Filter.
        Includes Temporal Patterns (Months, Recent).
        """
        
        valid_queries = []
        
        # [FIX] Handle Virtual Tables (Direct Query to MSSQL)
        if datasource.is_virtual:
             table_name = datasource.source_table
        else:
             table_name = datasource.get_local_table_name()
             
        if not table_name:
             print(f"Skipping {datasource.name}: No table name found.")
             return []

        # [OPTIMIZATION] Reuse MSSQL connection for virtual tables
        mssql_conn = None
        if datasource.is_virtual:
             from datia.services.etl_service import ETLService
             try:
                 mssql_conn = ETLService().get_connection()
             except Exception as e:
                 print(f"Warning: Could not connect to MSSQL for validation: {e}")

        # 1. Identify Roles
        dimensions = list(datasource.fields.filter(usage_type='dimension', is_active=True))
        metrics = list(datasource.fields.filter(usage_type='metric', is_active=True))

        # [IMPROVEMENT] Auto-detect metrics if none defined explicitly
        if not metrics:
            print(f"[{datasource.name}] No metrics defined. Attempting auto-detection by name...")
            keywords = ['importe', 'precio', 'cantidad', 'total', 'saldo', 'coste', 'margen', 'valor', 'amount', 'price', 'qty', 'unidades', 'iva', 'base', 'debe', 'haber', 'presu']
            candidates = datasource.fields.filter(is_active=True).exclude(usage_type='dimension')
            
            for f in candidates:
                # Check Type
                dtype = f.data_type.lower()
                is_numeric = any(t in dtype for t in ['int', 'decimal', 'numeric', 'float', 'money', 'double', 'real'])
                
                # Check Name
                name_match = any(k in f.field_name.lower() or k in f.business_name.lower() for k in keywords)
                
                if is_numeric and name_match:
                    print(f" -> Auto-detected metric: {f.field_name}")
                    metrics.append(f)

        
        # Identify Date Fields for Temporal Patterns
        # Check data_type and also business_name hints
        date_fields = []
        for f in datasource.fields.filter(is_active=True):
            dtype = f.data_type.lower()
            if dtype in ['date', 'datetime', 'timestamp', 'datetime2', 'smalldatetime']:
                date_fields.append(f)
            elif 'fecha' in f.field_name.lower() or 'date' in f.field_name.lower():
                # Fallback by name if type is text/varchar but semantically is a date
                date_fields.append(f)

        # 2. Find mandatory 'CodigoEmpresa' field
        company_field = None
        for f in datasource.fields.filter(is_active=True):
            if 'empresa' in f.field_name.lower() or 'empresa' in f.business_name.lower():
                company_field = f
                break
        
        # If no explicit Company field found, try to find one used as key or dim without specific name, 
        # but the user said it IS there. We will try to find it. 
        # If absolutely not found, we might skip the filter or warn, but for now let's assume valid mapping.
        
        generated_sqls = set()

        # [NF-037] Extract Context Concepts
        context_suffix = self._extract_context_concepts(datasource.table_context)

        # --- PHASE 1: TEMPORAL PATTERNS (Priority) ---
        # Generate questions like "Pedidos de agosto", "Últimos pedidos"
        if date_fields:
            # The first date column in the mapping may be absent from the local copy.
            # Keep the first one whose SQL validates.
            months = {
                1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
                7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
            }
            primary_date = None
            for candidate in date_fields:
                probe = self._build_temporal_month_query(
                    table_name, candidate, 1, 'enero', None, company_field,
                    business_name=datasource.name,
                    context_suffix=context_suffix,
                    is_virtual=datasource.is_virtual,
                )
                if probe and self._validate_sql(probe['sql'], datasource, db_connection=mssql_conn):
                    primary_date = candidate
                    break
            if primary_date is None:
                date_fields = []
            else:
              for m_num, m_name in months.items():
                if len(valid_queries) >= count: break
                
                # [FIX ISS-036] Always generate COUNT (target=None) + First Metric
                # This ensures "Pedidos de agosto" (Count) exists even if we have metrics
                targets = [None] 
                if metrics:
                    targets.append(metrics[0])
                
                for target in targets:
                    if len(valid_queries) >= count: break

                    q_data = self._build_temporal_month_query(
                        table_name, primary_date, m_num, m_name, target, company_field, 
                        business_name=datasource.name, # Pass business name
                        context_suffix=context_suffix, # [NF-037]
                        is_virtual=datasource.is_virtual
                    )
                    
                    if q_data and q_data['sql'] not in generated_sqls:
                        if self._validate_sql(q_data['sql'], datasource, db_connection=mssql_conn):
                            valid_queries.append(q_data)
                            generated_sqls.add(q_data['sql'])

            # B. Recency Queries ("Últimos 10...")
            if primary_date is not None and len(valid_queries) < count:
                q_data = self._build_temporal_recency_query(
                    table_name, primary_date, company_field, limit=10, 
                    business_name=datasource.name, # Pass business name
                    context_suffix=context_suffix, # [NF-037]
                    is_virtual=datasource.is_virtual
                )
                if q_data and q_data['sql'] not in generated_sqls:
                     if self._validate_sql(q_data['sql'], datasource, db_connection=mssql_conn):
                        valid_queries.append(q_data)
                        generated_sqls.add(q_data['sql'])

        # --- PHASE 2: RELATIONAL PATTERNS (JOINs) ---
        # Generate queries that cross tables using defined DataRelation
        # Moved BEFORE combinations to ensure we generate relational questions even if limit is reached
        relations = DataRelation.objects.filter(source=datasource)
        
        for rel in relations:
            if len(valid_queries) >= count:
                break
                
            target_table = rel.target
            
            # [FIX] Ensure both tables are in the same storage (both local or both virtual)
            if datasource.is_virtual != target_table.is_virtual:
                continue
            
            # Identify Dimensions in Target Table
            target_dims = list(target_table.fields.filter(usage_type='dimension', is_active=True))

            if not target_dims:
                continue

            for t_dim in target_dims:
                if len(valid_queries) >= count: break
                
                target_metric = metrics[0] if metrics else None
                
                q_data = self._build_relational_query(datasource, rel, t_dim, target_metric, company_field)
                
                if q_data and q_data['sql'] not in generated_sqls:
                    if self._validate_sql(q_data['sql'], datasource, db_connection=mssql_conn):
                        valid_queries.append(q_data)
                        generated_sqls.add(q_data['sql'])

        # --- PHASE 3: STRUCTURAL COMBINATIONS ---
        
        # 3. Generating Combinations
        # We need to generate enough queries to reach 'count', but prioritized by dimensionality.
        # User said: "Solo se han de realizar tantas consultas como combinaciones posible"
        # This implies we should iterate ALL combinations.
        
        if not dimensions:
             # Fallback if no dimensions defined
             if not valid_queries: # If we didn't generate temporal ones either
                 return self._fallback_generation(datasource, table_name, count)
             return valid_queries

        # Generate all combinations of dimensions (from 1 up to len(dimensions))
        all_combinations = []
        for r in range(1, len(dimensions) + 1):
            combos = list(itertools.combinations(dimensions, r))
            all_combinations.extend(combos)
        
        for dims in all_combinations:
            if len(valid_queries) >= count:
                break
                
            # For each dimension set, pick a Metric (or iterate metrics if we need more volume)
            # Let's try to use all metrics for each dimension set if possible/needed
            target_metrics = metrics if metrics else [None] # Handle count(*) if no metrics
            
            for metric in target_metrics:
                if len(valid_queries) >= count:
                    break
                
                # Reduce aggregations to just SUM/AVG/MAX to avoid useless counts
                # unless we have few combos
                aggregations = ['SUM'] if len(all_combinations) > 10 else ['SUM', 'AVG', 'MAX', 'MIN']
                
                for agg in aggregations:
                    if len(valid_queries) >= count:
                        break
                        
                    query_data = self._build_bi_query(table_name, dims, metric, company_field, agg_func=agg, is_virtual=datasource.is_virtual)
                    
                    if query_data and query_data['sql'] not in generated_sqls:
                        if self._validate_sql(query_data['sql'], datasource, db_connection=mssql_conn):
                            valid_queries.append(query_data)
                            generated_sqls.add(query_data['sql'])

        if mssql_conn:
            try:
                mssql_conn.close()
            except:
                pass

        return valid_queries

    def save_batch(self, queries: List[Dict], datasource: DataSource) -> int:
        """
        Saves the generated queries to MetricsEmbeddings.
        """
        saved_count = 0
        embedding_service = ServiceFactory.get_embedding_service()
        if not embedding_service:
            print("No Embedding Service available")
            return 0

        for idx, q in enumerate(queries):
            # Support both list of descriptions (NLG) and single string (Legacy)
            descriptions = q.get('description')
            if isinstance(descriptions, str):
                descriptions = [descriptions]
            elif not isinstance(descriptions, list):
                continue

            for variant_idx, desc in enumerate(descriptions):
                try:
                    # Generate embedding
                    vector = embedding_service.embed_text(desc)
                    if not vector:
                        continue

                    # Unique key including variant index
                    # E.g. LineasPedido_synth_12_0_hash
                    unique_key = f"{datasource.name}_synth_{idx}_{variant_idx}_{hash(desc) & 0xFFFFFFFF}"
                    
                    MetricsEmbeddings.objects.update_or_create(
                        kind='qa',
                        key=unique_key,
                        defaults={
                            'text': desc,
                            'vector': vector,
                            'metadata': {
                                'sql_template': q['sql'],
                                'source_table': datasource.name,
                                'scope': 'synthetic',
                                'label': desc[:50], # Helpful for debugging
                                'generated_at': str(datetime.now())
                            }
                        }
                    )
                    saved_count += 1
                except Exception as e:
                    print(f"Error saving synthetic query: {e}")
                    
        return saved_count

    def _fallback_generation(self, datasource, table_name, count):
        """Old logic for tables without BI markup"""
        return []
    
    def _get_col_name(self, field: DataField, is_virtual: bool) -> str:
        source_name = field.field_name
        if not is_virtual:
            try:
                bn = (field.business_name or "").strip()
            except Exception:
                bn = ""
            if bn:
                source_name = bn
        if is_virtual:
            return source_name
        safe = source_name.lower().replace(' ', '_').replace('.', '_')
        if safe == 'id':
            safe = 'source_id'
        if safe == 'order':
            safe = 'order'
        return safe

    def _build_bi_query(self, table: str, dims: tuple, metric: Optional[DataField], company_field: Optional[DataField], agg_func: str = "SUM", is_virtual: bool = False) -> Dict:
        """
        SELECT Dim1, Dim2, AGG(Metric) 
        FROM Table 
        WHERE CodigoEmpresa = 1 
        GROUP BY Dim1, Dim2 
        ORDER BY 1, 2
        """
        
        # Quote identifiers
        dim_cols = [self._quote(self._get_col_name(d, is_virtual)) for d in dims]
        dim_names = [d.business_name for d in dims]
        table_q = self._quote(table)
        
        select_parts = dim_cols.copy()
        
        # Metric
        if metric:
            met_col = self._quote(self._get_col_name(metric, is_virtual))
            met_name = metric.business_name
            # Choose aggregation
            agg = agg_func
            
            select_parts.append(f"{agg}({met_col}) as {met_col}")
            
            # Better descriptions
            action_map = {
                'SUM': 'Calcular el total de',
                'AVG': 'Calcular el promedio de',
                'MAX': 'Encontrar el valor máximo de',
                'MIN': 'Encontrar el valor mínimo de',
                'COUNT': 'Contar'
            }
            prefix = action_map.get(agg, f"Calcular {agg} de")
            desc_action = f"{prefix} {met_name}"
        else:
            select_parts.append("COUNT(*) as registros")
            desc_action = "Contar registros"
            met_name = "Registros"

        select_clause = ", ".join(select_parts)
        
        # Group By
        if is_virtual:
             # MSSQL does not support ordinal GROUP BY safely. Use explicit column names.
             group_clause = ", ".join(dim_cols)
        else:
             group_clause = ", ".join([str(i+1) for i in range(len(dim_cols))])
        
        # Where Clause (Mandatory Company)
        where_clause = ""
        if company_field:
            comp_col = self._quote(self._get_col_name(company_field, is_virtual))
            
            # [FIX] Check type for quoting '1'
            val = '{empresa}'
            if company_field.data_type in ['varchar', 'text', 'char', 'nvarchar']:
                 val = "'{empresa}'"
            
            where_clause = f"WHERE {comp_col} = {val}"

        # [FIX] Syntax differences
        if is_virtual:
             # MSSQL: SELECT TOP 50 ...
             sql = f"SELECT TOP 50 {select_clause} FROM {table_q} {where_clause} GROUP BY {group_clause} ORDER BY 1"
        else:
             # Postgres: SELECT ... LIMIT 50
             sql = f"SELECT {select_clause} FROM {table_q} {where_clause} GROUP BY {group_clause} ORDER BY 1 LIMIT 50"
        
        # [NLG] Natural Language Generation
        # Generate multiple variations to improve semantic matching
        descriptions = []
        
        # 1. Base Action Verbs
        verbs = ["Mostrar", "Ver", "Listar", "Dime", "Dame"]
        if is_virtual: verbs.extend(["Sacar", "Consultar"])
        
        dim_text = " por ".join(dim_names)
        
        if metric:
            # METRIC QUERIES
            met_name_clean = metric.business_name.lower().replace('importe', '').replace('neto', '').replace('total', '').strip() or "ventas"
            
            # Identify semantic concept (Money vs Quantity)
            is_money = any(k in metric.business_name.lower() for k in ['importe', 'precio', 'saldo', 'coste', 'margen', 'eur', '€'])
            if 'neto' in metric.field_name.lower() or 'importe' in metric.field_name.lower(): is_money = True
            
            noun = "ventas" if is_money else ("cantidad" if "cantidad" in metric.business_name.lower() else "unidades")
            if "margen" in metric.business_name.lower(): noun = "margen"
            if "coste" in metric.business_name.lower(): noun = "costes"
            
            # Variation 1: Formal
            descriptions.append(f"{agg_func} de {metric.business_name} desagregado por {dim_text}")
            
            # Variation 2: Business Question
            if agg_func == 'SUM':
                 if is_money:
                     descriptions.append(f"¿Cuánto hemos facturado por {dim_text}?")
                     descriptions.append(f"Ventas totales por {dim_text} para la empresa actual")
                 else:
                     descriptions.append(f"¿Cuántas unidades por {dim_text}?")
                     descriptions.append(f"Total de {noun} por {dim_text}")
            elif agg_func == 'AVG':
                 descriptions.append(f"Promedio de {noun} por {dim_text}")
                 descriptions.append(f"Media de {noun} agrupado por {dim_text}")
            
            # Variation 3: Ranking hints (implicitly ordered by 1)
            descriptions.append(f"Ranking de {dim_text} según {noun}")
            
        else:
            # COUNT QUERIES
            descriptions.append(f"Contar registros por {dim_text}")
            descriptions.append(f"Número de operaciones por {dim_text}")
            descriptions.append(f"Volumen de actividad por {dim_text}")
            descriptions.append(f"¿Cuántos registros hay por {dim_text}?")

        # Return LIST of descriptions/questions
        # The generator saves them all pointing to the same SQL
        return {
            "sql": sql,
            "description": descriptions, # Now a list
            "is_list": True
        }

    def _build_temporal_month_query(self, table: str, date_field: DataField, month_num: int, month_name: str, metric: Optional[DataField], company_field: Optional[DataField], business_name: str = "", context_suffix: str = "", is_virtual: bool = False) -> Dict:
        """
        Generates SQL for a specific month.
        Example: SELECT * FROM Table WHERE MONTH(DateCol) = 8
        """
        table_q = self._quote(table)
        date_col = self._quote(self._get_col_name(date_field, is_virtual))
        
        # WHERE Clause (Company + Month)
        where_parts = []
        
        # Company
        if company_field:
            comp_col = self._quote(self._get_col_name(company_field, is_virtual))
            val = '{empresa}'
            if company_field.data_type in ['varchar', 'text', 'char', 'nvarchar']:
                 val = "'{empresa}'"
            where_parts.append(f"{comp_col} = {val}")
            
        # Month
        if is_virtual:
            # MSSQL
            where_parts.append(f"MONTH({date_col}) = {month_num}")
        else:
            # Postgres
            where_parts.append(f"EXTRACT(MONTH FROM {date_col}) = {month_num}")
            
        where_clause = "WHERE " + " AND ".join(where_parts)
        
        # SELECT / Metric
        if metric:
            met_col = self._quote(self._get_col_name(metric, is_virtual))
            select_part = f"SUM({met_col}) as total"
            desc_part = f"Total de {metric.business_name}"
            # [FIX ISS-036] Include business object name
            # "Total de Importe de Pedidos de Cliente de agosto..."
            description = f"{desc_part} de {business_name} de {month_name}, para la empresa actual."
        else:
            select_part = "COUNT(*) as registros"
            desc_part = "Contar registros"
            # [FIX ISS-036] Include business object name
            # "Contar Pedidos de Cliente de agosto..."
            description = f"Contar {business_name} de {month_name}, para la empresa actual."
            
        # [NF-037] Append context concepts if available
        if context_suffix:
            description += f" {context_suffix}"

        # SQL Construction
        sql = f"SELECT {select_part} FROM {table_q} {where_clause}"
        
        return {
            "sql": sql,
            "description": description
        }

    def _build_temporal_recency_query(self, table: str, date_field: DataField, company_field: Optional[DataField], limit: int = 10, business_name: str = "", context_suffix: str = "", is_virtual: bool = False) -> Dict:
        """
        Generates SQL for recent records.
        Example: SELECT * FROM Table ORDER BY DateCol DESC LIMIT 10
        """
        table_q = self._quote(table)
        date_col = self._quote(self._get_col_name(date_field, is_virtual))
        
        # WHERE Clause (Company)
        where_clause = ""
        if company_field:
            comp_col = self._quote(self._get_col_name(company_field, is_virtual))
            val = '{empresa}'
            if company_field.data_type in ['varchar', 'text', 'char', 'nvarchar']:
                 val = "'{empresa}'"
            where_clause = f"WHERE {comp_col} = {val}"
            
        # SQL Construction
        select_clause = f"SELECT {date_col}"
        if is_virtual:
            select_clause = f"SELECT TOP {limit} *" # MSSQL TOP * is safer for "Show me"
            sql = f"{select_clause} FROM {table_q} {where_clause} ORDER BY {date_col} DESC"
        else:
            select_clause = "SELECT *" # Postgres
            sql = f"{select_clause} FROM {table_q} {where_clause} ORDER BY {date_col} DESC LIMIT {limit}"
            
        # [FIX ISS-036] Include business object name
        description = f"Mostrar los últimos {limit} {business_name} ordenados por {date_field.business_name}, para la empresa actual."
        
        # [NF-037] Append context concepts if available
        if context_suffix:
            description += f" {context_suffix}"

        return {
            "sql": sql,
            "description": description
        }

    def _build_relational_query(self, source_ds: DataSource, relation: DataRelation, target_dim: DataField, metric: Optional[DataField], company_field: Optional[DataField], agg_func: str = "SUM") -> Dict:
        """
        Builds a query with JOIN.
        SELECT Target.Dim, SUM(Source.Metric)
        FROM Source
        JOIN Target ON Source.FK = Target.PK
        GROUP BY Target.Dim
        """
        is_virtual = source_ds.is_virtual
        
        # Tables
        if is_virtual:
            source_tbl_name = source_ds.source_table
            target_tbl_name = relation.target.source_table
        else:
            source_tbl_name = source_ds.get_local_table_name()
            target_tbl_name = relation.target.get_local_table_name()
            
        if not source_tbl_name or not target_tbl_name:
            return None

        # Aliases for clarity (T1, T2)
        t1 = "t1"
        t2 = "t2"
        
        # JOIN Condition
        # t1.fk = t2.pk
        fk_col = self._get_col_name(relation.from_field, is_virtual)
        pk_col = self._get_col_name(relation.to_field, is_virtual)
        
        join_clause = f"JOIN {self._quote(target_tbl_name)} {t2} ON {t1}.{self._quote(fk_col)} = {t2}.{self._quote(pk_col)}"
        
        # Dimension (from Target T2)
        dim_col_name = self._get_col_name(target_dim, is_virtual)
        dim_select = f"{t2}.{self._quote(dim_col_name)}"
        
        # Metric (from Source T1)
        if metric:
            met_col_name = self._get_col_name(metric, is_virtual)
            met_select = f"{agg_func}({t1}.{self._quote(met_col_name)})"
            met_desc = metric.business_name
        else:
            met_select = "COUNT(*)"
            met_desc = "Registros"
            
        # WHERE (Company on Source T1)
        where_clause = ""
        if company_field:
            comp_col = self._get_col_name(company_field, is_virtual)
            val = '{empresa}'
            if company_field.data_type in ['varchar', 'text', 'char', 'nvarchar']:
                 val = "'{empresa}'"
            where_clause = f"WHERE {t1}.{self._quote(comp_col)} = {val}"
            
        # Construct SQL
        if is_virtual:
             # MSSQL
             sql = f"SELECT TOP 50 {dim_select}, {met_select} as valor FROM {self._quote(source_tbl_name)} {t1} {join_clause} {where_clause} GROUP BY {dim_select} ORDER BY 1"
        else:
             # Postgres
             sql = f"SELECT {dim_select}, {met_select} as valor FROM {self._quote(source_tbl_name)} {t1} {join_clause} {where_clause} GROUP BY {dim_select} ORDER BY 1 LIMIT 50"
             
        # Description
        descriptions = []
        dim_desc = target_dim.business_name
        
        if metric:
             descriptions.append(f"{agg_func} de {met_desc} por {dim_desc}")
             descriptions.append(f"Desglose de {met_desc} según {dim_desc}")
             descriptions.append(f"¿Cómo se distribuye {met_desc} entre {dim_desc}?")
        else:
             descriptions.append(f"Cantidad de registros por {dim_desc}")
             
        return {
            "sql": sql,
            "description": descriptions,
            "is_list": True
        }

    def _quote(self, name: str) -> str:
        return f'"{name}"'

    def _validate_sql(self, sql: str, datasource: DataSource = None, db_connection=None) -> bool:
        """
        Validates the generated SQL against the target database.
        """
        # [FIX] Replace placeholder {empresa} with dummy value for validation
        validation_sql = sql.replace("'{empresa}'", "'1'").replace("{empresa}", "1")

        # [FIX] MSSQL Validation for Virtual Tables
        if datasource and datasource.is_virtual:
             if not db_connection:
                 return False

             try:
                 cursor = db_connection.cursor()
                 cursor.execute("SET FMTONLY ON")
                 cursor.execute(validation_sql)
                 cursor.execute("SET FMTONLY OFF")
                 return True
             except Exception as e:
                 return False
        
        # Postgres Validation (EXPLAIN)
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"EXPLAIN {validation_sql}")
            return True
        except Exception as e:
            logger.warning(f"Validation Error: {e}")
            return False
