"""
Intent Detector para Auto-Training Inteligente.
Analiza queries fallidas y detecta patrones.
"""
import re
from typing import Dict, List, Any, Optional
from datia.models import DataSource, DataField

class IntentDetector:
    """Detecta intenciones en queries de lenguaje natural."""
    
    # Meses en español
    MESES = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12
    }
    
    def detect(self, query: str, empresa: int) -> Dict[str, Any]:
        """
        Analiza una query y extrae intenciones.
        
        Returns:
            {
                'temporal': {'month': 8, 'year': 2025} o None,
                'numeric': {'field_hint': 'importe', 'op': '>', 'value': 1000} o None,
                'dimensional': {'field_hint': 'cliente', 'value': 'MERCADONA'} o None,
                'tables': ['datiadb_cabecerapedidocliente']
            }
        """
        q_lower = query.lower().strip()
        intent = {
            'temporal': None,
            'numeric': None,
            'dimensional': None,
            'tables': []
        }
        
        # 1. DETECCIÓN TEMPORAL
        intent['temporal'] = self._detect_temporal(q_lower)
        
        # 2. DETECCIÓN NUMÉRICA (Filtros)
        intent['numeric'] = self._detect_numeric(q_lower)
        
        # 3. DETECCIÓN DE TABLAS RELEVANTES
        intent['tables'] = self._detect_tables(q_lower, empresa)
        
        # 4. DETECCION DE LIMITE Y ORDEN
        intent['limit'], intent['ordering'] = self._detect_limit_ordering(q_lower)
        
        # 5. DETECCION DE METRICAS DE NEGOCIO (NEW)
        # ¿Qué quiere medir? (Ventas, Coste, Margen, Beneficio)
        intent['metric'] = self._detect_metric_intent(q_lower)
        
        # 6. DETECCION DE AGRUPACION (NEW)
        # ¿Cómo lo quiere ver? (Por cliente, por articulo, por mes)
        intent['grouping'] = self._detect_grouping_intent(q_lower)
        
        # 7. FILTROS DIMENSIONALES (Especificos: "Cliente Mercadona")
        intent['dimensional'] = self._detect_dimensional(q_lower)

        # 8. DETECCION DE TIPO DE RESPUESTA (NEW)
        intent['type'] = self._detect_type_intent(q_lower)

        return intent
    
    def _detect_type_intent(self, q_lower: str) -> str:
        """
        Detecta si el usuario quiere una tabla, un grafico o un informe completo.
        Default: 'table'
        """
        if any(w in q_lower for w in ['informe', 'reporte', 'analisis', 'detallado', 'resumen', 'dashboard', 'deep dive']):
            return 'report'
        if any(w in q_lower for w in ['grafico', 'chart', 'evolucion', 'tendencia', 'visual']):
            return 'chart'
        
        return 'table'

    def _detect_temporal(self, query: str) -> Optional[Dict[str, int]]:

        """Detecta menciones temporales (meses, años)."""
        result = {}
        
        # Detectar meses
        # Detectar meses y sus abreviaturas con regex estricto
        for mes_txt, mes_num in self.MESES.items():
            # \b asegura que sea palabra completa (ej: evita matchear 'ene' en 'general')
            if re.search(r'\b' + mes_txt + r'\b', query, re.IGNORECASE):
                result['month'] = mes_num
                break
        
        # Detectar años (2020-2030)
        year_match = re.search(r'\b(202[0-9])\b', query)
        if year_match:
            result['year'] = int(year_match.group(1))
        
        # Detectar trimestres
        q_match = re.search(r'\bq\s*([1-4])\b', query, re.IGNORECASE)
        if q_match:
            result['quarter'] = int(q_match.group(1))
        else:
            t_match = re.search(r'\btrimestre\s*([1-4])\b', query, re.IGNORECASE)
            if t_match:
                result['quarter'] = int(t_match.group(1))
            elif re.search(r'último trimestre|ultimo trimestre', query, re.IGNORECASE):
                result['quarter'] = 4
        
        # Detectar rangos de meses
        m_range = re.search(r'\b(entre|desde|de)\s+([a-záéíóú]+|\d{1,2})\s+(?:y|a|hasta)\s+([a-záéíóú]+|\d{1,2})\b', query, re.IGNORECASE)
        if m_range:
            start_tok = m_range.group(2).lower()
            end_tok = m_range.group(3).lower()
            def tok_to_month(tok: str) -> int:
                if tok.isdigit():
                    val = int(tok)
                    return val if 1 <= val <= 12 else None
                return self.MESES.get(tok)
            start_m = tok_to_month(start_tok)
            end_m = tok_to_month(end_tok)
            if start_m and end_m:
                result['month_range'] = {'start': start_m, 'end': end_m}
        
        # Detectar últimos 3 meses
        if re.search(r'(los\s+)?(últimos|ultimos)\s+3\s+meses', query, re.IGNORECASE) or re.search(r'(3|tres)\s+(últimos|ultimos)\s+meses', query, re.IGNORECASE):
            result['last_3_months'] = 1
        
        # Rangos relativos
        if 'últim' in query and ('mes' in query or '30' in query):
            result['range'] = 'last_month'
        elif 'últim' in query and ('semana' in query or '7' in query):
            result['range'] = 'last_week'
            
        return result if result else None
    
    def _detect_numeric(self, query: str) -> Optional[Dict[str, Any]]:
        """Detecta comparaciones numéricas."""
        # Patrones: "mayor a 1000", "más de 500", "menor de 100"
        
        # Mayor/Superior
        match = re.search(r'(mayor|superior|mas de|más de)\s+(\d+)', query)
        if match:
            return {
                'op': '>',
                'value': int(match.group(2)),
                'field_hint': self._guess_numeric_field(query)
            }
        
        # Menor/Inferior
        match = re.search(r'(menor|inferior|menos de)\s+(\d+)', query)
        if match:
            return {
                'op': '<',
                'value': int(match.group(2)),
                'field_hint': self._guess_numeric_field(query)
            }
        
        return None
    
    def _guess_numeric_field(self, query: str) -> str:
        """Adivina el campo numérico basado en keywords."""
        if 'importe' in query or 'euro' in query or 'precio' in query:
            return 'importe'
        if 'cantidad' in query or 'unidad' in query:
            return 'cantidad'
        return 'metric'  # Genérico
    
    def _detect_dimensional(self, query: str) -> Optional[Dict[str, Any]]:
        """Detecta filtros por dimensiones."""
        # Clientes conocidos
        clientes = ['mercadona', 'carrefour', 'dia', 'eroski', 'alcampo']
        for cliente in clientes:
            if cliente in query:
                return {
                    'field_hint': 'cliente',
                    'value': cliente.upper()
                }
        
        # Provincias
        provincias = ['madrid', 'barcelona', 'valencia', 'sevilla', 'zaragoza']
        for prov in provincias:
            if prov in query:
                return {
                    'field_hint': 'provincia',
                    'value': prov.upper()
                }
        
        return None
    
    def _detect_tables(self, query: str, empresa: int) -> List[str]:
        """Identifica tablas relevantes basadas en keywords."""
        tables = []
        
        # Keywords de tabla
        keywords_cabecera = ['pedido', 'venta', 'factura', 'orden', 'cabecera']
        keywords_lineas = ['linea', 'detalle', 'articulo', 'producto']
        
        # Buscar tablas activas
        sources = DataSource.objects.filter(is_active=True)
        
        for source in sources:
            table_name_lower = source.name.lower()
            local_name = source.get_local_table_name()
            
            if not local_name:
                continue
            
            # Match por keywords
            for kw in keywords_cabecera:
                if kw in query or kw in table_name_lower:
                    if local_name not in tables:
                        tables.append(local_name)
                    break
            
            for kw in keywords_lineas:
                if kw in query or kw in table_name_lower:
                    if local_name not in tables:
                        tables.append(local_name)
                    break
        
        return tables

    def _detect_limit_ordering(self, q_lower: str):
        limit = None
        ordering = None
        
        # "10 ultimos", "top 5", "5 primeros"
        limit_match = re.search(r'\b(\d+)\s+(ultimo|último|reciente|primero|top|mejor|peor)', q_lower)
        if limit_match:
            limit = int(limit_match.group(1))
            kw = limit_match.group(2)
            if any(x in kw for x in ['ultim', 'reciente', 'top', 'mejor']):
                ordering = 'DESC'
            elif any(x in kw for x in ['primer', 'peor']):
                ordering = 'ASC'
        else:
            # "Ultimos 10"
            limit_match_rev = re.search(r'(ultimo|último|reciente|primero|top|mejor|peor)\s*s?\s+(\d+)', q_lower)
            if limit_match_rev:
                limit = int(limit_match_rev.group(2))
                kw = limit_match_rev.group(1)
                if any(x in kw for x in ['ultim', 'reciente', 'top', 'mejor']):
                    ordering = 'DESC'
                elif any(x in kw for x in ['primer', 'peor']):
                    ordering = 'ASC'
        
        # "mejores 10" o "10 mejores"
        if limit is None:
            m_mej = re.search(r'\bmejores\s+(\d+)\b', q_lower)
            if m_mej:
                limit = int(m_mej.group(1))
                ordering = 'DESC'
        if limit is None:
            m_mej_rev = re.search(r'\b(\d+)\s+mejores\b', q_lower)
            if m_mej_rev:
                limit = int(m_mej_rev.group(1))
                ordering = 'DESC'
                    
        return limit, ordering

    def _detect_metric_intent(self, q_lower: str) -> str:
        """
        Detecta qué métrica financiera interesa.
        Returns: 'sales', 'cost', 'margin', 'profit', 'units', 'count' (default implied if nothing else)
        """
        if any(w in q_lower for w in ['margen', 'rentabil', 'beneficio', 'ganancia', 'margin', 'benficio']):
            return 'margin'
        if any(w in q_lower for w in ['coste', 'gasto', 'compra', 'gastos', 'compras', 'costes', 'costo']):
            return 'cost'
        if any(w in q_lower for w in ['cantidad', 'unidad', 'bulto', 'pieza']):
            return 'units'
        if any(w in q_lower for w in ['venta', 'pedidos', 'facturacion', 'ingreso', 'importe', 'ventas', 'facturado', 'venetes']):
            return 'sales'
            
        return 'sales' # Default a ventas si no se especifica, mejor que count(*)

    def _detect_grouping_intent(self, q_lower: str) -> Optional[str]:
        """
        Detecta intención de agrupamiento.
        Returns: 'month', 'year', 'client', 'product', 'zone', 'agent'
        """
        # Temporal
        if 'mes' in q_lower or 'mensual' in q_lower:
            return 'month'
        if 'año' in q_lower or 'anual' in q_lower or 'ejercicio' in q_lower:
            return 'year'
        if 'trimestre' in q_lower:
            return 'quarter'
            
        # Dimensiones
        if 'cliente' in q_lower:
            return 'client'
        if 'articulo' in q_lower or 'producto' in q_lower or 'referencia' in q_lower:
            return 'product'
        if 'familia' in q_lower:
            return 'family'
        if 'zona' in q_lower or 'provincia' in q_lower or 'pais' in q_lower:
            return 'zone'
        if 'representante' in q_lower or 'agente' in q_lower or 'vendedor' in q_lower:
            return 'agent'
            
        return None
