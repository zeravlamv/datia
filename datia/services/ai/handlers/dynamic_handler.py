
from typing import Dict, Any
from .base import BaseHandler
from datia.services.query_builder import QueryBuilder
from datia.services.security.sql_guard import SQLGuard

def _conservar_memoria(result, intent_data):
    if not isinstance(result, dict) or not isinstance(intent_data, dict):
        return result
    for clave in ('vinculo', 'lectura', 'hereda', 'sustituye', 'recorrido'):
        if clave in intent_data and clave not in result:
            result[clave] = intent_data[clave]
    return result


def _euros(valor):
    try:
        amount = f'{float(valor):,.2f}'
    except (TypeError, ValueError):
        amount = '0.00'
    return amount.replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'


class DynamicHandler(BaseHandler):
    def _responder_resumen(self, intent_data: Dict, context: Dict) -> Dict:
        lang = context.get('lang', 'es')
        anio = intent_data.get('anio') or context.get('ejercicio')
        sql = intent_data.get('sql') or ''
        try:
            SQLGuard.ensure_allowed(sql)
            filas = self.exec_sql(sql)
        except Exception as exc:
            return {'type': 'error', 'text': str(exc), 'sql': sql}
        total = 0
        if filas:
            primero = filas[0] if isinstance(filas[0], dict) else {}
            total = primero.get('val') if primero.get('val') is not None else primero.get('value')
        etiqueta = intent_data.get('label') or 'Resumen'
        texto = f'{etiqueta} {anio}: {_euros(total)}'
        partes = []
        for seccion in intent_data.get('secciones') or []:
            consulta = seccion.get('sql') or ''
            try:
                SQLGuard.ensure_allowed(consulta)
                filas_corte = self.exec_sql(consulta)
            except Exception:
                continue
            meta = {
                'type': 'table',
                'label': seccion.get('label') or 'Ranking',
                'sql': consulta,
                'keep_label': True,
                'lectura': intent_data.get('lectura'),
                'source': 'mapeo',
                'intent_meta': {'metric': seccion.get('metric') or 'sales'},
            }
            hecho = self.formatter.format_response(
                meta, filas_corte, anio, int(seccion.get('limit') or 10), lang=lang,
            )
            partes.append({
                'label': meta['label'],
                'text': hecho.get('text') or '',
                'data': hecho.get('data') or [],
                'chart_config': hecho.get('chart_config'),
                'metric': hecho.get('metric') or meta['intent_meta']['metric'],
            })
        return _conservar_memoria({
            'type': 'resumen',
            'answer': texto,
            'text': texto,
            'sql': sql,
            'anio': anio,
            'partes': partes,
            'source': 'mapeo',
            'label': etiqueta,
        }, intent_data)

    def handle(self, intent_data: Dict, context: Dict) -> Dict:
        if intent_data.get('secciones'):
            return self._responder_resumen(intent_data, context)
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
             return _conservar_memoria(
                 self.formatter.format_response(intent_data, rows, ejercicio, limit, lang=lang),
                 intent_data,
             )

        # Check if implicitly report (e.g. from router ReportHandler intent)
        # OR if logic suggests report? For now explicit intent or parameter.
        if intent_data.get('type') == 'report':
            is_detailed = True

        if not is_detailed:
            # Standard List
            lang = context.get('lang', 'es')
            result = self.formatter.format_response(intent_data, rows, ejercicio, limit, lang=lang)
            nota = intent_data.get('nota')
            if nota and isinstance(result, dict):
                result['answer'] = f"{result.get('answer') or ''} {nota}".strip()
                result['text'] = f"{result.get('text') or ''} {nota}".strip()
            return _conservar_memoria(result, intent_data)
            
        # --- Deep Dive Report Mode ---
        # Pass context to allow AI Analysis
        return self.generate_deep_dive_report(rows, intent_data, context)
