import logging
import re
from typing import Dict, Any, Optional
from .base import BaseBuilder

logger = logging.getLogger(__name__)

class RankingBuilder(BaseBuilder):
    """
    Handles Top/Ranking queries (e.g. "Top Clientes", "Mejores Familias").
    """

    @classmethod
    def build(cls, question: str, empresa: int, ejercicio: int, entity_key: str) -> Optional[Dict[str, Any]]:
        config = cls.ENTITIES.get(entity_key)
        if not config: return None
        
        # 1. Schema Validation
        label_col, col_map = cls.validate_table_columns(config['table'], config['label_candidates'])
        if not label_col:
            logger.warning(f"Ranking Handler: Could not resolve label column for {entity_key}")
            return None
            
        # 2. Metric Resolution
        is_purchase = (entity_key == 'proveedor')
        val_col, cost_col, metric_type = cls.resolve_metrics(col_map, question.lower(), is_purchase)
        
        # 3. Year Resolution
        years = re.findall(r'\b(20\d{2})\b', question)
        target_year = years[0] if years else ejercicio
        
        # 4. Date Column Resolution & Join Injection (Rule: Lines need Cabecera for Date Safety)
        date_col_name = None
        join_clause = ""
        alias = config['alias'] # Defined early for usage in JOIN
        
        # Determine if we need to join with Cabecera
        needs_join = False
        if config['metric_source'] == 'lineas':
            # Check if DateCol exists in Lines table
            found_in_lines, _ = cls.validate_table_columns(config['table'], [config['date_col']])
            if not found_in_lines:
                needs_join = True
        
        if needs_join:
            # JOIN STRATEGY
            # Assuming standard naming convention: Cabecera is same name but 'cabecera' instead of 'lineas'
            cabecera_table = config['table'].replace('lineas', 'cabecera')
            
            # Verify Cabecera exists
            _, _ = cls.validate_table_columns(cabecera_table, [])
            
            # Build JOIN with FIXED ALIAS usage
            join_clause = f"""
                JOIN "{cabecera_table}" H 
                ON {alias}."CodigoEmpresa" = H."CodigoEmpresa" 
                AND {alias}."EjercicioPedido" = H."EjercicioPedido" 
                AND {alias}."SeriePedido" = H."SeriePedido" 
                AND {alias}."NumeroPedido" = H."NumeroPedido"
            """
            
            # Use Header Date
            date_candidates = ['FechaPedido', 'FechaAlbaran', 'Fecha']
            date_col_name, _ = cls.validate_table_columns(cabecera_table, date_candidates)
            if not date_col_name: date_col_name = "FechaPedido" # Fallback
            
            # Update date expression to use Header Alias (H)
            date_expr = f'H."{date_col_name}"'
            logger.info(f"RankingBuilder: Injected JOIN with {cabecera_table} for Date Safety")
            
        else:
            # NO JOIN - Use Table's own date
            date_col_name, _ = cls.validate_table_columns(config['table'], [config['date_col'], 'Fecha', 'FechaDocumento'])
            if not date_col_name: date_col_name = config['date_col']
            date_expr = f'{alias}."{date_col_name}"'

        # 5. Build Query
        table = f'"{config["table"]}"'
        
        limit_match = re.search(r'\b(5|10|15|20|50|100)\b', question)
        limit = int(limit_match.group(1)) if limit_match else 20
        
        sql = f"""
            SELECT 
                {alias}."{label_col}" as label, 
                SUM({alias}."{val_col}") as val, 
                SUM({alias}."{cost_col}") as coste, 
                COUNT(DISTINCT {alias}."{config['count_col']}") as ops 
            FROM {table} {alias}
            {join_clause}
            WHERE {alias}."CodigoEmpresa" = {empresa} 
              AND EXTRACT(YEAR FROM {date_expr}) = {target_year}
            GROUP BY 1 
            ORDER BY 2 DESC 
            LIMIT {limit}
        """
        
        return {
            'key': f'ranking_{entity_key}',
            'sql': " ".join(sql.split()),
            'type': 'table',
            'chart_type': 'bar',
            'label': f'Top {entity_key.capitalize()}s {target_year}',
            'source': 'deterministic_v3_ranking',
            'intent_meta': {'metric': metric_type}
        }
