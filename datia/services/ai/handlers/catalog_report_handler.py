import re
import json
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal

from django.utils import translation

from .catalog_sections import (
    build_compras_top_proveedores,
    build_compras_resumen,
    build_compras_mensual,
    build_ventas_rango_periodos,
)

from datia.models.totales import (
    MetricsTotalesEmpresaEjercicio,
    MetricsTotalesEmpresaEjercicioMes,
    MetricsTotalesEmpresaEjercicioCliente,
    MetricsTotalesEmpresaEjercicioArticulo,
    MetricsTotalesEmpresaEjercicioCompra,
    MetricsTotalesEmpresaEjercicioCompraMes,
    MetricsTotalesEmpresaEjercicioProveedor,
    MetricsTotalesEmpresaEjercicioProveedorMes,
)
from datia.services.financial_service import FinancialService
from datia.factories import ServiceFactory

from .base import BaseHandler


def _to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return 0.0


def _months_es() -> List[str]:
    return ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']


class CatalogReportHandler(BaseHandler):
    TRANS = {
        'es': {
            'unknown': 'Desconocido',
            'sales_eur': 'Ventas (€)',
            'margin_pct': 'Margen (%)',
            'kpi_sales': 'Ingresos',
            'kpi_margin': 'Margen',
            'kpi_top1': 'Top 1',
            'kpi_top3': 'Top 3',
            'chart_top_clients': 'Mejores clientes',
            'chart_top_products': 'Mejores productos',
            'chart_sales_monthly': 'Ventas por mes',
            'chart_margin_monthly': 'Margen por mes',
            'chart_fin_monthly': 'Ingresos, Gastos y EBITDA',
            'chart_per100': 'Coste por cada 100',
        }
    }

    class Models:
        MetricsTotalesEmpresaEjercicioMes = MetricsTotalesEmpresaEjercicioMes
        MetricsTotalesEmpresaEjercicioCompraMes = MetricsTotalesEmpresaEjercicioCompraMes
        MetricsTotalesEmpresaEjercicioProveedor = MetricsTotalesEmpresaEjercicioProveedor

    def _t(self, key: str) -> str:
        lang = translation.get_language() or 'es'
        if lang not in self.TRANS:
            lang = 'es'
        return self.TRANS[lang].get(key, key)

    def _bar_h(self, labels: List[str], values: List[float], title: str, label: str) -> Dict[str, Any]:
        return {
            'type': 'bar',
            'data': {
                'labels': labels,
                'datasets': [{
                    'label': label,
                    'data': values,
                    'backgroundColor': ['#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe'],
                    'borderRadius': 4
                }]
            },
            'options': {
                'indexAxis': 'y',
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {'display': False},
                    'title': {'display': True, 'text': title}
                },
                'scales': {'x': {'grid': {'color': '#334155'}}}
            }
        }

    def _pie(self, labels: List[str], values: List[float], title: str) -> Dict[str, Any]:
        return {
            'type': 'doughnut',
            'data': {
                'labels': labels,
                'datasets': [{
                    'data': values,
                    'backgroundColor': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#22c55e'],
                    'borderWidth': 0
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {'position': 'right'},
                    'title': {'display': True, 'text': title}
                }
            }
        }

    def _line_dual(self, labels: List[str], a: List[float], b: List[float], title: str, la: str, lb: str) -> Dict[str, Any]:
        return {
            'type': 'line',
            'data': {
                'labels': labels,
                'datasets': [
                    {'label': la, 'data': a, 'borderColor': '#3b82f6', 'backgroundColor': 'rgba(59,130,246,0.2)', 'tension': 0.25},
                    {'label': lb, 'data': b, 'borderColor': '#10b981', 'backgroundColor': 'rgba(16,185,129,0.2)', 'tension': 0.25},
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': title}},
                'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
            }
        }

    def _concentration_pie(self, top: List[Tuple[str, float]], total: float, title: str) -> Dict[str, Any]:
        labels = []
        values = []
        acc = 0.0
        for name, val in top:
            labels.append(name)
            values.append(val)
            acc += val
        rest = max(0.0, total - acc)
        if rest > 0:
            labels.append('Resto')
            values.append(rest)
        return self._pie(labels, values, title)

    def _kpi(self, label: str, value: float, suffix: str = '€', color: str = '#e5e7eb', change: str = '') -> Dict[str, Any]:
        out = {'label': label, 'value': round(value, 2), 'suffix': suffix, 'color': color}
        if change:
            out['change'] = change
        return out

    def _year_ctx(self, context: Dict[str, Any]) -> Tuple[int, int, int]:
        empresa = context.get('empresa', 0)
        try:
            empresa = int(str(empresa).strip())
        except Exception:
            empresa = 0
        ejercicio = context.get('ejercicio')
        try:
            year = int(ejercicio)
        except Exception:
            import datetime
            year = datetime.datetime.now().year
        return empresa, year, year - 1

    def _augment_with_llm(self, payload: Dict[str, Any], intent_id: str, intent_data: Dict, context: Dict) -> Dict[str, Any]:
        fallback_answer = self._build_fallback_answer(payload, intent_id, context)
        if fallback_answer:
            payload["answer"] = fallback_answer
            payload["text"] = fallback_answer

        try:
            llm = ServiceFactory.get_report_llm_service(kind="financiera")
        except Exception:
            return payload
        if not hasattr(llm, "generate_text_with_policy"):
            return payload

        empresa = context.get("empresa")
        ejercicio = context.get("ejercicio")
        query = str((intent_data or {}).get("query") or "")

        intent_id = str(intent_id or "")
        kind = "financiera"
        if intent_id.startswith("ventas."):
            kind = "ventas"
        elif intent_id.startswith("compras."):
            kind = "ventas"
        elif intent_id.startswith("tesoreria."):
            kind = "financiera"
        elif intent_id.startswith("finanzas."):
            kind = "financiera"

        safe_keys = ["kpis", "table", "chart_config", "charts", "series", "totals", "data"]
        safe_payload = {}
        for k in safe_keys:
            if k in payload:
                safe_payload[k] = payload[k]

        summary = payload.get("answer") or payload.get("text") or ""

        try:
            ctx_json = json.dumps(safe_payload, ensure_ascii=False)
        except Exception:
            ctx_json = "{}"

        prompt = (
            "Actúa como Director Financiero (CFO). Responde siempre en español, con un tono claro, crítico y ejecutivo.\n"
            f"Consulta del usuario: {query}\n"
            f"Empresa: {empresa}, Ejercicio: {ejercicio}\n"
            f"Intento identificado: {intent_id}\n\n"
            "Resumen previo (puede estar vacío):\n"
            f"{summary}\n\n"
            "Contexto numérico (JSON):\n"
            f"{ctx_json}\n\n"
            "Tareas:\n"
            "- Escribe un resumen ejecutivo con 4 bloques: Situación actual, Variaciones vs año anterior, Riesgos/Oportunidades, Acciones recomendadas.\n"
            "- Usa cifras del contexto en cada bloque y menciona variaciones relevantes.\n"
            "- Sé específico: evita frases vacías como 'crecimiento sólido' si no explicas contra qué y cuánto.\n"
            "- Si los datos son débiles o contradictorios, dilo explícitamente.\n"
            "- Máximo 220 palabras.\n"
            "No inventes cifras que no aparezcan en el contexto. No repitas literalmente el JSON."
        )

        try:
            res = llm.generate_text_with_policy(
                prompt=prompt,
                kind=kind,
                requested_model=None,
                deadline=300,
                req_id=None,
                prefer_no_stream=True,
                allow_degrade=True,
            )
        except Exception:
            return payload

        if isinstance(res, dict) and res.get("status") == "ok" and res.get("text"):
            text = str(res.get("text"))
            payload["answer"] = text
            payload["text"] = text
        return payload

    def _build_fallback_answer(self, payload: Dict[str, Any], intent_id: str, context: Dict) -> str:
        empresa = context.get("empresa")
        ejercicio = context.get("ejercicio")
        if intent_id == "finanzas.resumen_ejercicio":
            totals = payload.get("totals") or {}
            snapshot = (totals.get("snapshot") or {}) if isinstance(totals, dict) else {}
            py = (snapshot.get("py") or {}) if isinstance(snapshot, dict) else {}
            var = (snapshot.get("var") or {}) if isinstance(snapshot, dict) else {}
            ratios = ((totals.get("ratios") or {}).get("ratios") or {}) if isinstance(totals, dict) else {}

            def fnum(v):
                try:
                    return f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                except Exception:
                    return "0,00"

            ingresos = float(snapshot.get("ingresos") or 0)
            gastos = float(snapshot.get("gastos") or 0)
            resultado = float(snapshot.get("resultado") or 0)
            otros_ing = float(snapshot.get("otros_ingresos") or 0)
            otros_gast = float(snapshot.get("otros_gastos") or 0)
            ing_py = float(py.get("ingresos") or 0)
            res_py = float(py.get("resultado") or 0)
            ing_pct = float(((var.get("ingresos") or {}).get("pct")) or 0)
            res_pct = float(((var.get("resultado") or {}).get("pct")) or 0)
            margen = float(((ratios.get("margen_ebitda") or {}).get("value")) or 0)
            liquidez = float(((ratios.get("liquidez_corriente") or {}).get("value")) or 0)
            endeud = float(((ratios.get("endeudamiento") or {}).get("value")) or 0)
            cobro = float(((ratios.get("periodo_cobro") or {}).get("value")) or 0)
            pago = float(((ratios.get("periodo_pago") or {}).get("value")) or 0)

            return (
                f"Situación actual: en {ejercicio}, la empresa {empresa} registra ingresos de {fnum(ingresos)} €,"
                f" gastos de {fnum(gastos)} € y un resultado de explotación de {fnum(resultado)} €. "
                f"Además, los otros ingresos suman {fnum(otros_ing)} € y los otros gastos {fnum(otros_gast)} €.\n\n"
                f"Variación vs año anterior: frente a {ejercicio - 1}, los ingresos cambian un {fnum(ing_pct)} %"
                f" ({fnum(ingresos - ing_py)} €) y el resultado de explotación cambia un {fnum(res_pct)} %"
                f" ({fnum(resultado - res_py)} €).\n\n"
                f"Riesgos y oportunidades: el margen EBITDA se sitúa en {fnum(margen)} %, la liquidez corriente en {fnum(liquidez)}x"
                f" y el endeudamiento en {fnum(endeud)} %. El periodo medio de cobro es {fnum(cobro)} días"
                f" y el de pago {fnum(pago)} días.\n\n"
                f"Acciones recomendadas: revisar la estructura de otros gastos, defender margen en líneas rentables"
                f" y ajustar circulante para reducir tensión entre cobro y pago."
            )

        if intent_id == "ventas.top_clientes":
            rows = (((payload.get("table") or {}).get("rows")) or [])
            if rows:
                top = rows[0]
                top3 = sum(float((r[1] or 0)) for r in rows[:3])
                total = sum(float((r[1] or 0)) for r in rows)
                c = str(top[0] or "")
                v = float(top[1] or 0)
                py = float(top[2] or 0)
                varpct = float(top[3] or 0)
                return (
                    f"Ranking comercial {ejercicio}: el cliente líder es {c} con ventas de {v:,.2f} €,"
                    f" frente a {py:,.2f} € del ejercicio anterior ({varpct:.1f} %). "
                    f"Los tres primeros clientes concentran {top3:,.2f} € sobre un total analizado de {total:,.2f} €. "
                    f"Conviene revisar concentración, evolución del margen y dependencia comercial sobre la cabecera del ranking."
                )

        if intent_id == "ventas.resumen_ejercicio":
            kpis = payload.get("kpis") or []
            if kpis:
                k = kpis[0]
                return (
                    f"Ventas {ejercicio}: volumen neto de {k.get('value', 0):,.2f} {k.get('suffix', '')}. "
                    f"La evolución interanual es {k.get('change', 0)} %. "
                    f"El análisis debe centrarse en estacionalidad mensual, concentración de clientes y protección del margen."
                )

        return str(payload.get("answer") or payload.get("text") or "")

    @staticmethod
    def _parse_years_from_query(q: str) -> List[int]:
        s = str(q or '')
        years = []
        for m in re.finditer(r"\b(20\d{2})\b", s):
            try:
                y = int(m.group(1))
            except Exception:
                continue
            if 2000 <= y <= 2099 and y not in years:
                years.append(y)
        return years

    def handle(self, intent_data: Dict, context: Dict) -> Dict[str, Any]:
        intent_id = (intent_data or {}).get('intent_id') or ''
        empresa, year, prev = self._year_ctx(context)
        limit = 10
        try:
            limit = int(context.get('limit') or 10)
        except Exception:
            limit = 10
        try:
            q = str((intent_data or {}).get('query') or '')
            m = re.search(r"\b(?:top|mejores|peores|ranking|los|las)\s+(\d{1,3})\b", q, re.IGNORECASE)
            if not m:
                m = re.search(r"\b(\d{1,3})\s+(?:peores|mejores|primeros|primeras)\b", q, re.IGNORECASE)
            if m:
                n = int(m.group(1))
                if 1 <= n <= 100:
                    limit = n
        except Exception:
            pass
        if limit <= 0:
            limit = 10
        if intent_id == 'tesoreria.resumen':
            payload = self._tesoreria_resumen(empresa, year)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'presupuestos.comparativa':
            q = str((intent_data or {}).get('query') or '')
            years = self._parse_years_from_query(q)
            y = years[0] if years else year
            payload = self._presupuestos_comparativa(empresa, y)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'financiera.ratios':
            q = str((intent_data or {}).get('query') or '')
            years = self._parse_years_from_query(q)
            if len(years) >= 2:
                payload = self._financiera_ratios(empresa, years[0], years[1])
                payload = self._augment_with_llm(payload, intent_id, intent_data, context)
                return self._with_text(payload)
            if len(years) == 1:
                payload = self._financiera_ratios(empresa, years[0], None)
                payload = self._augment_with_llm(payload, intent_id, intent_data, context)
                return self._with_text(payload)
            payload = self._financiera_ratios(empresa, year, None)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'tesoreria.forecast':
            payload = self._tesoreria_forecast(empresa, year)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'tesoreria.pool_bancario':
            payload = self._tesoreria_pool_bancario(empresa, year)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'tesoreria.caja_mensual':
            payload = self._tesoreria_caja_mensual(empresa, year)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'ventas.resumen_ejercicio':
            payload = self._ventas_resumen(empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        worst = bool(re.search(r"\b(peores|peor|menores|menor)\b", str((intent_data or {}).get('query') or ''), re.IGNORECASE))
        if intent_id == 'ventas.top_clientes':
            payload = self._ventas_top_clientes(empresa, year, prev, limit, worst=worst)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'ventas.top_productos':
            payload = self._ventas_top_productos(empresa, year, prev, limit, worst=worst)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'ventas.ventas_mensual':
            payload = self._ventas_mensual(empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'ventas.margen_mensual':
            payload = self._margen_mensual(empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'ventas.rango_periodos':
            q = (intent_data or {}).get('query') or ''
            payload = build_ventas_rango_periodos(self, q, empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'finanzas.resumen_ejercicio':
            payload = self._finanzas_resumen(empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'finanzas.per100':
            payload = self._finanzas_per100(empresa, year)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'compras.top_proveedores':
            payload = build_compras_top_proveedores(self, empresa, year, prev, limit, worst=worst)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'compras.resumen_ejercicio':
            payload = build_compras_resumen(self, empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        if intent_id == 'compras.compras_mensual':
            payload = build_compras_mensual(self, empresa, year, prev)
            payload = self._augment_with_llm(payload, intent_id, intent_data, context)
            return self._with_text(payload)
        payload = {'type': 'text', 'answer': 'No he podido resolver esta consulta con el catálogo mínimo.'}
        payload = self._augment_with_llm(payload, intent_id, intent_data, context)
        return self._with_text(payload)

    def _with_text(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {'type': 'text', 'text': 'Respuesta inválida', 'answer': 'Respuesta inválida'}
        ans = payload.get('answer') or payload.get('text') or ''
        payload['answer'] = ans
        payload['text'] = ans
        payload.setdefault('sql', None)
        payload.setdefault('source', 'catalog')
        return payload

    def _tesoreria_resumen(self, empresa: int, year: int) -> Dict[str, Any]:
        svc = FinancialService()
        snap = svc.get_treasury_snapshot(empresa, year) or {}
        k = (snap.get('kpis') or {}) if isinstance(snap, dict) else {}
        cash = float(k.get('cash') or 0)
        receivables = float(k.get('receivables') or 0)
        payables = float(k.get('payables') or 0)
        unpaid = float(k.get('unpaid_receivables') or 0)
        dso = float(k.get('dso') or 0)
        dpo = float(k.get('dpo') or 0)
        wc = float(k.get('working_capital') or 0)
        cartera_total = float(k.get('cartera_importe_total') or 0)
        cartera_cobros = float(k.get('cartera_importe_cobros') or 0)
        cartera_pagos = float(k.get('cartera_importe_pagos') or 0)
        cartera_overdue_90 = float(k.get('cartera_importe_overdue_90') or 0)

        forecast = svc.get_treasury_forecast(empresa, year, months=6) or {}
        fc_series = forecast.get('forecast') or []
        labels = [str(x.get('period') or '') for x in fc_series]
        inflow = [float(x.get('inflow') or 0) for x in fc_series]
        outflow = [float(x.get('outflow') or 0) for x in fc_series]
        balance = [float(x.get('balance') or 0) for x in fc_series]

        chart_forecast = {
            'type': 'line',
            'data': {
                'labels': labels,
                'datasets': [
                    {'label': 'Cobros', 'data': inflow, 'borderColor': '#10b981', 'backgroundColor': 'rgba(16,185,129,0.12)', 'tension': 0.25},
                    {'label': 'Pagos', 'data': outflow, 'borderColor': '#ef4444', 'backgroundColor': 'rgba(239,68,68,0.10)', 'tension': 0.25},
                    {'label': 'Caja proyectada', 'data': balance, 'borderColor': '#3b82f6', 'backgroundColor': 'rgba(59,130,246,0.12)', 'tension': 0.25},
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': 'Previsión tesorería (6 meses)'}},
                'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
            }
        }

        top_clients = ((snap.get('charts') or {}).get('top_clients') or []) if isinstance(snap, dict) else []
        top_suppliers = ((snap.get('charts') or {}).get('top_suppliers') or []) if isinstance(snap, dict) else []
        top_banks = ((snap.get('charts') or {}).get('banks') or []) if isinstance(snap, dict) else []

        def to_bar(items, title):
            data = [(str(i.get('name') or ''), float(i.get('value') or 0)) for i in (items or []) if isinstance(i, dict)]
            data = [(n, v) for (n, v) in data if n]
            labels_b = [n[:18] + '...' if len(n) > 18 else n for (n, _) in data[:10]]
            values_b = [v for (_, v) in data[:10]]
            return self._bar_h(labels_b[::-1], values_b[::-1], title, '€') if labels_b else None

        chart_clients = to_bar(top_clients, 'Top cobros pendientes (cliente)')
        chart_suppliers = to_bar(top_suppliers, 'Top pagos pendientes (proveedor)')
        chart_banks = to_bar(top_banks, 'Bancos (saldo 572)')

        table_rows = []
        for x in fc_series:
            table_rows.append([
                str(x.get('period') or ''),
                round(float(x.get('inflow') or 0), 2),
                round(float(x.get('outflow') or 0), 2),
                round(float(x.get('balance') or 0), 2),
                round(float(x.get('ratio') or 0), 2),
            ])

        cartera_det = self._get_cartera_detail_tables(empresa, year, limit=30)
        aging = (snap.get('aging') or {}) if isinstance(snap, dict) else {}
        ar = (aging.get('receivables') or {}) if isinstance(aging, dict) else {}
        ap = (aging.get('payables') or {}) if isinstance(aging, dict) else {}
        aging_labels = ['Vencido', '0-30', '30-60', '60-90', '>90']
        aging_values = [
            float(ar.get('overdue') or 0),
            float(ar.get('0-30') or 0),
            float(ar.get('30-60') or 0),
            float(ar.get('60-90') or 0),
            float(ar.get('>90') or 0),
        ]
        chart_aging = self._pie(aging_labels, aging_values, 'Aging cobros (pendiente)')

        kpis = [
            {'label': 'Caja', 'value': round(cash, 2), 'suffix': '€', 'color': '#3b82f6'},
            {'label': 'Cobros pendientes', 'value': round(receivables, 2), 'suffix': '€', 'color': '#10b981'},
            {'label': 'Pagos pendientes', 'value': round(payables, 2), 'suffix': '€', 'color': '#ef4444'},
            {'label': 'Impagado vencido', 'value': round(unpaid, 2), 'suffix': '€', 'color': '#f59e0b'},
            {'label': 'Working Capital', 'value': round(wc, 2), 'suffix': '€', 'color': '#a78bfa'},
            {'label': 'DSO / DPO', 'value': 0, 'suffix': '', 'color': '#e5e7eb', 'change': f"{round(dso, 0)}d / {round(dpo, 0)}d"},
            {'label': 'Cartera (importe)', 'value': round(cartera_total, 2), 'suffix': '€', 'color': '#22c55e'},
            {'label': 'Cartera cobros', 'value': round(cartera_cobros, 2), 'suffix': '€', 'color': '#10b981'},
            {'label': 'Cartera pagos', 'value': round(cartera_pagos, 2), 'suffix': '€', 'color': '#ef4444'},
            {'label': 'Vencido >90d', 'value': round(cartera_overdue_90, 2), 'suffix': '€', 'color': '#f97316'},
        ]

        tables = [
            {'title': 'Previsión (6 meses desde hoy)', 'columns': ['Periodo', 'Cobros', 'Pagos', 'Caja', 'Ratio liquidez'], 'rows': table_rows},
        ]
        tables.extend(cartera_det.get('tables') or [])
        if (cartera_det.get('schedule') or {}).get('rows'):
            tables.append(cartera_det.get('schedule'))

        chart_main = chart_forecast
        table_main = {'title': 'Previsión (6 meses desde hoy)', 'columns': ['Periodo', 'Cobros', 'Pagos', 'Caja', 'Ratio liquidez'], 'rows': table_rows}
        try:
            from datetime import date
            today = date.today()
            if int(year) != int(today.year):
                sched = cartera_det.get('schedule') or {}
                sched_rows = sched.get('rows') or []
                months = _months_es()
                cobros = []
                pagos = []
                labels_m = []
                for i in range(12):
                    labels_m.append(months[i])
                    try:
                        cobros.append(float((sched_rows[i] or [None, 0])[1] or 0))
                    except Exception:
                        cobros.append(0.0)
                    try:
                        pagos.append(float((sched_rows[i] or [None, 0, 0])[2] or 0))
                    except Exception:
                        pagos.append(0.0)
                neto = [c - p for c, p in zip(cobros, pagos)]
                chart_main = {
                    'type': 'bar',
                    'data': {
                        'labels': labels_m,
                        'datasets': [
                            {'label': 'Cobros', 'data': cobros, 'backgroundColor': 'rgba(16,185,129,0.30)', 'borderColor': '#10b981'},
                            {'label': 'Pagos', 'data': pagos, 'backgroundColor': 'rgba(239,68,68,0.26)', 'borderColor': '#ef4444'},
                            {'label': 'Neto', 'data': neto, 'backgroundColor': 'rgba(59,130,246,0.20)', 'borderColor': '#3b82f6'},
                        ]
                    },
                    'options': {
                        'responsive': True,
                        'maintainAspectRatio': False,
                        'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': f'Calendario de vencimientos (pendiente) {year}'}},
                        'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
                    }
                }
                table_main = sched
        except Exception:
            pass

        out = {
            'type': 'report',
            'key': 'tesoreria_resumen',
            'kpis': kpis,
            'answer': (
                f"Informe de tesorería (caja, cartera y previsión) del ejercicio {year}. "
                f"Cartera pendiente (importe): {round(cartera_total, 2)} €; cobros {round(cartera_cobros, 2)} €; pagos {round(cartera_pagos, 2)} €."
            ),
            'chart_config': chart_main,
            'table': table_main,
            'tables': tables,
            'chart_concentration': chart_aging,
        }
        if chart_clients:
            out['chart_pareto_clients'] = chart_clients
        if chart_suppliers:
            out['chart_pareto_suppliers'] = chart_suppliers
        if chart_banks:
            out['chart_banks'] = chart_banks
        return out

    def _get_cartera_detail_tables(self, empresa: int, year: int, limit: int = 30) -> Dict[str, Any]:
        from datetime import date
        from datia.models.financial import DatiaCarteraEfectos, DatiaPlanCuentas

        today = date.today()
        qs = DatiaCarteraEfectos.objects.filter(empresa=empresa, ejercicio=year).exclude(
            estado__in=['COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO']
        )

        rows = list(qs.values('codigo_titular', 'fecha_vencimiento', 'importe', 'importe_cobrado', 'estado', 'tipo_efecto'))

        def pending(r):
            return float(r.get('importe') or 0) - float(r.get('importe_cobrado') or 0)

        active = []
        for r in rows:
            p = pending(r)
            if p <= 0.01:
                continue
            active.append(r)

        codes = []
        for r in active:
            c = str(r.get('codigo_titular') or '').strip()
            if c:
                codes.append(c)
        codes = list(dict.fromkeys(codes))
        names = {}
        if codes:
            for p in DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=year, codigo__in=codes).values('codigo', 'descripcion'):
                names[str(p.get('codigo') or '')] = str(p.get('descripcion') or '')

        def build_table(tipo, title):
            items = [r for r in active if (str(r.get('tipo_efecto') or '').upper() == tipo)]
            items.sort(key=lambda r: pending(r), reverse=True)
            out_rows = []
            for r in items[:max(10, int(limit or 30))]:
                code = str(r.get('codigo_titular') or '').strip()
                name = names.get(code, code)
                vto = r.get('fecha_vencimiento')
                estado = str(r.get('estado') or '')
                p = pending(r)
                days = ''
                try:
                    if vto:
                        days = (vto - today).days
                except Exception:
                    days = ''
                out_rows.append([
                    name,
                    code,
                    str(vto) if vto else '',
                    float(days) if isinstance(days, int) else '',
                    round(float(p), 2),
                    estado
                ])
            return {'title': title, 'columns': ['Titular', 'Código', 'Vencimiento', 'Días', 'Pendiente €', 'Estado'], 'rows': out_rows}

        cobros_table = build_table('C', 'Cartera: cobros pendientes (Top)')
        pagos_table = build_table('P', 'Cartera: pagos pendientes (Top)')

        by_month_c = [0.0] * 12
        by_month_p = [0.0] * 12
        out_of_year = 0.0
        no_date = 0.0
        for r in active:
            vto = r.get('fecha_vencimiento')
            p = pending(r)
            if not vto:
                no_date += p
                continue
            if int(getattr(vto, 'year', 0) or 0) != int(year):
                out_of_year += p
                continue
            m = int(getattr(vto, 'month', 0) or 0)
            if 1 <= m <= 12:
                if str(r.get('tipo_efecto') or '').upper() == 'C':
                    by_month_c[m - 1] += p
                else:
                    by_month_p[m - 1] += p

        sched_rows = []
        months = _months_es()
        for i in range(12):
            sched_rows.append([months[i], round(by_month_c[i], 2), round(by_month_p[i], 2), round(by_month_c[i] - by_month_p[i], 2)])
        sched_rows.append(['Sin vencimiento', round(no_date, 2), 0.0, round(no_date, 2)])
        if out_of_year > 0:
            sched_rows.append([f'Vencimientos fuera {year}', round(out_of_year, 2), 0.0, round(out_of_year, 2)])

        schedule = {'title': f'Calendario de vencimientos (pendiente) {year}', 'columns': ['Mes', 'Cobros €', 'Pagos €', 'Neto €'], 'rows': sched_rows}

        return {
            'tables': [t for t in [cobros_table, pagos_table] if (t.get('rows') or [])],
            'schedule': schedule
        }

    def _tesoreria_forecast(self, empresa: int, year: int) -> Dict[str, Any]:
        svc = FinancialService()
        forecast = svc.get_treasury_forecast(empresa, year, months=6) or {}
        fc_series = forecast.get('forecast') or []
        labels = [str(x.get('period') or '') for x in fc_series]
        inflow = [float(x.get('inflow') or 0) for x in fc_series]
        outflow = [float(x.get('outflow') or 0) for x in fc_series]
        balance = [float(x.get('balance') or 0) for x in fc_series]
        chart = {
            'type': 'line',
            'data': {
                'labels': labels,
                'datasets': [
                    {'label': 'Cobros', 'data': inflow, 'borderColor': '#10b981', 'backgroundColor': 'rgba(16,185,129,0.12)', 'tension': 0.25},
                    {'label': 'Pagos', 'data': outflow, 'borderColor': '#ef4444', 'backgroundColor': 'rgba(239,68,68,0.10)', 'tension': 0.25},
                    {'label': 'Caja proyectada', 'data': balance, 'borderColor': '#3b82f6', 'backgroundColor': 'rgba(59,130,246,0.12)', 'tension': 0.25},
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': 'Previsión tesorería (6 meses)'}},
                'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
            }
        }
        rows = []
        for x in fc_series:
            rows.append([
                str(x.get('period') or ''),
                round(float(x.get('inflow') or 0), 2),
                round(float(x.get('outflow') or 0), 2),
                round(float(x.get('balance') or 0), 2),
                round(float(x.get('ratio') or 0), 2),
            ])
        start_cash = float(forecast.get('start_cash') or 0)
        kpis = [
            {'label': 'Caja inicial', 'value': round(start_cash, 2), 'suffix': '€', 'color': '#3b82f6'},
            {'label': 'Cobros (sum)', 'value': round(float((forecast.get('validation') or {}).get('sum_inflow') or 0), 2), 'suffix': '€', 'color': '#10b981'},
            {'label': 'Pagos (sum)', 'value': round(float((forecast.get('validation') or {}).get('sum_outflow') or 0), 2), 'suffix': '€', 'color': '#ef4444'},
        ]
        return {
            'type': 'report',
            'key': 'tesoreria_forecast',
            'kpis': kpis,
            'answer': f"Previsión de tesorería (cobros/pagos) para {year}.",
            'chart_config': chart,
            'table': {'title': 'Previsión (mensual)', 'columns': ['Periodo', 'Cobros', 'Pagos', 'Caja', 'Ratio liquidez'], 'rows': rows},
        }

    def _tesoreria_caja_mensual(self, empresa: int, year: int) -> Dict[str, Any]:
        from django.db.models import Sum
        from datia.models.financial import DatiaAcumuladosConta
        labels = _months_es()
        vals = [0.0] * 12
        qs = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=year, periodo__gte=1, periodo__lte=12, cuenta__startswith='57'
        ).values('periodo').annotate(total=Sum('saldo'))
        for row in qs:
            p = int(row.get('periodo') or 0)
            if 1 <= p <= 12:
                vals[p - 1] = float(row.get('total') or 0.0)
        chart = {
            'type': 'line',
            'data': {'labels': labels, 'datasets': [{'label': 'Caja (57)', 'data': [round(float(v or 0), 2) for v in vals], 'borderColor': '#3b82f6', 'backgroundColor': 'rgba(59,130,246,0.12)', 'tension': 0.25}]},
            'options': {'responsive': True, 'maintainAspectRatio': False, 'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': f'Caja mensual (57) {year}'}}, 'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}}
        }
        return {
            'type': 'report',
            'key': 'tesoreria_caja_mensual',
            'kpis': [{'label': 'Caja (fin año)', 'value': round(sum(vals), 2), 'suffix': '€', 'color': '#3b82f6'}],
            'answer': f"Saldos mensuales de caja (grupo 57) para {year}.",
            'chart_config': chart,
        }

    def _tesoreria_pool_bancario(self, empresa: int, year: int) -> Dict[str, Any]:
        from datia.services.banking_service import BankingService
        svc = BankingService()
        s = svc.get_summary(empresa, year) or {}
        tot = (s.get('totales') or {}) if isinstance(s, dict) else {}
        limite = float(tot.get('limite') or 0)
        dispuesto = float(tot.get('dispuesto') or 0)
        disponible = float(tot.get('disponible') or 0)
        util = float(tot.get('utilizacion_pct') or 0)

        banks = s.get('por_banco') or []
        banks = [b for b in banks if isinstance(b, dict)]
        banks.sort(key=lambda x: float(x.get('limite') or 0), reverse=True)
        b_labels = [str(b.get('bank') or b.get('bank_id') or '') for b in banks[:10] if (b.get('bank') or b.get('bank_id'))]
        b_vals = [float(b.get('limite') or 0) for b in banks[:10] if (b.get('bank') or b.get('bank_id'))]
        chart_banks = self._bar_h(b_labels[::-1], b_vals[::-1], 'Límites por banco', '€') if b_labels else None

        tipos = s.get('por_tipo') or []
        tipos = [t for t in tipos if isinstance(t, dict)]
        tipos.sort(key=lambda x: float(x.get('limite') or 0), reverse=True)
        t_labels = [str(t.get('tipo') or '') for t in tipos[:10] if t.get('tipo')]
        t_vals = [float(t.get('limite') or 0) for t in tipos[:10] if t.get('tipo')]
        chart_tipos = self._bar_h(t_labels[::-1], t_vals[::-1], 'Límites por tipo', '€') if t_labels else None

        rows = []
        for it in (s.get('items') or [])[:50]:
            if not isinstance(it, dict):
                continue
            rows.append([
                str(it.get('bank') or ''),
                str(it.get('tipo') or ''),
                str(it.get('producto') or ''),
                round(float(it.get('limite') or 0), 2),
                round(float(it.get('dispuesto') or 0), 2),
                round(float(it.get('disponible') or 0), 2),
            ])

        kpis = [
            {'label': 'Límite', 'value': round(limite, 2), 'suffix': '€', 'color': '#3b82f6'},
            {'label': 'Dispuesto', 'value': round(dispuesto, 2), 'suffix': '€', 'color': '#ef4444'},
            {'label': 'Disponible', 'value': round(disponible, 2), 'suffix': '€', 'color': '#10b981'},
            {'label': 'Utilización', 'value': round(util, 2), 'suffix': '%', 'color': '#f59e0b'},
        ]

        out = {
            'type': 'report',
            'key': 'tesoreria_pool_bancario',
            'kpis': kpis,
            'answer': f"Pool bancario del ejercicio {year}.",
            'table': {'title': 'Instrumentos', 'columns': ['Banco', 'Tipo', 'Producto', 'Límite', 'Dispuesto', 'Disponible'], 'rows': rows},
        }
        if chart_banks:
            out['chart_pareto_banks'] = chart_banks
        if chart_tipos:
            out['chart_pareto_types'] = chart_tipos
        return out

    def _presupuestos_comparativa(self, empresa: int, year: int) -> Dict[str, Any]:
        svc = FinancialService()
        data = svc.get_budget_comparison_data(empresa, year) or {}
        table = data.get('table') or []
        charts = data.get('charts') or {}
        monthly = (charts.get('monthly') or {}) if isinstance(charts, dict) else {}

        real_inc = [float(x or 0) for x in (monthly.get('real_income') or [0]*12)]
        bud_inc = [float(x or 0) for x in (monthly.get('budget_income') or [0]*12)]
        real_exp = [float(x or 0) for x in (monthly.get('real_expense') or [0]*12)]
        bud_exp = [float(x or 0) for x in (monthly.get('budget_expense') or [0]*12)]

        def ssum(arr):
            return float(sum(float(x or 0) for x in (arr or [])))

        real_inc_t = ssum(real_inc)
        bud_inc_t = ssum(bud_inc)
        real_exp_t = ssum(real_exp)
        bud_exp_t = ssum(bud_exp)
        real_net = real_inc_t - real_exp_t
        bud_net = bud_inc_t - bud_exp_t
        dev_inc = real_inc_t - bud_inc_t
        dev_exp = real_exp_t - bud_exp_t
        dev_net = real_net - bud_net

        kpis = [
            {'label': 'Ingresos real', 'value': round(real_inc_t, 2), 'suffix': '€', 'color': '#3b82f6', 'change': f"vs presupuesto: {round(dev_inc, 2)} €"},
            {'label': 'Ingresos presupuesto', 'value': round(bud_inc_t, 2), 'suffix': '€', 'color': '#60a5fa'},
            {'label': 'Gastos real', 'value': round(real_exp_t, 2), 'suffix': '€', 'color': '#ef4444', 'change': f"vs presupuesto: {round(dev_exp, 2)} €"},
            {'label': 'Gastos presupuesto', 'value': round(bud_exp_t, 2), 'suffix': '€', 'color': '#fca5a5'},
            {'label': 'Neto real', 'value': round(real_net, 2), 'suffix': '€', 'color': '#22c55e', 'change': f"vs presupuesto: {round(dev_net, 2)} €"},
            {'label': 'Neto presupuesto', 'value': round(bud_net, 2), 'suffix': '€', 'color': '#86efac'},
        ]

        months = _months_es()
        net_real_m = [round(real_inc[i] - real_exp[i], 2) for i in range(12)]
        net_bud_m = [round(bud_inc[i] - bud_exp[i], 2) for i in range(12)]
        chart = {
            'type': 'line',
            'data': {
                'labels': months,
                'datasets': [
                    {'label': 'Neto real', 'data': net_real_m, 'borderColor': '#22c55e', 'backgroundColor': 'rgba(34,197,94,0.12)', 'tension': 0.25},
                    {'label': 'Neto presupuesto', 'data': net_bud_m, 'borderColor': '#86efac', 'backgroundColor': 'rgba(134,239,172,0.10)', 'tension': 0.25},
                    {'label': 'Ingresos real', 'data': [round(x,2) for x in real_inc], 'borderColor': '#3b82f6', 'backgroundColor': 'rgba(59,130,246,0.10)', 'tension': 0.25},
                    {'label': 'Gastos real', 'data': [round(x,2) for x in real_exp], 'borderColor': '#ef4444', 'backgroundColor': 'rgba(239,68,68,0.08)', 'tension': 0.25},
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': f'Presupuesto vs Real (mensual) {year}'}},
                'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
            }
        }

        rows = []
        for r in (table or []):
            if not isinstance(r, dict):
                continue
            rows.append([
                str(r.get('cuenta') or ''),
                str(r.get('descripcion') or ''),
                float(r.get('real') or 0),
                float(r.get('presupuesto') or 0),
                float(r.get('desviacion') or 0),
                float(r.get('desviacion_pct') or 0),
            ])

        rows.sort(key=lambda x: abs(float(x[4] or 0)), reverse=True)
        top = rows[:12]
        labels = [f"{x[0]} {x[1][:14]}" for x in top]
        vals = [float(x[4] or 0) for x in top]
        chart_dev = self._bar_h(labels[::-1], vals[::-1], 'Top desviaciones (Real - Presupuesto)', '€') if labels else None

        out = {
            'type': 'report',
            'key': 'presupuestos_comparativa',
            'kpis': kpis,
            'answer': f"Comparativa Presupuesto vs Real del ejercicio {year}.",
            'chart_config': chart,
            'table': {'title': 'Presupuesto vs Real (Top desviaciones)', 'columns': ['Cuenta', 'Descripción', 'Real', 'Presupuesto', 'Desviación', 'Desv %'], 'rows': top},
            'tables': [{'title': 'Presupuesto vs Real (todas las cuentas)', 'columns': ['Cuenta', 'Descripción', 'Real', 'Presupuesto', 'Desviación', 'Desv %'], 'rows': rows[:250]}],
        }
        if chart_dev:
            out['chart_pareto'] = chart_dev
        return out

    def _financiera_ratios(self, empresa: int, year: int, year_cmp: int = None) -> Dict[str, Any]:
        svc = FinancialService()
        data_a = svc.get_ratios_extended(empresa, year) or {}
        ratios_a = data_a.get('ratios') or {}
        base_a = data_a.get('base') or {}
        year_cmp = int(year_cmp) if year_cmp else None
        data_b = svc.get_ratios_extended(empresa, year_cmp) if year_cmp else None
        ratios_b = (data_b or {}).get('ratios') or {}
        base_b = (data_b or {}).get('base') or {}

        rows = []
        order = [
            ('liquidez', 'liquidez_corriente', 'Liquidez corriente', ''),
            ('liquidez', 'test_acido', 'Test ácido', ''),
            ('liquidez', 'disponibilidad', 'Disponibilidad', ''),
            ('liquidez', 'fondo_maniobra', 'Fondo de maniobra', '€'),
            ('solvencia', 'endeudamiento', 'Endeudamiento', '%'),
            ('solvencia', 'autonomia', 'Autonomía', ''),
            ('solvencia', 'garantia', 'Garantía', ''),
            ('solvencia', 'calidad_deuda', 'Calidad de deuda', '%'),
            ('gestion', 'rotacion_activos', 'Rotación de activos', 'x'),
            ('gestion', 'rotacion_stock', 'Rotación de stock', 'x'),
            ('gestion', 'periodo_cobro', 'Periodo de cobro', 'd'),
            ('gestion', 'periodo_pago', 'Periodo de pago', 'd'),
            ('rentabilidad', 'margen_bruto', 'Margen bruto', '%'),
            ('rentabilidad', 'margen_neto', 'Margen neto', '%'),
            ('rentabilidad', 'roa', 'ROA', '%'),
            ('rentabilidad', 'roe', 'ROE', '%'),
            ('cobertura', 'cobertura_interes', 'Cobertura de interés', 'x'),
            ('cobertura', 'cobertura_deuda', 'Cobertura de deuda', 'x'),
            ('cobertura', 'margen_ebitda', 'Margen EBITDA', '%'),
        ]

        def _fmt_es(num: float, dec: int = 2) -> str:
            try:
                s = f"{float(num or 0):,.{int(dec)}f}"
                return s.replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return str(num)

        def _unit_from(v: Dict[str, Any], hint: str) -> str:
            if hint:
                return hint
            u = str(v.get('unit') or '')
            if u == 'percent':
                return '%'
            if u == 'days':
                return 'd'
            if u == 'times':
                return 'x'
            if u == 'eur':
                return '€'
            return ''

        color_map = {
            'liquidez': '#3b82f6',
            'solvencia': '#ef4444',
            'gestion': '#d4d4d8',
            'rentabilidad': '#10b981',
            'cobertura': '#f59e0b',
        }

        kpis = []
        for cat, key, name, unit_hint in order:
            va = ratios_a.get(key) or {}
            available_a = bool(va.get('available', True))
            unit = _unit_from(va, unit_hint)
            st_a = str(va.get('zone_label') or va.get('status') or '')
            vb = ratios_b.get(key) or {}
            available_b = bool(vb.get('available', True)) if year_cmp else False
            st_b = str(vb.get('zone_label') or vb.get('status') or '') if year_cmp else ''
            decimals = 2
            if unit in ('d',):
                decimals = 0
            elif unit in ('x',):
                decimals = 2
            elif unit in ('%',):
                decimals = 2
            elif unit in ('€',):
                decimals = 2

            if year_cmp:
                val_a = float(va.get('value') or 0.0) if available_a else None
                val_b = float(vb.get('value') or 0.0) if available_b else None

                a_txt = (_fmt_es(val_a, decimals) + (f" {unit}" if unit else "")) if val_a is not None else "N/D"
                b_txt = (_fmt_es(val_b, decimals) + (f" {unit}" if unit else "")) if val_b is not None else "N/D"

                d_txt = "N/D"
                dp_txt = "N/D"
                ch = "N/D"
                if (val_a is not None) and (val_b is not None):
                    delta = val_b - val_a
                    delta_pct = ((delta / abs(val_a)) * 100.0) if abs(val_a) > 1e-9 else None
                    d_txt = _fmt_es(delta, decimals) + (f" {unit}" if unit else "")
                    dp_txt = (_fmt_es(delta_pct, 1) + " %") if delta_pct is not None else "N/D"
                    ch = f"vs {year}: {_fmt_es(delta, decimals)}{(' ' + unit) if unit else ''}"
                    if delta_pct is not None:
                        ch += f" ({_fmt_es(delta_pct, 1)} %)"

                if val_b is not None:
                    kpis.append({'label': name, 'group': cat, 'value': round(val_b, decimals), 'suffix': unit, 'decimals': decimals, 'color': color_map.get(cat, '#e5e7eb'), 'change': ch})
                else:
                    kpis.append({'label': name, 'group': cat, 'value': 'N/D', 'suffix': '', 'color': '#71717a', 'change': 'N/D'})

                rows.append([cat, name, a_txt, b_txt, d_txt, dp_txt, st_a or 'N/D', st_b or 'N/D'])
            else:
                if available_a:
                    val = float(va.get('value') or 0.0)
                    kpis.append({'label': name, 'group': cat, 'value': round(val, decimals), 'suffix': unit, 'decimals': decimals, 'color': color_map.get(cat, '#e5e7eb'), 'change': st_a})
                    v_txt = _fmt_es(val, decimals) + (f" {unit}" if unit else "")
                    rows.append([cat, name, v_txt, st_a])
                else:
                    kpis.append({'label': name, 'group': cat, 'value': 'N/D', 'suffix': '', 'color': '#71717a', 'change': 'N/D'})
                    rows.append([cat, name, 'N/D', 'N/D'])

        expl = []
        expl.append("<li><strong>Liquidez</strong>: mide capacidad de pago a corto plazo (liquidez corriente, test ácido, disponibilidad, fondo de maniobra).</li>")
        expl.append("<li><strong>Solvencia</strong>: estructura financiera (endeudamiento, autonomía, garantía, calidad de deuda).</li>")
        expl.append("<li><strong>Gestión</strong>: eficiencia operativa (rotaciones, periodos de cobro y pago).</li>")
        expl.append("<li><strong>Rentabilidad</strong>: márgenes y ROA/ROE.</li>")
        expl.append("<li><strong>Cobertura</strong>: capacidad de soportar costes financieros y generar margen EBITDA.</li>")

        if year_cmp:
            answer = (
                f"<h3>Ratios financieros {year} vs {year_cmp}</h3>"
                f"<p>Base {year}: ventas {_fmt_es(base_a.get('ventas_totales', 0), 2)} €, activo {_fmt_es(base_a.get('activo_total', 0), 2)} €, pasivo {_fmt_es(base_a.get('pasivo_total', 0), 2)} €.</p>"
                f"<p>Base {year_cmp}: ventas {_fmt_es(base_b.get('ventas_totales', 0), 2)} €, activo {_fmt_es(base_b.get('activo_total', 0), 2)} €, pasivo {_fmt_es(base_b.get('pasivo_total', 0), 2)} €.</p>"
                f"<ul>{''.join(expl)}</ul>"
            )
        else:
            answer = (
                f"<h3>Ratios financieros {year}</h3>"
                f"<p>Base: ventas {_fmt_es(base_a.get('ventas_totales', 0), 2)} €, activo total {_fmt_es(base_a.get('activo_total', 0), 2)} €, pasivo total {_fmt_es(base_a.get('pasivo_total', 0), 2)} €.</p>"
                f"<ul>{''.join(expl)}</ul>"
            )

        def _getv(rr: Dict[str, Any], k: str) -> float:
            try:
                return float((rr.get(k) or {}).get('value') or 0)
            except Exception:
                return 0.0
        labels_key = ['Liquidez', 'Endeudamiento %', 'ROE %', 'ROA %', 'Margen neto %']
        vals_a = [_getv(ratios_a, 'liquidez_corriente'), _getv(ratios_a, 'endeudamiento'), _getv(ratios_a, 'roe'), _getv(ratios_a, 'roa'), _getv(ratios_a, 'margen_neto')]
        if year_cmp:
            vals_b = [_getv(ratios_b, 'liquidez_corriente'), _getv(ratios_b, 'endeudamiento'), _getv(ratios_b, 'roe'), _getv(ratios_b, 'roa'), _getv(ratios_b, 'margen_neto')]
            chart = {
                'type': 'bar',
                'data': {
                    'labels': labels_key,
                    'datasets': [
                        {'label': str(year), 'data': vals_a, 'backgroundColor': 'rgba(96,165,250,0.35)', 'borderColor': '#60a5fa'},
                        {'label': str(year_cmp), 'data': vals_b, 'backgroundColor': 'rgba(59,130,246,0.35)', 'borderColor': '#3b82f6'},
                    ]
                },
                'options': {
                    'responsive': True,
                    'maintainAspectRatio': False,
                    'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': f"Ratios clave {year} vs {year_cmp}"}},
                    'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
                }
            }
        else:
            chart = self._bar_h(labels_key, vals_a, f"Ratios clave {year}", '')

        return {
            'type': 'report',
            'key': 'financiera_ratios',
            'kpis': kpis,
            'answer': answer,
            'chart_config': chart,
            'tables': [
                {'title': 'Ratios', 'columns': (['Categoría', 'Ratio', str(year), str(year_cmp), 'Δ', 'Δ%', 'Lectura', 'Lectura (cmp)'] if year_cmp else ['Categoría', 'Ratio', 'Valor', 'Lectura']), 'rows': rows},
            ],
        }

    def _ventas_resumen(self, empresa: int, year: int, prev: int) -> Dict[str, Any]:
        curr = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa, ejercicio=year).first()
        prev_row = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa, ejercicio=prev).first()
        curr_sales = _to_float(curr.importe_neto_total) if curr else 0.0
        prev_sales = _to_float(prev_row.importe_neto_total) if prev_row else 0.0
        yoy = ((curr_sales - prev_sales) / prev_sales * 100) if prev_sales > 0 else 0.0
        kpis = [
            {'label': self._t('kpi_sales'), 'value': round(curr_sales, 2), 'suffix': '€', 'color': '#3b82f6', 'change': round(yoy, 1)},
        ]
        return {
            'type': 'report',
            'key': 'ventas_resumen',
            'kpis': kpis,
            'answer': f"Resumen de ventas del ejercicio {year}.",
            'chart_config': self._ventas_mensual_chart(empresa, year, prev, self._t('chart_sales_monthly')),
        }

    def _yoy_total_chart(self, year: int, prev: int, cy: float, py: float, title: str) -> Dict[str, Any]:
        return {
            'type': 'bar',
            'data': {
                'labels': [str(prev), str(year)],
                'datasets': [{
                    'label': self._t('sales_eur'),
                    'data': [round(py, 2), round(cy, 2)],
                    'backgroundColor': ['#60a5fa', '#3b82f6'],
                    'borderRadius': 6
                }]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {'legend': {'display': False}, 'title': {'display': True, 'text': title}},
                'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
            }
        }

    def _ventas_totales(self, empresa: int, year: int) -> float:
        row = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa, ejercicio=year).first()
        return _to_float(row.importe_neto_total) if row else 0.0

    def _compras_totales(self, empresa: int, year: int) -> float:
        row = MetricsTotalesEmpresaEjercicioCompra.objects.filter(empresa=empresa, ejercicio=year).first()
        return _to_float(row.importe_neto_total) if row else 0.0

    def _ventas_top_clientes(self, empresa: int, year: int, prev: int, limit: int, worst: bool = False) -> Dict[str, Any]:
        qs = MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=year)
        if worst:
            qs = qs.filter(importe_neto_total__gt=0)
        rows = list(qs.order_by('importe_neto_total' if worst else '-importe_neto_total')[:limit])
        data = []
        total = 0.0
        for r in rows:
            name = (r.nombre or r.cliente or self._t('unknown')).strip()
            val = _to_float(r.importe_neto_total)
            cost = _to_float(getattr(r, 'importe_coste_total', 0))
            ops = int(getattr(r, 'albaranes_count', 0) or 0)
            total += val
            data.append({'key': r.cliente, 'name': name, 'value': val, 'cost': cost, 'ops': ops})
        labels = [(d['name'][:15] + '...') if len(d['name']) > 15 else d['name'] for d in data]
        values = [d['value'] for d in data]
        keys = [d['key'] for d in data if d.get('key') is not None]
        prev_rows = list(
            MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=prev, cliente__in=keys)
        ) if keys else []
        prev_map = {r.cliente: r for r in prev_rows}

        table_rows = []
        for d in data:
            pr = prev_map.get(d.get('key'))
            py_sales = _to_float(getattr(pr, 'importe_neto_total', 0)) if pr else 0.0
            py_cost = _to_float(getattr(pr, 'importe_coste_total', 0)) if pr else 0.0
            py_ops = int(getattr(pr, 'albaranes_count', 0) or 0) if pr else 0
            cy_sales = d['value']
            cy_cost = d['cost']
            cy_ops = d['ops']
            cy_margin = cy_sales - cy_cost
            py_margin = py_sales - py_cost
            cy_margin_pct = (cy_margin / cy_sales * 100.0) if cy_sales else 0.0
            py_margin_pct = (py_margin / py_sales * 100.0) if py_sales else 0.0
            sales_var_pct = ((cy_sales - py_sales) / py_sales * 100.0) if py_sales else 0.0
            price_cy = (cy_sales / cy_ops) if cy_ops else 0.0
            price_py = (py_sales / py_ops) if py_ops else 0.0
            table_rows.append([
                d['name'],
                round(cy_sales, 2), round(py_sales, 2), round(sales_var_pct, 1),
                round(cy_cost, 2), round(py_cost, 2),
                round(cy_margin, 2), round(py_margin, 2),
                round(cy_margin_pct, 1), round(py_margin_pct, 1),
                cy_ops, py_ops,
                round(price_cy, 2), round(price_py, 2)
            ])
        kpis = [
            self._kpi(f"{self._t('kpi_top1')}: {(data[0]['name'] if data else '')}", round(values[0], 2) if values else 0.0, '€', '#3b82f6'),
            self._kpi(self._t('kpi_top3'), round(sum(values[:3]), 2) if values else 0.0, '€', '#10b981'),
        ]
        top_for_pie = [(labels[i], values[i]) for i in range(min(5, len(values)))]
        cy_total = self._ventas_totales(empresa, year)
        py_total = self._ventas_totales(empresa, prev)
        return {
            'type': 'report',
            'key': 'ventas_top_clientes',
            'kpis': kpis,
            'answer': f"{'Clientes con menores ventas' if worst else 'Mejores clientes'} del ejercicio {year}.",
            'chart_config': self._yoy_total_chart(year, prev, cy_total, py_total, f"Comparativa {year} vs {prev}"),
            'chart_pareto_clients': self._bar_h(labels, values, 'Clientes con menores ventas' if worst else self._t('chart_top_clients'), self._t('sales_eur')),
            'chart_concentration_clients': self._concentration_pie(top_for_pie, sum(values), 'Concentración de ventas'),
            'table': {'title': 'Detalle', 'columns': ['Cliente', f'Ventas {year} (€)', f'Ventas {prev} (€)', 'Var %', f'Coste {year} (€)', f'Coste {prev} (€)', f'Margen {year} (€)', f'Margen {prev} (€)', f'Margen {year} %', f'Margen {prev} %', f'Ops {year}', f'Ops {prev}', f'Precio medio {year} (€)', f'Precio medio {prev} (€)'], 'rows': table_rows},
        }

    def _ventas_top_productos(self, empresa: int, year: int, prev: int, limit: int, worst: bool = False) -> Dict[str, Any]:
        qs = MetricsTotalesEmpresaEjercicioArticulo.objects.filter(empresa=empresa, ejercicio=year)
        if worst:
            qs = qs.filter(importe_neto_total__gt=0)
        rows = list(qs.order_by('importe_neto_total' if worst else '-importe_neto_total')[:limit])
        data = []
        for r in rows:
            name = (r.descripcion or r.articulo or self._t('unknown')).strip()
            val = _to_float(r.importe_neto_total)
            cost = _to_float(getattr(r, 'importe_coste_total', 0))
            ops = int(getattr(r, 'albaranes_count', 0) or 0)
            data.append({'key': r.articulo, 'name': name, 'value': val, 'cost': cost, 'ops': ops})
        labels = [(d['name'][:15] + '...') if len(d['name']) > 15 else d['name'] for d in data]
        values = [d['value'] for d in data]
        keys = [d['key'] for d in data if d.get('key') is not None]
        prev_rows = list(
            MetricsTotalesEmpresaEjercicioArticulo.objects.filter(empresa=empresa, ejercicio=prev, articulo__in=keys)
        ) if keys else []
        prev_map = {r.articulo: r for r in prev_rows}

        table_rows = []
        for d in data:
            pr = prev_map.get(d.get('key'))
            py_sales = _to_float(getattr(pr, 'importe_neto_total', 0)) if pr else 0.0
            py_cost = _to_float(getattr(pr, 'importe_coste_total', 0)) if pr else 0.0
            py_ops = int(getattr(pr, 'albaranes_count', 0) or 0) if pr else 0
            cy_sales = d['value']
            cy_cost = d['cost']
            cy_ops = d['ops']
            cy_margin = cy_sales - cy_cost
            py_margin = py_sales - py_cost
            cy_margin_pct = (cy_margin / cy_sales * 100.0) if cy_sales else 0.0
            py_margin_pct = (py_margin / py_sales * 100.0) if py_sales else 0.0
            sales_var_pct = ((cy_sales - py_sales) / py_sales * 100.0) if py_sales else 0.0
            price_cy = (cy_sales / cy_ops) if cy_ops else 0.0
            price_py = (py_sales / py_ops) if py_ops else 0.0
            table_rows.append([
                d['name'],
                round(cy_sales, 2), round(py_sales, 2), round(sales_var_pct, 1),
                round(cy_cost, 2), round(py_cost, 2),
                round(cy_margin, 2), round(py_margin, 2),
                round(cy_margin_pct, 1), round(py_margin_pct, 1),
                cy_ops, py_ops,
                round(price_cy, 2), round(price_py, 2)
            ])
        kpis = [
            self._kpi(f"{self._t('kpi_top1')}: {(data[0]['name'] if data else '')}", round(values[0], 2) if values else 0.0, '€', '#3b82f6'),
            self._kpi(self._t('kpi_top3'), round(sum(values[:3]), 2) if values else 0.0, '€', '#10b981'),
        ]
        top_for_pie = [(labels[i], values[i]) for i in range(min(5, len(values)))]
        cy_total = self._ventas_totales(empresa, year)
        py_total = self._ventas_totales(empresa, prev)
        return {
            'type': 'report',
            'key': 'ventas_top_productos',
            'kpis': kpis,
            'answer': f"{'Productos con menores ventas' if worst else 'Mejores productos'} del ejercicio {year}.",
            'chart_config': self._yoy_total_chart(year, prev, cy_total, py_total, f"Comparativa {year} vs {prev}"),
            'chart_pareto_products': self._bar_h(labels, values, 'Productos con menores ventas' if worst else self._t('chart_top_products'), self._t('sales_eur')),
            'chart_concentration_products': self._concentration_pie(top_for_pie, sum(values), 'Concentración de ventas'),
            'table': {'title': 'Detalle', 'columns': ['Artículo', f'Ventas {year} (€)', f'Ventas {prev} (€)', 'Var %', f'Coste {year} (€)', f'Coste {prev} (€)', f'Margen {year} (€)', f'Margen {prev} (€)', f'Margen {year} %', f'Margen {prev} %', f'Ops {year}', f'Ops {prev}', f'Precio medio {year} (€)', f'Precio medio {prev} (€)'], 'rows': table_rows},
        }

    def _ventas_mensual_chart(self, empresa: int, year: int, prev: int, title: str) -> Dict[str, Any]:
        labels = _months_es()
        curr = [0.0] * 12
        prev_vals = [0.0] * 12
        for r in MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=year):
            m = int(r.mes or 0)
            if 1 <= m <= 12:
                curr[m - 1] = _to_float(r.importe_neto_total)
        for r in MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=prev):
            m = int(r.mes or 0)
            if 1 <= m <= 12:
                prev_vals[m - 1] = _to_float(r.importe_neto_total)
        return self._line_dual(labels, curr, prev_vals, title, str(year), str(prev))

    def _ventas_mensual(self, empresa: int, year: int, prev: int) -> Dict[str, Any]:
        chart = self._ventas_mensual_chart(empresa, year, prev, self._t('chart_sales_monthly'))
        return {
            'type': 'report',
            'key': 'ventas_mensual',
            'kpis': [],
            'answer': f"Evolución mensual de ventas ({year} vs {prev}).",
            'chart_config': chart,
        }

    def _margen_mensual(self, empresa: int, year: int, prev: int) -> Dict[str, Any]:
        labels = _months_es()
        curr = [0.0] * 12
        prev_vals = [0.0] * 12
        for r in MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=year):
            m = int(r.mes or 0)
            if 1 <= m <= 12:
                net = _to_float(r.importe_neto_total)
                cost = _to_float(r.importe_coste_total)
                curr[m - 1] = round(((net - cost) / net * 100) if net > 0 else 0.0, 2)
        for r in MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=prev):
            m = int(r.mes or 0)
            if 1 <= m <= 12:
                net = _to_float(r.importe_neto_total)
                cost = _to_float(r.importe_coste_total)
                prev_vals[m - 1] = round(((net - cost) / net * 100) if net > 0 else 0.0, 2)
        chart = self._line_dual(labels, curr, prev_vals, self._t('chart_margin_monthly'), str(year), str(prev))
        return {
            'type': 'report',
            'key': 'margen_mensual',
            'kpis': [],
            'answer': f"Evolución mensual del margen ({year} vs {prev}).",
            'chart_config': chart,
        }

    def _finanzas_resumen(self, empresa: int, year: int, prev: int) -> Dict[str, Any]:
        svc = FinancialService()
        snapshot = svc.get_snapshot(empresa, year)
        ratios_ext = svc.get_ratios_extended(empresa, year)
        curr_month = svc.get_monthly_kpis(empresa, year)
        prev_month = svc.get_monthly_kpis(empresa, prev)

        labels = curr_month.get('labels') or _months_es()
        ingresos_cy = curr_month.get('ingresos') or [0.0] * 12
        ingresos_py = prev_month.get('ingresos') or [0.0] * 12
        chart_ingresos = self._line_dual(labels, ingresos_cy, ingresos_py, "Ingresos (YoY)", str(year), str(prev))

        py = snapshot.get('py') or {}
        var = snapshot.get('var') or {}

        def _v(d, key, sub=None):
            if not isinstance(d, dict):
                return 0.0
            v = d.get(key, 0.0) if sub is None else ((d.get(key) or {}).get(sub) or 0.0)
            try:
                return float(v or 0.0)
            except Exception:
                return 0.0

        ingresos_val = float(snapshot.get('ingresos', 0.0))
        gastos_val = float(snapshot.get('gastos', 0.0))
        otros_ing_val = float(snapshot.get('otros_ingresos', 0.0))
        otros_gast_val = float(snapshot.get('otros_gastos', 0.0))
        resultado_val = float(snapshot.get('resultado', 0.0))

        ingresos_py = float(py.get('ingresos', 0.0))
        gastos_py_val = float(py.get('gastos', 0.0))
        resultado_py_val = float(py.get('resultado', 0.0))

        ingresos_var_abs = _v(var, 'ingresos', 'abs')
        ingresos_var_pct = _v(var, 'ingresos', 'pct')
        gastos_var_abs = _v(var, 'gastos', 'abs')
        gastos_var_pct = _v(var, 'gastos', 'pct')
        resultado_var_abs = _v(var, 'resultado', 'abs')
        resultado_var_pct = _v(var, 'resultado', 'pct')

        ratios = (ratios_ext.get('ratios') or {}) if isinstance(ratios_ext, dict) else {}

        def _ratio(key):
            r = ratios.get(key) or {}
            return float(r.get('value') or 0.0)

        liquidez_corriente = _ratio('liquidez_corriente')
        endeudamiento_pct = _ratio('endeudamiento')
        margen_ebitda_pct = _ratio('margen_ebitda')
        margen_neto_pct = _ratio('margen_neto')
        periodo_cobro = _ratio('periodo_cobro')
        periodo_pago = _ratio('periodo_pago')

        kpis = [
            self._kpi("Ingresos", round(ingresos_val, 2), "€", "#3b82f6", change=f"vs {prev}: {round(ingresos_var_abs,2)} € ({round(ingresos_var_pct,1)}%)"),
            self._kpi("Gastos", round(gastos_val, 2), "€", "#ef4444", change=f"vs {prev}: {round(gastos_var_abs,2)} € ({round(gastos_var_pct,1)}%)"),
            self._kpi("Resultado explotación", round(resultado_val, 2), "€", "#22c55e", change=f"vs {prev}: {round(resultado_var_abs,2)} € ({round(resultado_var_pct,1)}%)"),
            self._kpi("Otros ingresos", round(otros_ing_val, 2), "€", "#38bdf8"),
            self._kpi("Otros gastos", round(otros_gast_val, 2), "€", "#f97316"),
            self._kpi("Margen EBITDA", round(margen_ebitda_pct, 2), "%", "#a855f7"),
            self._kpi("Margen neto", round(margen_neto_pct, 2), "%", "#0ea5e9"),
            self._kpi("Liquidez corriente", round(liquidez_corriente, 2), "x", "#22c55e"),
            self._kpi("Endeudamiento", round(endeudamiento_pct, 2), "%", "#eab308"),
            self._kpi("Periodo cobro", round(periodo_cobro, 1), "días", "#3b82f6"),
            self._kpi("Periodo pago", round(periodo_pago, 1), "días", "#ef4444"),
        ]

        table_rows = [
            ["Ingresos", ingresos_val, ingresos_py, ingresos_var_abs, ingresos_var_pct],
            ["Gastos", gastos_val, gastos_py_val, gastos_var_abs, gastos_var_pct],
            ["Resultado explotación", resultado_val, resultado_py_val, resultado_var_abs, resultado_var_pct],
        ]

        table = {
            'title': f"Resumen cuantitativo {year} vs {prev}",
            'columns': ["Magnitud", f"{year} €", f"{prev} €", "Δ €", "Δ %"],
            'rows': [[r[0], round(r[1],2), round(r[2],2), round(r[3],2), round(r[4],1)] for r in table_rows],
        }

        return {
            'type': 'report',
            'key': 'finanzas_resumen',
            'kpis': kpis,
            'answer': f"Resumen financiero del ejercicio {year}.",
            'chart_config': chart_ingresos,
            'table': table,
            'totals': {
                'snapshot': snapshot,
                'ratios': ratios_ext,
            },
        }

    def _finanzas_per100(self, empresa: int, year: int) -> Dict[str, Any]:
        svc = FinancialService()
        dto = svc.get_per100(empresa, year, eq_mode=True)
        parts_cy = ((dto.get('cy') or {}).get('parts') or []) if isinstance(dto, dict) else []
        parts_py = ((dto.get('py') or {}).get('parts') or []) if isinstance(dto, dict) else []
        label_map = {
            'costo_ventas': 'Coste de Ventas',
            'otros_gastos_exp': 'Otros Gastos de Explotación',
            'gastos_admin': 'Gastos Administrativos',
            'impuestos': 'Impuestos',
            'personal': 'Gastos de Personal',
            'amort': 'Amortizaciones y Deterioros',
            'financiero': 'Resultado Financiero',
            'utilidad_neta': 'Utilidad Neta',
        }
        order = ['costo_ventas', 'otros_gastos_exp', 'utilidad_neta']
        def pct_map(parts):
            out = {}
            for p in parts or []:
                out[str(p.get('key') or '')] = float(p.get('pct') or 0.0)
            return out
        cy_m = pct_map(parts_cy)
        py_m = pct_map(parts_py)
        labels = [label_map.get(k, k) for k in order if k in cy_m or k in py_m]
        cy_vals = [cy_m.get(k, 0.0) for k in order if k in cy_m or k in py_m]
        py_vals = [py_m.get(k, 0.0) for k in order if k in cy_m or k in py_m]
        chart = {
            'type': 'bar',
            'data': {
                'labels': labels,
                'datasets': [
                    {'label': str(year), 'data': cy_vals, 'backgroundColor': '#3b82f6', 'borderRadius': 4},
                    {'label': str(year - 1), 'data': py_vals, 'backgroundColor': '#60a5fa', 'borderRadius': 4},
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {'legend': {'display': True}, 'title': {'display': True, 'text': self._t('chart_per100')}},
                'scales': {'x': {'grid': {'color': '#334155'}}, 'y': {'grid': {'color': '#334155'}}}
            }
        }
        return {
            'type': 'report',
            'key': 'finanzas_per100',
            'kpis': [],
            'answer': f"Coste por cada 100 del ejercicio {year}.",
            'chart_config': chart,
        }

    def to_float(self, v) -> float:
        return _to_float(v)

    def t(self, key: str) -> str:
        return self._t(key)

    def line_dual(self, labels: List[str], a: List[float], b: List[float], title: str, la: str, lb: str) -> Dict[str, Any]:
        return self._line_dual(labels, a, b, title, la, lb)

    def bar_h(self, labels: List[str], values: List[float], title: str, label: str) -> Dict[str, Any]:
        return self._bar_h(labels, values, title, label)

    def concentration_pie(self, top: List[Tuple[str, float]], total: float, title: str) -> Dict[str, Any]:
        return self._concentration_pie(top, total, title)

    def yoy_total_chart(self, year: int, prev: int, cy: float, py: float, title: str) -> Dict[str, Any]:
        return self._yoy_total_chart(year, prev, cy, py, title)

    def compras_totales(self, empresa: int, year: int) -> float:
        return self._compras_totales(empresa, year)
