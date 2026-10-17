
from typing import Dict, Any
from .base import BaseHandler
from datia.services.query_builder import QueryBuilder
from datia.services.security.sql_guard import SQLGuard

class DynamicHandler(BaseHandler):
    def handle(self, intent_data: Dict, context: Dict) -> Dict:
        sql = intent_data['sql']
        ejercicio = context['ejercicio']
        limit = context.get('limit', 20)
        is_detailed = context.get('detailed', False)
        sql = sql.replace('{limit}', str(limit))
        try:
            SQLGuard.ensure_allowed(sql)
        except PermissionError as e:
            return {"type": "error", "text": str(e), "sql": sql}
        rows = self.exec_sql(sql)
        
        # [FIX] If no data, delegate to formatter immediately to show "Force Generation" button
        if not rows:
             lang = context.get('lang', 'es')
             return self.formatter.format_response(intent_data, rows, ejercicio, limit, lang=lang)

        # Check if implicitly report (e.g. from router ReportHandler intent)
        # OR if logic suggests report? For now explicit intent or parameter.
        if intent_data.get('type') == 'report':
            is_detailed = True

        if not is_detailed:
            # Standard List
            lang = context.get('lang', 'es')
            return self.formatter.format_response(intent_data, rows, ejercicio, limit, lang=lang)
            
        # --- Deep Dive Report Mode ---
        # Pass context to allow AI Analysis
        return self.generate_deep_dive_report(rows, intent_data, context)
