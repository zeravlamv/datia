from datia.services.financial_service import FinancialService
from datia.services.totals_service import TotalsService
import logging
import json
from datia.services.cache_service import compute_mssql_fingerprint

logger = logging.getLogger(__name__)

class FinancialContextBuilder:
    """
    Agrega datos financieros (P&L, Balance, Ratios, Presupuestos, Tesorería) 
    para el informe Estratégico de IA (Rol Controller).
    """
    def build_context(self, empresa: int, ejercicio: int, fast_mode: bool = False) -> dict:
        service = FinancialService()
        
        # 1. Snapshot General (KPIs + Ratios)
        snapshot = service.get_snapshot(empresa, ejercicio)
        
        # 2. Cuenta de Resultados (P&L) - Comparativa con Presupuesto (si existe)
        pl_report = service.get_pl_report(empresa, ejercicio, level=1)
        
        # Detect if Budget available to switch context mode
        has_budget = pl_report.get('total_ingresos_budget', 0) > 0
        comparison_mode = "budget" if has_budget else "previous_year"

        # 3. Balance de Situación (Resumen)
        balance = service.get_balance_summary(empresa, ejercicio)
        
        # 4. Tesorería (Snapshot básico + Forecast corto plazo)
        treasury = service.get_treasury_snapshot(empresa, ejercicio)
        treasury_forecast = {}
        if not fast_mode:
            try:
                 # Forecast simple 3 meses para contexto
                treasury_forecast = service.get_treasury_forecast(empresa, ejercicio, months=3)
                treasury['forecast_3m'] = treasury_forecast.get('forecast', [])
            except Exception:
                treasury['forecast_3m'] = []
        else:
            treasury['forecast_3m'] = []

        # 5. Trimestral (Evolución)
        try:
            quarterly = service.get_quarterly_report(empresa, ejercicio)
        except Exception:
             # Fast fallback
             quarterly = {"rows": []}
        
        # 6. Análisis Avanzado (Tendencias y Anomalías)
        try:
            advanced = service.get_advanced_analysis(empresa, ejercicio)
        except Exception:
            advanced = {"trend": {"direction": "stable"}, "anomalies": [], "recommendations": []}

        # 7. Drilldown de Ratios Clave (Liquidez, Solvencia)
        ratios_detail = {}
        # [OPTIMIZATION] Disabled Drilldown to save time
        # for r in ['liquidez', 'solvencia', 'endeudamiento']:
        #    try:
        #        ratios_detail[r] = service.get_ratio_drilldown(empresa, ejercicio, r)
        #    except:
        #        pass

        # Build Structured Context for LLM
        context = {
            "meta": {
                "empresa_id": empresa,
                "ejercicio": ejercicio,
                "moneda": "EUR",
                "rol": "Controller Financiero / CFO",
                "comparison_mode": comparison_mode,
                "fingerprint": compute_mssql_fingerprint()
            },
            "kpis_globales": {
                "ventas": snapshot.get("ingresos", 0),
                "otros_ingresos": snapshot.get("otros_ingresos", 0),
                "v_existencias": snapshot.get("variacion", 0),
                "compras": snapshot.get("gastos", 0),
                "otros_gastos": snapshot.get("otros_gastos", 0),
                "gastos": snapshot.get("gastos", 0),
                "ebitda": snapshot.get("resultado", 0),
                "margen_op_pct": snapshot.get("ratios", {}).get("margen", 0),
                "resultado_neto_balance": balance.get("balance_eq_diff", 0)
            },
            "kpis_comparativa": {
                "py": snapshot.get("py", {}),
                "var": snapshot.get("var", {})
            },
            "balance_situacion": {
                "activo_total": balance.get("totales", {}).get("activo", 0),
                "pasivo_total": balance.get("totales", {}).get("pasivo", 0),
                "patrimonio_neto": balance.get("totales", {}).get("patrimonio", 0),
                "fondo_maniobra": treasury.get('fondo_maniobra', 0),
                "ratios": {
                    "liquidez": balance.get("ratios", {}).get("liquidez", 0),
                    "solvencia": balance.get("ratios", {}).get("solvencia", 0),
                    "endeudamiento_pct": balance.get("ratios", {}).get("endeudamiento", 0)
                }
            },
            "series_mensuales": {},
            "pl_analisis": [
                {
                    "concepto": row["descripcion"],
                    "real": row["valor"],
                    "objetivo": row["presupuesto"] if has_budget else 0, # Or prev year?
                    "desviacion_importe": row["desviacion"],
                    "desviacion_pct": (row["desviacion"] / row["presupuesto"] * 100) if has_budget and row["presupuesto"] else 0
                }
                for row in pl_report.get("rows", [])
                if row.get("is_header", False)
            ],
            "tesoreria": {
                "disponible_actual": treasury.get('disponible', 0),
                "periodo_medio_cobro_dias": treasury.get('dso', 0),
                "periodo_medio_pago_dias": treasury.get('dpo', 0),
                "dso": (treasury.get('kpis', {}).get('dso') if isinstance(treasury.get('kpis'), dict) else None) or treasury.get('dso', 0),
                "dpo": (treasury.get('kpis', {}).get('dpo') if isinstance(treasury.get('kpis'), dict) else None) or treasury.get('dpo', 0),
                "fondo_maniobra": (treasury.get('kpis', {}).get('working_capital') if isinstance(treasury.get('kpis'), dict) else None) or treasury.get('fondo_maniobra', 0),
                "disponible": (treasury.get('kpis', {}).get('cash') if isinstance(treasury.get('kpis'), dict) else None) or treasury.get('disponible', 0),
                "tension_liquidez_detectada": len(treasury_forecast.get('alerts', [])) > 0 if treasury_forecast else False
            },
            "tendencias_anomalias": {
                "direccion_anual": advanced.get("trend", {}).get("direction", "stable"),
                "anomalias_detectadas": [
                    f"Mes {a['index']+1}: {a['type']} ({a['value']})" 
                    for a in advanced.get("anomalies", [])
                ],
                "recomendaciones_algoritmicas": advanced.get("recommendations", [])
            }
        }

        # 11. KPIs Mensuales (Ingresos, Gastos, EBITDA, Margen%)
        try:
            monthly = service.get_monthly_kpis(empresa, ejercicio)
        except Exception:
            monthly = {'labels': [], 'ingresos': [0.0]*12, 'gastos': [0.0]*12, 'ebitda': [0.0]*12, 'margen_pct': [0.0]*12}
        context["series_mensuales"] = monthly

        # 12. Estacionalidad y YoY por mes (Ingresos)
        try:
            monthly_prev = service.get_monthly_kpis(empresa, ejercicio - 1)
            ingresos_prev = monthly_prev.get('ingresos') or [0.0]*12
        except Exception:
            ingresos_prev = [0.0]*12
        ingresos = monthly.get('ingresos') or [0.0]*12
        total_ingresos = sum(ingresos) if ingresos else 0.0
        estacionalidad = []
        for idx in range(12):
            val = ingresos[idx] if idx < len(ingresos) else 0.0
            prev = ingresos_prev[idx] if idx < len(ingresos_prev) else 0.0
            share_pct = (val / total_ingresos * 100) if total_ingresos > 0 else 0.0
            yoy_pct = ((val - prev) / prev * 100) if prev > 0 else 0.0
            estacionalidad.append({"mes": idx + 1, "share_pct": round(share_pct, 2), "yoy_pct": round(yoy_pct, 2)})
        context["estacionalidad"] = estacionalidad

        # Add Computed Alerts for Context
        alerts = []
        if context["kpis_globales"]["margen_op_pct"] < 5:
            alerts.append("ALERTA: Margen Operativo Crítico (<5%)")
        if context["balance_situacion"]["ratios"]["liquidez"] < 1.0:
             alerts.append("ALERTA: Problema de Liquidez (Ratio < 1.0)")
        if context["tesoreria"]["tension_liquidez_detectada"]:
             alerts.append("ALERTA: Tensión de Tesorería proyectada a 3 meses")
        
        context["alertas_sistema"] = alerts
        
        # 13. Persistir contexto en disco para trazabilidad y reutilización
        try:
            import os, json
            from django.conf import settings
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
            ctx_path = os.path.join(ctx_dir, f"datia_ai_context_financiera_{empresa}_{ejercicio}.json")
            with open(ctx_path, 'w', encoding='utf-8') as f:
                json.dump(context, f, ensure_ascii=False)
            try:
                from datia.factories import ServiceFactory
                emb = ServiceFactory.get_embedding_service()
                emb.add_embedding(
                    text=json.dumps(context, ensure_ascii=False),
                    sql="",
                    metadata={"empresa": empresa, "ejercicio": ejercicio, "type": "financiera", "fingerprint": compute_mssql_fingerprint()},
                    kind="context",
                    key=f"context_financiera_{empresa}_{ejercicio}"
                )
            except Exception:
                pass
        except Exception:
            pass

        return context

