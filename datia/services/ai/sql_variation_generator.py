"""
Geenerador de Variaciones SQL Basado en Reglas.
Convierte intenciones detectadas (tiempo, número, dimensión) en queries SQL candidatas.
"""
from typing import List, Dict, Any
from datia.models import DataField, DataSource

class SQLVariationGenerator:
    """Genera SQLs candidatos basados en intenciones y esquema."""

    def generate(self, intent: Dict[str, Any], empresa_id: int) -> List[str]:
        """
        Genera una lista de queries SQL de NEGOCIO candidatas.
        Prioriza: SUM(metric), GROUP BY dim, ORDER BY metric DESC.
        """
        variations = []
        tables = intent.get('tables', [])
        
        if not tables:
            return []

        # Por ahora asumimos una tabla principal
        main_table = tables[0]
        fields = self._get_table_fields(main_table)
        
        # 1. IDENTIFICAR MÉTRICAS (Numeric Fields)
        # ----------------------------------------
        metric_intent = intent.get('metric', 'sales') # default sales
        
        # Keywords para buscar campos
        sales_kw = ['importe', 'amount', 'total', 'neto', 'venta']
        cost_kw  = ['coste', 'costo', 'compra']
        units_kw = ['cantidad', 'unidades', 'bultos']
        
        f_sales = self._find_field_by_type(fields, 'numeric', sales_kw)
        f_cost  = self._find_field_by_type(fields, 'numeric', cost_kw)
        f_units = self._find_field_by_type(fields, 'numeric', units_kw)
        
        # Determinar Select Expression
        select_expr = ""
        metric_alias = "Valor"
        
        if metric_intent == 'margin':
            if f_sales and f_cost:
                select_expr = f"SUM({f_sales}) - SUM({f_cost})"
                metric_alias = "MargenBeneficio"
            elif f_sales:
                # Fallback si no hay coste
                select_expr = f"SUM({f_sales})"
                metric_alias = "Ventas (Sin Coste)"
        elif metric_intent == 'cost':
             if f_cost:
                 select_expr = f"SUM({f_cost})"
                 metric_alias = "CosteTotal"
             elif f_sales:
                 select_expr = f"SUM({f_sales})" # Fallback
        elif metric_intent == 'units':
             if f_units:
                 select_expr = f"SUM({f_units})"
                 metric_alias = "Unidades"
             else:
                 select_expr = "COUNT(*)" # Unico caso donde count aceptable para "cantidad"
                 metric_alias = "ConteoRegistros"
        else: # Sales default
             if f_sales:
                 select_expr = f"SUM({f_sales})"
                 metric_alias = "VentasTotal"
             else:
                 select_expr = "COUNT(*)" # Last resort fallback
        
        # 2. CONSTRUIR CONDICIONES (WHERE)
        # --------------------------------
        try:
            emp_int = int(str(empresa_id).strip())
        except Exception:
            emp_int = 0
        conditions = [f"sync_empresa = {emp_int}"]
        
        # Temporal
        if intent.get('temporal'):
             conditions.extend(self._build_temporal_conditions(intent['temporal'], fields))
             
        # Numérico (Filtros en HAVING o WHERE?)
        # Si es filtro "mayor a 1000", suele ser sobre la métrica agregada -> HAVING
        # Si es sobre un campo dimensional -> WHERE.
        # Por simplicidad v1: Asumimos WHERE si encontramos campo no agregado, o HAVING si es métrica.
        having_clause = ""
        if intent.get('numeric'):
             # Simplificación: Si quiere "ventas > 1000", es HAVING SUM(venta) > 1000
             # Pero SQL generator necesita ser robusto.
             # Generamos variacion con HAVING.
             n_op = intent['numeric']['op']
             n_val = intent['numeric']['value']
             having_clause = f"HAVING {select_expr} {n_op} {n_val}"

        # 3. AGRUPAMIENTO (GROUP BY)
        # --------------------------
        grouping = intent.get('grouping')
        group_field = None
        group_expr = ""
        
        if grouping == 'month':
             date_field = self._find_field_by_type(fields, 'date', ['fecha', 'date'])
             if date_field:
                 group_expr = f"EXTRACT(MONTH FROM {date_field})"
                 group_field = "Mes"
        elif grouping == 'year':
             date_field = self._find_field_by_type(fields, 'date', ['fecha', 'date'])
             if date_field:
                 group_expr = f"EXTRACT(YEAR FROM {date_field})"
                 group_field = "Ejercicio"
        elif grouping == 'client':
             group_expr = self._find_field_by_keyword(fields, 'cliente') or self._find_field_by_keyword(fields, 'nombre')
             group_field = "Cliente"
        elif grouping == 'product':
             group_expr = self._find_field_by_keyword(fields, 'articulo') or self._find_field_by_keyword(fields, 'descripcion')
             group_field = "Producto"
        elif grouping == 'zone':
             group_expr = self._find_field_by_keyword(fields, 'provincia') or self._find_field_by_keyword(fields, 'zona')
             group_field = "Zona"
        elif grouping == 'agent':
             group_expr = self._find_field_by_keyword(fields, 'agente') or self._find_field_by_keyword(fields, 'vendedor')
             group_field = "Agente"

        # 4. ORDENAMIENTO Y LIMITES
        # -------------------------
        # Por defecto en BI: Ordenar por la métrica descendente (Top)
        order_clause = f"ORDER BY 2 DESC" if group_expr else "" # 2 refers to metric usually
        
        # Override si hay intención explícita
        if intent.get('ordering') == 'ASC':
             order_clause = f"ORDER BY 2 ASC"
             
        # Limite
        limit_clause = ""
        if intent.get('limit'):
             limit_clause = f"LIMIT {intent['limit']}"
        else:
             limit_clause = "LIMIT 20" # Default safety limit for BI lists

        # 5. GENERAR SQL FINALES
        # ----------------------
        
        # Variación A: Agrupada (La preferida si hay grouping)
        if group_expr:
             sql = f"SELECT {group_expr} as {group_field}, {select_expr} as {metric_alias} FROM {main_table} WHERE {' AND '.join(conditions)} GROUP BY 1 {having_clause} {order_clause} {limit_clause}"
             variations.append(sql)
        
        # Variación B: Totales (Sin agrupar, si no hay grouping o como alternativa)
        if not group_expr or 'temporal' in intent: # Si hay filtro temporal, a veces quieren solo el total
             sql = f"SELECT {select_expr} as {metric_alias} FROM {main_table} WHERE {' AND '.join(conditions)}"
             variations.append(sql)
             
        # Variación C: Detalle (Solo si pidieron Limite explícito y no es agrupación)
        # "10 ultimos pedidos" -> Listado, no suma.
        if intent.get('limit') and not grouping:
             # Necesitamos columnas estrella pero mejor * para detalle
             date_field = self._find_field_by_type(fields, 'date', ['fecha', 'date'])
             sort_col = date_field if date_field else "1"
             sql = f"SELECT * FROM {main_table} WHERE {' AND '.join(conditions)} ORDER BY {sort_col} DESC LIMIT {intent['limit']}"
             variations.append(sql)

        return list(dict.fromkeys([v for v in variations if v]))

    def _get_table_fields(self, table_name: str) -> List[DataField]:
        """Obtiene los metadatos de campos para una tabla dada (nombre local)."""
        # Buscar DataSource por nombre de tabla local (aproximación)
        # El nombre local es "datiadb_xyz", el source_table es "XYZ"
        # Buscamos source mapeado
        ds = None
        # Iterar fuentes para encontrar cual genera esta tabla local
        # Esto es costoso si hay muchos sources, pero seguro
        for source in DataSource.objects.filter(is_active=True):
            if source.get_local_table_name() == table_name:
                ds = source
                break
        
        if not ds:
            return []
            
        return list(DataField.objects.filter(source=ds))

    def _find_field_by_type(self, fields: List[DataField], dtype: str, priority_keywords: List[str] = None) -> str:
        """Encuentra un campo por tipo de dato, priorizando por nombre."""
        # Mapeo de tipos django a categorías
        numeric_types = ['decimal', 'int', 'float', 'number', 'numeric']
        date_types = ['date', 'datetime', 'timestamp']
        
        candidates = []
        for f in fields:
            f_type = f.data_type.lower()
            if dtype == 'numeric' and f_type in numeric_types:
                candidates.append(f.field_name)
            elif dtype == 'date' and f_type in date_types:
                candidates.append(f.field_name)
        
        if not candidates:
            return None
            
        # Prioridad por keyword
        if priority_keywords:
            for kw in priority_keywords:
                for cand in candidates:
                    if kw in cand.lower():
                        return f'"{cand}"' # Quote for safety
        
        # Si no hay prioridad, devolver el primero
        return f'"{candidates[0]}"'

    def _find_field_by_keyword(self, fields: List[DataField], keyword: str) -> str:
        """Busca un campo que contenga la keyword en su nombre."""
        for f in fields:
            if keyword in f.field_name.lower():
                return f'"{f.field_name}"'
        return None

    def _build_temporal_conditions(self, temp_intent: Dict, fields: List[DataField]) -> List[str]:
        """Genera condiciones WHERE para tiempo."""
        conditions = []
        date_field = self._find_field_by_type(fields, 'date', ['fecha', 'date', 'created'])
        
        if not date_field:
            return []
            
        if 'month' in temp_intent:
            month = temp_intent['month']
            # Postgres: EXTRACT(MONTH FROM col)
            conditions.append(f"EXTRACT(MONTH FROM {date_field}) = {month}")
            
            # Si hay año, añadirlo
            if 'year' in temp_intent:
                year = temp_intent['year']
                conditions.append(f"EXTRACT(MONTH FROM {date_field}) = {month} AND EXTRACT(YEAR FROM {date_field}) = {year}")
        
        if 'year' in temp_intent and 'month' not in temp_intent:
             year = temp_intent['year']
             conditions.append(f"EXTRACT(YEAR FROM {date_field}) = {year}")
             
        return conditions
