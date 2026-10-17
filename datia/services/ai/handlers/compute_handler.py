from datia.services.ai.handlers.base import BaseHandler
from datia.services.ai.compute_runtime import build_code, run_snippet
from datia.services.ai.dsl_query import DSLQueryExecutor
from datia.services.ai.language import LanguageService
import uuid
from django.conf import settings
import os

class PythonComputeHandler(BaseHandler):
    def _build_compute_dsl(self, question: str, empresa: int, ejercicio: int):
        q = question.lower()
        if 'media mov' in q or 'moving average' in q:
            return {"compute": "moving_average", "args": {"window": 3}, "input": "sales_by_month", "output": "sales_ma3"}
        if 'ratio' in q and 'ingres' in q and 'gasto' in q:
            return {"compute": "ratio", "args": {"a": "income_by_month", "b": "expense_by_month"}, "output": "ratio_ie"}
        if 'normaliz' in q:
            return {"compute": "normalize", "input": "series", "output": "series_norm"}
        return {"compute": "moving_average", "args": {"window": 3}, "input": "sales_by_month", "output": "sales_ma3"}

    def _resolve_inputs(self, dsl, empresa: int, ejercicio: int):
        inputs = {}
        target = dsl.get('input')
        if target == 'sales_by_month' or dsl.get('args', {}).get('a') == 'income_by_month' or dsl.get('args', {}).get('b') == 'expense_by_month':
            dsl_month = {
                "source": "metrics_mensual",
                "filters": [],
                "group_by": ["mes"],
                "aggregations": [{"field": "importe_neto_total", "func": "sum", "alias": "val"}],
                "order_by": [{"field": "mes", "dir": "asc"}],
                "limit": 12,
                "time": {"group": "month"}
            }
            rows = DSLQueryExecutor.compile_and_execute(dsl_month, empresa, ejercicio)
            sales = [r.get('val') or 0 for r in rows]
            inputs['sales_by_month'] = sales
        if dsl.get('args', {}).get('a') == 'income_by_month' or dsl.get('args', {}).get('b') == 'expense_by_month':
            dsl_fin = {
                "source": "financial_acumulados",
                "filters": [],
                "group_by": ["mes"],
                "aggregations": [{"field": "importe_neto_total", "func": "sum", "alias": "val"}],
                "order_by": [{"field": "mes", "dir": "asc"}],
                "limit": 12,
                "time": {"group": "month"}
            }
            rows = DSLQueryExecutor.compile_and_execute(dsl_fin, empresa, ejercicio)
            series = [r.get('val') or 0 for r in rows]
            inputs['income_by_month'] = series
            inputs['expense_by_month'] = series
        if target == 'series':
            inputs['series'] = inputs.get('sales_by_month') or []
        return inputs

    def _persist(self, empresa, ejercicio, question, dsl, code, result):
        rid = uuid.uuid4().hex[:8]
        try:
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        except Exception:
            ctx_dir = settings.BASE_DIR
        if not os.path.exists(ctx_dir):
            os.makedirs(ctx_dir, exist_ok=True)
        path = os.path.join(ctx_dir, f"datia_ai_compute_{empresa}_{ejercicio}_{rid}.json")
        payload = {"empresa": empresa, "ejercicio": ejercicio, "query_text": question, "dsl": dsl, "code": code, "result": result}
        try:
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass
        return {"id": rid, "path": path}

    def handle(self, intent_data, context):
        question = intent_data.get('query') or intent_data.get('question') or ''
        empresa = context.get('empresa')
        ejercicio = context.get('ejercicio')
        lang = context.get('lang', 'es')
        dsl = self._build_compute_dsl(question, empresa, ejercicio)
        inputs = self._resolve_inputs(dsl, empresa, ejercicio)
        code = build_code(dsl)
        result = run_snippet(code, inputs, timeout_ms=3000)
        meta = self._persist(empresa, ejercicio, question, dsl, code, result)
        text = LanguageService.get_text('generative_success', lang, question=question) if hasattr(LanguageService, 'get_text') else "Cálculo completado"
        rows = []
        out_key = dsl.get('output')
        vals = result.get(out_key) or []
        for i, v in enumerate(vals):
            rows.append({"label": i+1, "val": float(v) if v is not None else None})
        return {"type": "table", "text": text, "data": rows, "key": "compute", "source": "ai_compute", "path": meta["path"]}
