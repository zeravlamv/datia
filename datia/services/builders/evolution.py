import logging
import re
from typing import Dict, Any, Optional
from .base import BaseBuilder

logger = logging.getLogger(__name__)

class EvolutionBuilder(BaseBuilder):
    """
    Handles Evolution/Trend queries (e.g. "Ventas 2024", "Compras Mensuales").
    """

    @classmethod
    def build(cls, question: str, empresa: int, ejercicio: int, is_purchase: bool = False) -> Dict[str, Any]:
        # Determine Table
        if is_purchase:
            table = "datiadb_cabeceraalbaranproveedor"
            if 'pedido' in question.lower():
                table = "datiadb_cabecerapedidoproveedor"
        else:
            ql = question.lower()
            if 'albaran' in ql or 'albarán' in ql or 'albaranes' in ql:
                table = "datiadb_cabeceraalbarancliente"
            else:
                table = "datiadb_cabecerapedidocliente"
            
        # Validate Schema
        _, col_map = cls.validate_table_columns(table, [])
        if not col_map:
            return {'error': 'Schema validation failed for evolution'}

        # Resolve Metrics
        val_col, cost_col, metric_type = cls.resolve_metrics(col_map, question.lower(), is_purchase)
        
        # Resolve Date
        date_candidates = ['FechaPedido', 'FechaAlbaran', 'Fecha', 'FechaDocumento']
        date_col = next((col_map[c.lower()] for c in date_candidates if c.lower() in col_map), 'FechaPedido')
        
        # Resolve Year
        years = re.findall(r'\b(20\d{2})\b', question)
        
        if len(years) >= 2:
            # COMPARISON (Multi-Year)
            years_sql = ", ".join(years)
            sql = f"""
                SELECT 
                    EXTRACT(MONTH FROM "{date_col}") as label, 
                    EXTRACT(YEAR FROM "{date_col}") as serie, 
                    SUM("{val_col}") as val, 
                    SUM("{cost_col}") as coste,
                    COUNT(DISTINCT "NumeroPedido") as ops 
                FROM "{table}" 
                WHERE "CodigoEmpresa" = {empresa} 
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
                'source': 'deterministic_v3_evolution',
                'intent_meta': {'metric': metric_type, 'is_comparison': True}
            }
        else:
            # SINGLE YEAR
            target_year = years[0] if years else ejercicio
            sql = f"""
                SELECT 
                    EXTRACT(MONTH FROM "{date_col}") as label, 
                    SUM("{val_col}") as val, 
                    SUM("{cost_col}") as coste,
                    COUNT(DISTINCT "NumeroPedido") as ops 
                FROM "{table}" 
                WHERE "CodigoEmpresa" = {empresa} 
                  AND EXTRACT(YEAR FROM "{date_col}") = {target_year}
                GROUP BY label 
                ORDER BY label
            """
            return {
                'key': 'evolution_single',
                'sql': " ".join(sql.split()),
                'type': 'chart',
                'chart_type': 'bar',
                'label': f'Evolución Mensual {target_year}',
                'source': 'deterministic_v3_evolution',
                'intent_meta': {'metric': metric_type}
            }
