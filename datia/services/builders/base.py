import logging
from typing import Dict, Any, Optional, Tuple, List
from django.db import connections

logger = logging.getLogger(__name__)

class BaseBuilder:
    """
    Base class for specific Query Builders.
    Contains shared utilities for Schema Validation and Metric Resolution.
    """

    # Shared Entity Configuration
    ENTITIES = {
        'cliente': {
            'table': 'datiadb_cabecerapedidocliente',
            'alias': 'C',
            'label_candidates': ['Nombre', 'RazonSocial', 'NombreCliente'],
            'date_col': 'FechaPedido',
            'count_col': 'NumeroPedido',
            'metric_source': 'cabecera'
        },
        'articulo': {
            'table': 'datiadb_lineaspedidocliente',
            'alias': 'L',
            'label_candidates': ['DescripcionArticulo', 'Articulo', 'Producto'],
            'date_col': 'FechaPedido', # Forced to FechaPedido to trigger JOIN with Cabecera
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
            'date_col': 'FechaPedido', # Forced to FechaPedido to trigger JOIN
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

    @staticmethod
    def validate_table_columns(table_name: str, candidates: list[str]) -> Tuple[Optional[str], Dict[str, str]]:
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
    def resolve_metrics(col_map: Dict[str, str], intent_text: str, is_purchase: bool = False) -> Tuple[str, str, str]:
        """
        Resolves (ValCol, CostCol, MetricType) based on available columns and intent.
        """
        # 1. Define Candidates
        sales_cands = ['ImporteLiquido', 'ImporteNeto', 'ImporteBruto', 'TotalNeto', 'BaseImponible']
        cost_cands = ['ImporteCoste', 'CosteTotal', 'TotalCoste', 'Coste'] 
        
        # 2. Find existing columns
        real_sales = next((col_map[c.lower()] for c in sales_cands if c.lower() in col_map), 'ImporteBruto')
        real_cost = next((col_map[c.lower()] for c in cost_cands if c.lower() in col_map), None)
        
        # 3. Determine Intent
        metric_type = 'sales'
        if is_purchase:
            metric_type = 'purchase_amount'
            # Purchases usually don't have cost, just Net Amount
            val_col = real_sales
            cost_col = "0"
        elif 'coste' in intent_text or 'gasto' in intent_text:
            metric_type = 'cost'
            val_col = real_cost if real_cost else "0"
            cost_col = "0"
        elif 'margen' in intent_text or 'beneficio' in intent_text:
            metric_type = 'margin'
            val_col = real_sales
            cost_col = real_cost if real_cost else "0"
        else:
            # Default Sales
            val_col = real_sales
            cost_col = real_cost if real_cost else "0"
            
        return val_col, cost_col, metric_type
