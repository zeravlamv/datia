
from typing import Dict, Any
from .base import BaseHandler
from datia.services.security.sql_guard import SQLGuard

class ListHandler(BaseHandler):
    def handle(self, intent_data: Dict, context: Dict) -> Dict:
        sql = intent_data['sql']
        limit = context.get('limit', 20)
        ejercicio = context['ejercicio']
        
        # Inject params if sql is a template (generic RAG) or pre-built string
        if '{empresa}' in sql:
            sql = sql.format(**context)
            
        try:
            SQLGuard.ensure_allowed(sql)
        except PermissionError as e:
            return {"type": "error", "text": str(e), "sql": sql}
        rows = self.exec_sql(sql)
        
        # [FIX] If no data, delegate to formatter immediately to show "Force Generation" button
        if not rows:
             lang = context.get('lang', 'es')
             return self.formatter.format_response(intent_data, rows, ejercicio, limit, lang=lang)

        if context.get('detailed'):
            return self.generate_deep_dive_report(rows, intent_data)
            
        # Enrich with Top Breakdown if Sales Context (Consistency with GenerativeHandler)
        extras = {}
        question = context.get('query', '') or intent_data.get('label', '')
        is_sales_context = any(k in str(question).lower() for k in ['venta', 'factur', 'revenue', 'compar', 'vs'])
        
        if is_sales_context:
             try:
                 # Fetch Top Clients
                 top_clients = self._fetch_top_breakdown('DatiaDB_CabeceraPedidoCliente', 'NombreCliente', 'ImporteNeto', context, limit=5)
                 if top_clients: extras['top_clients'] = top_clients
                 
                 # Fetch Top Products
                 top_products = self._fetch_top_breakdown('DatiaDB_LineasPedidoCliente', 'DescripcionArticulo', 'ImporteNeto', context, limit=5)
                 if top_products: extras['top_products'] = top_products
             except Exception:
                 pass
        
        # Inject extras
        intent_data['extras'] = extras

        lang = context.get('lang', 'es')
        return self.formatter.format_response(intent_data, rows, ejercicio, limit, lang=lang)
