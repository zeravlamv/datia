from ninja import Router, Schema
from typing import Dict, Any, List, Optional
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
import io, csv, json, os, re
from datetime import date
from django.conf import settings
from statistics import mean
from datia.services.financial_service import FinancialService
from datia.services.etl_service import ETLService
from datia.services.utility_anatomy_service import UtilityAnatomyService
from datia.services.banking_service import BankingService
from datia.models.banking import BankingBank, BankingAccount, BankingInstrument, BankingInstrumentAccountMap, BankingAmortization

router = Router()

class PLDetailRow(Schema):
    cuenta: str
    descripcion: str = ""
    mes_actual: float
    mes_anterior: float
    variacion: float
    is_ingreso: bool

class PLDetailMeta(Schema):
    period_name: str = ""
    month_index: int
    year_current: int
    year_prev: int

class PLDetailResponse(Schema):
    data: List[PLDetailRow]
    meta: PLDetailMeta

class BalanceTotals(Schema):
    activo: float
    pasivo: float
    patrimonio: float

class BalanceDesgloseActivo(Schema):
    corriente: float
    no_corriente: float

class BalanceDesglosePasivo(Schema):
    corriente: float
    no_corriente: float

class BalanceRatios(Schema):
    liquidez: float
    solvencia: float
    endeudamiento: float

class BalanceDesglose(Schema):
    activo: BalanceDesgloseActivo
    pasivo: BalanceDesglosePasivo

class BalanceSummaryResponse(Schema):
    empresa: int
    ejercicio: int
    status: str
    reason: str = ""
    totales: BalanceTotals
    desglose: BalanceDesglose
    ratios: BalanceRatios
    balance_eq_diff: float

@router.get("/snapshot", response=Dict[str, Any])
def get_financial_snapshot(request: HttpRequest, empresa: int, ejercicio: int):
    """
    Returns high-level financial KPIs (Ingresos, Gastos, Resultado, Ratios).
    """
    service = FinancialService()
    return service.get_snapshot(empresa, ejercicio)

@router.get("/ratios", response=Dict[str, Any])
def get_financial_ratios(request: HttpRequest, empresa: int, ejercicio: int):
    service = FinancialService()
    return service.get_ratios_extended(empresa, ejercicio)

@router.get("/pl", response=Dict[str, Any])
def get_pl_report(request: HttpRequest, empresa: int, ejercicio: int, level: int = 3):
    """
    Returns detailed P&L (Cuenta de Resultados).
    """
    service = FinancialService()
    return service.get_pl_report(empresa, ejercicio, level)

@router.get("/pl/validate", response=Dict[str, Any])
def validate_pl_balance(request: HttpRequest, empresa: int, ejercicio: int, tolerance: float = 0.01):
    service = FinancialService()
    return service.validate_pl_balance(empresa, ejercicio, float(tolerance or 0.01))

@router.get("/analysis", response=Dict[str, Any])
def get_financial_analysis(request: HttpRequest, empresa: int, ejercicio: int):
    """
    Returns advanced strategic analysis (Trends, Anomalies, Recommendations).
    """
    service = FinancialService()
    return service.get_advanced_analysis(empresa, ejercicio)

@router.get("/pl-detail", response=PLDetailResponse)
def get_pl_detail(request: HttpRequest, empresa: int, ejercicio: int, month: int = 0, level: int = 3):
    """
    Returns detailed P&L comparing current month vs previous month, grouped by level.
    """
    service = FinancialService()
    return service.get_pl_detail(empresa, ejercicio, month, level)

@router.get("/per100", response=Dict[str, Any])
def get_per100(request: HttpRequest, empresa: int, ejercicio: int, eq: bool = True):
    service = FinancialService()
    return service.get_per100(empresa, ejercicio, bool(eq))

@router.get("/quarterly", response=Dict[str, Any])
def get_quarterly(request: HttpRequest, empresa: int, ejercicio: int, departamento: str = None):
    """
    Returns quarterly financial report with comparison vs previous year.
    """
    service = FinancialService()
    return service.get_quarterly_report(empresa, ejercicio, departamento)

@router.get("/monthly_kpis", response=Dict[str, Any])
def get_monthly_kpis(request: HttpRequest, empresa: int, ejercicio: int):
    service = FinancialService()
    return service.get_monthly_kpis(empresa, ejercicio)

@router.get("/departments", response=List[Dict[str, Any]])
def get_financial_departments(request: HttpRequest):
    """
    Returns available 'departamentos' (PGC areas) for filtering.
    """
    service = FinancialService()
    return service.list_departments()

@router.get("/balance/summary", response=BalanceSummaryResponse)
def get_balance_summary(request: HttpRequest, empresa: int, ejercicio: int):
    service = FinancialService()
    return service.get_balance_summary(empresa, ejercicio)

@router.get("/balance/tree", response=Dict[str, Any])
def get_balance_tree(request: HttpRequest, empresa: int, ejercicio: int, root: str = 'activo', start_level: int = 3, end_level: int = 6):
    service = FinancialService()
    return service.get_balance_tree(empresa, ejercicio, root, start_level, end_level)

@router.get("/balance/table", response=Dict[str, Any])
def get_balance_table(request: HttpRequest, empresa: int, ejercicio: int, root: str = 'activo', start_level: int = 3, end_level: int = 6, order: str = 'amount_desc'):
    """
    Returns flat Balance table: code, description, level, amount.
    """
    service = FinancialService()
    return service.get_balance_table(empresa, ejercicio, root, start_level, end_level, order)

@router.get("/ratio/drilldown", response=Dict[str, Any])
def get_ratio_drilldown(request: HttpRequest, empresa: int, ejercicio: int, ratio: str):
    """
    Returns drilldown (numerator/denominator accounts) and senior analysis for a ratio.
    """
    service = FinancialService()
    return service.get_ratio_drilldown(empresa, ejercicio, ratio)

@router.get("/quarterly/export")
def export_quarterly(request: HttpRequest, empresa: int, ejercicio: int, departamento: str = None, format: str = 'csv'):
    """
    Exports quarterly report data. Fallback to CSV if Excel/PDF not available.
    """
    service = FinancialService()
    data = service.get_quarterly_report(empresa, ejercicio, departamento)

    # CSV export
    if format.lower() in ('csv', 'excel', 'xlsx'):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow([
            'Quarter',
            'Ingresos CY', 'Gastos CY', 'Beneficio CY', 'Margen Operativo CY %',
            'Ticket Medio CY', 'Operaciones CY', 'Margen Negocio CY %',
            'Ingresos PY', 'Gastos PY', 'Beneficio PY', 'Margen Operativo PY %',
            'Var % Ingresos', 'Var % Gastos', 'Var % Beneficio', 'Dif. Margen Operativo (pts)'
        ])
        for q in data['quarters']:
            prev = data['comparison']['prev_values']['quarters'][q['quarter']]
            comp = data['comparison']['quarters'][q['quarter']]
            writer.writerow([
                q['quarter'],
                f"{q['ingresos']:.2f}", f"{q['gastos']:.2f}", f"{q['beneficio_neto']:.2f}", f"{q['margen_operativo']:.2f}",
                f"{q['metrics']['ticket_medio']:.2f}", q['metrics']['operaciones'], f"{q['metrics']['margen_pct']:.2f}",
                f"{prev['ingresos']:.2f}", f"{prev['gastos']:.2f}", f"{prev['beneficio_neto']:.2f}", f"{prev['margen_operativo']:.2f}",
                f"{comp['ingresos_var_pct']:.2f}", f"{comp['gastos_var_pct']:.2f}", f"{comp['beneficio_var_pct']:.2f}",
                f"{comp['margen_operativo_diff_pts']:.2f}",
            ])
        resp = HttpResponse(buffer.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="quarterly_{empresa}_{ejercicio}.csv"'
        return resp

    # PDF fallback: simple HTML for printing
    if format.lower() == 'pdf':
        html_rows = ''.join([
            f"<tr><td>{q['quarter']}</td><td>{q['ingresos']:.2f}</td><td>{q['gastos']:.2f}</td><td>{q['beneficio_neto']:.2f}</td><td>{q['margen_operativo']:.2f}</td><td>{q['metrics']['ticket_medio']:.2f}</td><td>{q['metrics']['operaciones']}</td><td>{q['metrics']['margen_pct']:.2f}</td></tr>"
            for q in data['quarters']
        ])
        html = f"""
        <html><head><meta charset="utf-8"><title>Quarterly {empresa} {ejercicio}</title></head>
        <body><h3>Informe Trimestral {empresa} {ejercicio}</h3>
        <table border="1" cellpadding="6" cellspacing="0">
        <thead><tr><th>Quarter</th><th>Ingresos</th><th>Gastos</th><th>Beneficio Neto</th><th>Margen Operativo %</th><th>Ticket Medio</th><th>Operaciones</th><th>Margen Negocio %</th></tr></thead>
        <tbody>{html_rows}</tbody></table></body></html>
        """
        return HttpResponse(html, content_type='text/html')

    return {"status": "error", "message": "Formato no soportado"}

@router.get("/accounts/tree", response=Dict[str, Any])
def get_accounts_tree(request: HttpRequest, empresa: int, ejercicio: int, root: str = 'ingresos', start_level: int = 3, end_level: int = 6):
    service = FinancialService()
    return service.get_accounts_tree(empresa, ejercicio, root, start_level, end_level)

@router.get("/accounts/detail", response=Dict[str, Any])
def get_account_detail(request: HttpRequest, empresa: int, ejercicio: int, code: str):
    service = FinancialService()
    return service.get_account_detail(empresa, ejercicio, code)

@router.get("/accounts/breakdown", response=Dict[str, Any])
def get_account_breakdown(request: HttpRequest, empresa: int, ejercicio: int, code: str):
    """
    Returns deepest-level breakdown under a given account prefix.
    """
    service = FinancialService()
    return service.get_account_breakdown(empresa, ejercicio, code)

@router.get("/infografia", response=Dict[str, Any])
def get_infografia(request: HttpRequest, empresa: int, ejercicio: int):
    ai_dir = getattr(settings, "DATIA_AI_CONTEXT_DIR", settings.BASE_DIR)
    fin_path = os.path.join(ai_dir, f"datia_ai_context_financiera_{empresa}_{ejercicio}.json")
    ven_path = os.path.join(ai_dir, f"datia_ai_context_ventas_{empresa}_{ejercicio}.json")
    if not os.path.exists(fin_path):
        return {"status": "error", "message": "JSON financiero no encontrado"}
    try:
        with open(fin_path, "r", encoding="utf-8") as f:
            fin = json.load(f)
    except Exception as e:
        return {"status": "error", "message": str(e)}
    ventas_ctx = None
    if os.path.exists(ven_path):
        try:
            with open(ven_path, "r", encoding="utf-8") as vf:
                ventas_ctx = json.load(vf)
        except:
            ventas_ctx = None
    kpis = fin.get("kpis_globales") or {}
    ratios = ((fin.get("balance_situacion") or {}).get("ratios")) or {}
    series = fin.get("series_mensuales") or {}
    estac = fin.get("estacionalidad") or []
    ventas_totales = float(kpis.get("ventas") or 0)
    solvencia = float(ratios.get("solvencia") or 0)
    margen_op_pct = float(kpis.get("margen_op_pct") or 0)
    yoy_vals = [float(x.get("yoy_pct") or 0) for x in estac] if isinstance(estac, list) else []
    yoy_global = float(mean(yoy_vals)) if yoy_vals else 0.0
    ingresos_m = series.get("ingresos") or []
    ebitda_m = series.get("ebitda") or []
    margen_m = series.get("margen_pct") or []
    def qsum(arr, qi):
        if not isinstance(arr, list) or len(arr) < 12:
            return None
        i = (qi - 1) * 3
        s = [x for x in arr[i:i+3] if x is not None]
        return float(sum(s)) if s else None
    def qavg(arr, qi):
        if not isinstance(arr, list) or len(arr) < 12:
            return None
        i = (qi - 1) * 3
        s = [x for x in arr[i:i+3] if x is not None]
        return float(sum(s) / float(len(s))) if s else None
    v_q = {"Q1": qsum(ingresos_m, 1), "Q2": qsum(ingresos_m, 2), "Q3": qsum(ingresos_m, 3), "Q4": qsum(ingresos_m, 4)}
    m_q = {"Q1": qavg(margen_m, 1), "Q2": qavg(margen_m, 2), "Q3": qavg(margen_m, 3), "Q4": qavg(margen_m, 4)}
    e_q = {"Q1": qsum(ebitda_m, 1), "Q2": qsum(ebitda_m, 2), "Q3": qsum(ebitda_m, 3), "Q4": qsum(ebitda_m, 4)}
    productos_top = []
    if ventas_ctx and isinstance(ventas_ctx.get("top_productos"), list):
        for p in ventas_ctx.get("top_productos")[:3]:
            nombre = p.get("nombre") or "Producto"
            ingresos = float(p.get("ingresos_generados") or 0)
            productos_top.append({"nombre": nombre, "ingresos": ingresos})
    dto = {
        "status": "ok",
        "empresa": empresa,
        "ejercicio": ejercicio,
        "kpis": {
            "ventas_totales": ventas_totales,
            "yoy_pct_global": yoy_global,
            "solvencia": solvencia,
            "margen_op_pct": margen_op_pct
        },
        "trimestres": {
            "ventas": v_q,
            "margen_pct": m_q,
            "ebitda": e_q
        },
        "productos_top": productos_top,
        "meta": {
            "origen": "json",
            "fuentes_n": 1 + (1 if ventas_ctx else 0)
        },
        "raw_fin": fin,
        "raw_ventas": ventas_ctx or {}
    }
    return dto

@router.post("/preferences/layout")
def save_dashboard_layout(request: HttpRequest, layout: Dict[str, Any] = None):
    """
    Saves user dashboard layout preferences.
    """
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    
    try:
        try:
            raw = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            raw = {}
        data = None
        if isinstance(raw, dict) and raw:
            data = raw.get('layout') if 'layout' in raw else raw
        if data is None:
            data = layout if isinstance(layout, dict) else {}
        from datia.models.preferences import UserPreference
        prefs, _ = UserPreference.objects.get_or_create(user=request.user)
        prefs.dashboard_layout = data
        prefs.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/preferences/layout", response=Dict[str, Any])
def get_dashboard_layout(request: HttpRequest):
    """
    Retrieves user dashboard layout preferences.
    """
    if not request.user.is_authenticated:
        return {}
    
    try:
        from datia.models.preferences import UserPreference
        prefs = UserPreference.objects.get(user=request.user)
        return prefs.dashboard_layout
    except:
        return {}

# --- UI Preferences (Logo & Accent Color) ---
# --- UI Preferences (Logo & Accent Color) ---
class UIPreferences(Schema):
    selected_logo: str = None
    accent_color: str = None

@router.post("/preferences/ui")
def save_ui_preferences(request: HttpRequest, prefs: UIPreferences):
    """
    Saves user UI preferences such as selected logo and accent color
    inside dashboard_layout['ui_prefs'] to avoid DB migrations.
    """
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    try:
        from datia.models.preferences import UserPreference
        uprefs, _ = UserPreference.objects.get_or_create(user=request.user)
        data = uprefs.dashboard_layout or {}
        ui = data.get('ui_prefs', {})
        if prefs.selected_logo is not None:
            ui['selected_logo'] = prefs.selected_logo
        if prefs.accent_color is not None:
            ui['accent_color'] = prefs.accent_color
        data['ui_prefs'] = ui
        uprefs.dashboard_layout = data
        uprefs.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/preferences/ui", response=Dict[str, Any])
def get_ui_preferences(request: HttpRequest):
    """
    Retrieves user UI preferences (selected_logo, accent_color)
    from dashboard_layout['ui_prefs'].
    """
    if not request.user.is_authenticated:
        return {}
    try:
        from datia.models.preferences import UserPreference
        uprefs = UserPreference.objects.get(user=request.user)
        data = uprefs.dashboard_layout or {}
        ui = data.get('ui_prefs', {})
        return {
            "selected_logo": ui.get("selected_logo", ""),
            "accent_color": ui.get("accent_color", "")
        }
    except Exception:
        return {}

# --- Pool UI Preferences (Default Bank/Tipo) ---
class PoolUIPrefs(Schema):
    default_bank_id: Optional[int] = None
    default_tipo: Optional[str] = None

@router.post("/pool/preferences", response=Dict[str, Any])
def save_pool_ui_prefs(request: HttpRequest, prefs: PoolUIPrefs):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    try:
        from datia.models.preferences import UserPreference
        uprefs, _ = UserPreference.objects.get_or_create(user=request.user)
        data = uprefs.dashboard_layout or {}
        pool = data.get('pool_prefs', {})
        if prefs.default_bank_id is not None:
            pool['default_bank_id'] = prefs.default_bank_id
        if prefs.default_tipo is not None:
            pool['default_tipo'] = prefs.default_tipo
        data['pool_prefs'] = pool
        uprefs.dashboard_layout = data
        uprefs.save()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/pool/preferences", response=Dict[str, Any])
def get_pool_ui_prefs(request: HttpRequest):
    if not request.user.is_authenticated:
        return {}
    try:
        from datia.models.preferences import UserPreference
        uprefs = UserPreference.objects.get(user=request.user)
        data = uprefs.dashboard_layout or {}
        pool = data.get('pool_prefs', {})
        return {
            "default_bank_id": pool.get("default_bank_id"),
            "default_tipo": pool.get("default_tipo")
        }
    except Exception:
        return {}

@router.post("/sync")
def sync_financials(request: HttpRequest, empresa: int, ejercicio: int):
    """
    Triggers manual sync of financial data.
    """
    etl = ETLService()
    # Using the generator in a blocking way for HTTP response (simplified)
    # Ideally should be streaming or background task
    msgs = []
    for update in etl.sync_mssql_financial_generator(empresa, ejercicio):
        msgs.append(str(update))
    return {"status": "ok", "logs": len(msgs)}

@router.get("/treasury", response=Dict[str, Any])
def get_treasury_snapshot(request: HttpRequest, empresa: int, ejercicio: int):
    """
    Returns treasury analysis (Cash, Aging, Working Capital).
    """
    service = FinancialService()
    return service.get_treasury_snapshot(empresa, ejercicio)

@router.get("/treasury/receivables_breakdown", response=Dict[str, Any])
def get_receivables_breakdown(request: HttpRequest, empresa: int, ejercicio: int, level: int = 3):
    """
    Returns breakdown of receivables (Group 43) aggregated by account code level.
    """
    service = FinancialService()
    return service.get_receivables_breakdown(empresa, ejercicio, level)

@router.get("/treasury/receivables_breakdown_detail", response=Dict[str, Any])
def get_receivables_breakdown_detail(request: HttpRequest, empresa: int, ejercicio: int, parent: str, level: int = 6):
    """
    Returns drilldown of receivables for a parent account prefix aggregated by target level.
    """
    service = FinancialService()
    return service.get_receivables_breakdown_detail(empresa, ejercicio, parent, level)
@router.get("/treasury/receivables_breakdown_flat", response=Dict[str, Any])
def get_receivables_breakdown_flat(request: HttpRequest, empresa: int, ejercicio: int, parent: str):
    """
    Returns full expansion (leaf accounts) under a level-3 parent prefix.
    """
    service = FinancialService()
    return service.get_receivables_breakdown_flat(empresa, ejercicio, parent)
@router.get("/treasury/cartera_clients_bucket", response=Dict[str, Any])
def get_cartera_clients_bucket(request: HttpRequest, empresa: int, ejercicio: int, bucket: str):
    """
    Returns list of clients and gross 'importe' for a given absolute bucket (0-30, 30-60, 60-90, >90).
    """
    service = FinancialService()
    return service.get_cartera_clients_bucket(empresa, ejercicio, bucket)

@router.get("/treasury/cartera_importe_codes", response=Dict[str, Any])
def get_cartera_importe_codes(request: HttpRequest, empresa: int, ejercicio: int, codes: str):
    """
    Returns a map {code: total_importe} for requested account codes/prefixes.
    """
    service = FinancialService()
    code_list = [c.strip() for c in (codes or '').split(',') if c.strip()]
    return service.get_cartera_importe_codes(empresa, ejercicio, code_list)
@router.get("/treasury/forecast", response=Dict[str, Any])
def get_treasury_forecast(request: HttpRequest, empresa: int, ejercicio: int, horizon: int = 6, cobro_anticipado_pct: float = 0.0, diferir_pagos_pct: float = 0.0, prob_default_pct: float = 0.0, umbral_liquidez: float = 1.5):
    """
    Returns cash flow forecast (inflows, outflows, projected balance and liquidity ratio).
    Allows scenario tuning via parameters.
    """
    service = FinancialService()
    return service.get_treasury_forecast(
        empresa,
        ejercicio,
        months=int(horizon or 6),
        cobro_anticipado_pct=float(cobro_anticipado_pct or 0.0),
        diferir_pagos_pct=float(diferir_pagos_pct or 0.0),
        prob_default_pct=float(prob_default_pct or 0.0),
        umbral_liquidez=float(umbral_liquidez or 1.5),
    )

@router.get("/treasury/forecast/export")
def export_treasury_forecast(request: HttpRequest, empresa: int, ejercicio: int, horizon: int = 6, cobro_anticipado_pct: float = 0.0, diferir_pagos_pct: float = 0.0, prob_default_pct: float = 0.0, umbral_liquidez: float = 1.5, format: str = 'csv'):
    """
    Exports treasury forecast to CSV or a simple printable HTML (PDF via browser print).
    """
    service = FinancialService()
    data = service.get_treasury_forecast(
        empresa,
        ejercicio,
        months=int(horizon or 6),
        cobro_anticipado_pct=float(cobro_anticipado_pct or 0.0),
        diferir_pagos_pct=float(diferir_pagos_pct or 0.0),
        prob_default_pct=float(prob_default_pct or 0.0),
        umbral_liquidez=float(umbral_liquidez or 1.5),
    )
    fc = data.get('forecast', []) or []
    alerts = data.get('alerts', []) or []
    if format.lower() in ('csv', 'excel', 'xlsx'):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(['Periodo', 'Inflow', 'Outflow', 'Balance', 'Liquidez'])
        for x in fc:
            writer.writerow([x.get('period'), f"{float(x.get('inflow', 0.0)):.2f}", f"{float(x.get('outflow', 0.0)):.2f}", f"{float(x.get('balance', 0.0)):.2f}", f"{float(x.get('ratio', 0.0)):.2f}"])
        if alerts:
            writer.writerow([])
            writer.writerow(['Alertas'])
            writer.writerow(['Periodo', 'Tipo', 'Umbral', 'Valor'])
            for a in alerts:
                writer.writerow([a.get('period'), a.get('type'), f"{float(a.get('threshold', 0.0)):.2f}", f"{float(a.get('value', 0.0)):.2f}"])
        resp = HttpResponse(buffer.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="treasury_forecast_{empresa}_{ejercicio}.csv"'
        return resp
    if format.lower() == 'pdf':
        rows_html = ''.join([
            f"<tr><td>{x.get('period')}</td><td>{float(x.get('inflow',0.0)):.2f}</td><td>{float(x.get('outflow',0.0)):.2f}</td><td>{float(x.get('balance',0.0)):.2f}</td><td>{float(x.get('ratio',0.0)):.2f}</td></tr>"
            for x in fc
        ])
        alerts_html = ''.join([
            f"<tr><td>{a.get('period')}</td><td>{a.get('type')}</td><td>{float(a.get('threshold',0.0)):.2f}</td><td>{float(a.get('value',0.0)):.2f}</td></tr>"
            for a in alerts
        ])
        html = f"""
        <html><head><meta charset="utf-8"><title>Tesorería {empresa} {ejercicio}</title></head>
        <body><h3>Forecast de Tesorería {empresa} {ejercicio}</h3>
        <table border="1" cellpadding="6" cellspacing="0">
        <thead><tr><th>Periodo</th><th>Inflow</th><th>Outflow</th><th>Balance</th><th>Liquidez</th></tr></thead>
        <tbody>{rows_html}</tbody></table>
        <h4>Alertas</h4>
        <table border="1" cellpadding="6" cellspacing="0"><thead><tr><th>Periodo</th><th>Tipo</th><th>Umbral</th><th>Valor</th></tr></thead><tbody>{alerts_html}</tbody></table>
        </body></html>
        """
        return HttpResponse(html, content_type='text/html')
    return {"status": "error", "message": "Formato no soportado"}

@router.get("/anatomy/utility", response=Dict[str, Any])
def get_utility_anatomy(request: HttpRequest, empresa: int, start_year: int, end_year: int, moneda: str = 'EUR', region: str = 'global'):
    svc = UtilityAnatomyService()
    return svc.get_anatomy(empresa, int(start_year), int(end_year), moneda, region)

@router.get("/anatomy/forecast", response=Dict[str, Any])
def get_utility_forecast(request: HttpRequest, empresa: int, start_year: int, end_year: int):
    svc = UtilityAnatomyService()
    return svc.get_forecast(empresa, int(start_year), int(end_year))

@router.get("/uninvoiced-lines", response=Dict[str, Any])
def get_uninvoiced_lines(request: HttpRequest, empresa: int, ejercicio: int):
    service = FinancialService()
    return service.get_uninvoiced_lines(empresa, ejercicio)


@router.get("/budgets", response=Dict[str, Any])
def get_budgets(request: HttpRequest, empresa: int, ejercicio: int, group_filter: str = 'PL', base_year: int = None):
    """
    Returns Budget Grid.
    """
    service = FinancialService()
    try:
        return service.get_budget_grid(empresa, ejercicio, group_filter, base_year)
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "rows": [],
            "meta": {"base_year": base_year, "budget_year": ejercicio},
        }

@router.post("/budgets/save")
def save_budget(request: HttpRequest):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}
    empresa = data.get('empresa')
    ejercicio = data.get('ejercicio')
    changes = data.get('changes', [])
    controls = data.get('controls', [])
    notes = data.get('notes', [])
    if not empresa or not ejercicio:
        return {"status": "error", "message": "Missing company/year"}
    try:
        service = FinancialService()
        count = 0
        for ctrl in controls or []:
            cuenta = ctrl.get('cuenta')
            agosto_full = bool(ctrl.get('agosto_full', False))
            line_pct = float(ctrl.get('line_pct', 0))
            if cuenta:
                service.save_budget_controls(empresa, int(ejercicio), str(cuenta), agosto_full, line_pct)
        for change in changes:
            cuenta = change.get('cuenta')
            period = change.get('period')
            val = change.get('value')
            if not cuenta or period is None or val is None:
                continue
            service.save_budget_row(empresa, int(ejercicio), str(cuenta), int(period), float(val))
            count += 1
        saved_notes = 0
        for note in notes or []:
            cuenta = note.get('cuenta')
            period = note.get('period')
            text = note.get('text')
            if not cuenta or period is None:
                continue
            service.save_budget_note(empresa, int(ejercicio), str(cuenta), int(period), str(text or ''))
            saved_notes += 1
        return {"status": "ok", "saved_cells": count, "saved_notes": saved_notes}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/budgets/generate")
def generate_budget(request: HttpRequest):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        data = {}
    try:
        empresa = data.get('empresa')
        ejercicio = data.get('ejercicio')
        base_year = data.get('base_year')
        increment_pct = data.get('increment_pct', 0.0)
        if not empresa or not ejercicio or not base_year:
            return {"status": "error", "message": "Missing parameters"}
        service = FinancialService()
        count = service.generate_initial_budget(empresa, int(ejercicio), int(base_year), float(increment_pct))
        return {"status": "ok", "generated_records": count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/budgets/exists", response=Dict[str, Any])
def budgets_exists(request: HttpRequest, empresa: int, ejercicio: int):
    try:
        from datia.models.financial import DatiaPresupuestos
        from django.db.models import Q
        q = Q(cuenta__startswith='6') | Q(cuenta__startswith='7')
        count = DatiaPresupuestos.objects.filter(empresa=empresa, ejercicio=ejercicio).filter(q).count()
        return {"exists": count > 0, "count": int(count)}
    except Exception as e:
        return {"exists": False, "count": 0, "error": str(e)}


    return StreamingHttpResponse(event_generator(), content_type="text/event-stream")

@router.get("/budgets/comparison", response=Dict[str, Any])
def get_budget_comparison(request: HttpRequest, empresa: str = '', ejercicio: str = ''):
    """
    Returns data for Budget Comparison (Actual vs Budget) including Table and Charts.
    """
    try:
        emp = int(empresa)
        eje = int(ejercicio)
    except (TypeError, ValueError):
        return {
            "status": "no_data",
            "reason": "Missing or invalid empresa/ejercicio",
            "table": [],
            "charts": {"monthly": {}, "cumulative": {}},
        }
    service = FinancialService()
    return service.get_budget_comparison_data(emp, eje)

# -----------------------------
# Pool Bancario (CRUD + Agregados)
# -----------------------------

class BankIn(Schema):
    nombre: str
    swift: str = None
    rating: str = None
    contacto: Dict[str, Any] = None
    activo: bool = True

class AccountIn(Schema):
    bank_id: int
    iban: str
    alias: str = None
    uso: str = None
    activo: bool = True

class InstrumentIn(Schema):
    bank_id: int
    account_id: int = None
    tipo: str
    producto: str = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    renovable: bool = False
    estado: str = 'activo'
    limite: float = 0.0
    base: str = 'euribor'
    diferencial: float = 0.0
    com_apertura: float = 0.0
    com_disponibilidad: float = 0.0
    com_no_disposicion: float = 0.0
    gastos_fijos: float = 0.0
    garantia: Dict[str, Any] = None
    covenants: Dict[str, Any] = None
    notas: str = None

class MapPrefixesIn(Schema):
    prefixes: List[str]

@router.get("/pool/banks", response=List[Dict[str, Any]])
def pool_list_banks(request: HttpRequest, empresa: str):
    try:
        empresa_int = int(str(empresa).strip())
    except Exception:
        return []
    from django.db.utils import ProgrammingError, OperationalError
    try:
        qs = BankingBank.objects.filter(empresa=empresa_int).order_by('nombre')
        return [
            {
                'id': b.id, 'empresa': b.empresa, 'nombre': b.nombre, 'swift': b.swift,
                'rating': b.rating, 'contacto': b.contacto, 'activo': b.activo
            } for b in qs
        ]
    except (ProgrammingError, OperationalError):
        # Si las tablas de pool bancario aún no existen, respondemos lista vacía
        return []

@router.post("/pool/banks", response=Dict[str, Any])
def pool_create_bank(request: HttpRequest, empresa: int, data: BankIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    svc = BankingService()
    bank = svc.create_bank(empresa, data.dict())
    return {'status': 'ok', 'id': bank.id}

@router.put("/pool/banks/{bank_id}", response=Dict[str, Any])
def pool_update_bank(request: HttpRequest, bank_id: int, data: BankIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    svc = BankingService()
    bank = svc.update_bank(bank_id, data.dict())
    return {'status': 'ok', 'id': bank.id}

@router.delete("/pool/banks/{bank_id}", response=Dict[str, Any])
def pool_delete_bank(request: HttpRequest, bank_id: int):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    svc = BankingService()
    svc.delete_bank(bank_id)
    return {'status': 'ok'}

@router.get("/pool/accounts", response=List[Dict[str, Any]])
def pool_list_accounts(request: HttpRequest, empresa: int, bank_id: int = None):
    qs = BankingAccount.objects.filter(empresa=empresa)
    if bank_id:
        qs = qs.filter(bank_id=bank_id)
    return [{
        'id': a.id, 'empresa': a.empresa, 'bank_id': a.bank_id,
        'iban': a.iban, 'alias': a.alias or '', 'uso': a.uso or '', 'activo': a.activo
    } for a in qs]

@router.post("/pool/accounts", response=Dict[str, Any])
def pool_create_account(request: HttpRequest, empresa: int, data: AccountIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    acc = BankingAccount.objects.create(
        empresa=empresa,
        bank_id=data.bank_id,
        iban=data.iban.strip(),
        alias=(data.alias or '').strip() or None,
        uso=(data.uso or '').strip() or None,
        activo=bool(data.activo),
    )
    return {'status': 'ok', 'id': acc.id}

@router.put("/pool/accounts/{account_id}", response=Dict[str, Any])
def pool_update_account(request: HttpRequest, account_id: int, data: AccountIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    acc = BankingAccount.objects.get(id=account_id)
    for f in ['bank_id', 'iban', 'alias', 'uso', 'activo']:
        if hasattr(data, f):
            setattr(acc, f, getattr(data, f))
    if acc.iban:
        acc.iban = acc.iban.strip()
    if acc.alias:
        acc.alias = acc.alias.strip()
    if acc.uso:
        acc.uso = acc.uso.strip()
    acc.save()
    return {'status': 'ok', 'id': acc.id}

@router.delete("/pool/accounts/{account_id}", response=Dict[str, Any])
def pool_delete_account(request: HttpRequest, account_id: int):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    BankingAccount.objects.filter(id=account_id).delete()
    return {'status': 'ok'}

@router.get("/pool/instruments", response=List[Dict[str, Any]])
def pool_list_instruments(request: HttpRequest, empresa: int, bank_id: int = None, tipo: str = None):
    from django.db.utils import ProgrammingError, OperationalError
    try:
        qs = BankingInstrument.objects.filter(empresa=empresa)
        if bank_id:
            qs = qs.filter(bank_id=bank_id)
        if tipo:
            qs = qs.filter(tipo=tipo)
        instruments = list(qs)
    except (ProgrammingError, OperationalError):
        return []
    lst = []
    for inst in instruments:
        lst.append({
            'id': inst.id, 'empresa': inst.empresa, 'bank_id': inst.bank_id,
            'account_id': inst.account_id, 'tipo': inst.tipo, 'producto': inst.producto,
            'fecha_inicio': inst.fecha_inicio.isoformat() if inst.fecha_inicio else None,
            'fecha_fin': inst.fecha_fin.isoformat() if inst.fecha_fin else None,
            'renovable': inst.renovable, 'estado': inst.estado, 'limite': float(inst.limite or 0.0),
            'base': inst.base, 'diferencial': float(inst.diferencial or 0.0),
            'com_apertura': float(inst.com_apertura or 0.0), 'com_disponibilidad': float(inst.com_disponibilidad or 0.0),
            'com_no_disposicion': float(inst.com_no_disposicion or 0.0), 'gastos_fijos': float(inst.gastos_fijos or 0.0),
            'garantia': inst.garantia or {}, 'covenants': inst.covenants or {}, 'notas': inst.notas or ''
        })
    return lst

@router.post("/pool/instruments", response=Dict[str, Any])
def pool_create_instrument(request: HttpRequest, empresa: int, data: InstrumentIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    if data.fecha_inicio and data.fecha_fin and data.fecha_inicio > data.fecha_fin:
        return {"status": "error", "message": "Fecha inicio posterior a fecha fin"}
    inst = BankingInstrument.objects.create(
        empresa=empresa,
        bank_id=data.bank_id,
        account_id=data.account_id,
        tipo=data.tipo,
        producto=data.producto,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        renovable=data.renovable,
        estado=data.estado,
        limite=data.limite,
        base=data.base,
        diferencial=data.diferencial,
        com_apertura=data.com_apertura,
        com_disponibilidad=data.com_disponibilidad,
        com_no_disposicion=data.com_no_disposicion,
        gastos_fijos=data.gastos_fijos,
        garantia=data.garantia or {},
        covenants=data.covenants or {},
        notas=data.notas or ''
    )
    return {'status': 'ok', 'id': inst.id}

@router.put("/pool/instruments/{instrument_id}", response=Dict[str, Any])
def pool_update_instrument(request: HttpRequest, instrument_id: int, data: InstrumentIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    inst = BankingInstrument.objects.get(id=instrument_id)
    if data.fecha_inicio and data.fecha_fin and data.fecha_inicio > data.fecha_fin:
        return {"status": "error", "message": "Fecha inicio posterior a fecha fin"}
    for f, v in data.dict().items():
        setattr(inst, f, v)
    inst.save()
    return {'status': 'ok', 'id': inst.id}

@router.delete("/pool/instruments/{instrument_id}", response=Dict[str, Any])
def pool_delete_instrument(request: HttpRequest, instrument_id: int):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    BankingInstrument.objects.filter(id=instrument_id).delete()
    return {'status': 'ok'}

@router.get("/pool/instruments/{instrument_id}/accounts", response=List[Dict[str, Any]])
def pool_list_maps(request: HttpRequest, instrument_id: int, empresa: int):
    qs = BankingInstrumentAccountMap.objects.filter(empresa=empresa, instrument_id=instrument_id)
    return [{'id': m.id, 'prefix': m.cuenta_prefix, 'prioridad': m.prioridad} for m in qs]

@router.post("/pool/instruments/{instrument_id}/accounts", response=Dict[str, Any])
def pool_add_maps(request: HttpRequest, instrument_id: int, empresa: int, data: MapPrefixesIn):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    prefixes = [p.strip() for p in (data.prefixes or []) if p and p.strip()]
    valid = []
    for p in prefixes:
        if re.fullmatch(r"\d{3,12}", p):
            valid.append(p)
        else:
            return {"status": "error", "message": f"Prefijo inválido: {p}"}
    created = 0
    for i, p in enumerate(valid):
        BankingInstrumentAccountMap.objects.get_or_create(
            empresa=empresa,
            instrument_id=instrument_id,
            cuenta_prefix=p,
            defaults={'prioridad': i}
        )
        created += 1
    return {'status': 'ok', 'created': created}

@router.delete("/pool/instruments/{instrument_id}/accounts/{map_id}", response=Dict[str, Any])
def pool_delete_map(request: HttpRequest, instrument_id: int, map_id: int):
    if not request.user.is_authenticated:
        return {"status": "error", "message": "Unauthorized"}
    BankingInstrumentAccountMap.objects.filter(id=map_id, instrument_id=instrument_id).delete()
    return {'status': 'ok'}

@router.get("/pool/summary", response=Dict[str, Any])
def pool_summary(request: HttpRequest, empresa: int, ejercicio: int, hasta_mes: int = None):
    svc = BankingService()
    until = int(hasta_mes) if hasta_mes is not None else None
    if until is not None and (until < 1 or until > 12):
        until = None
    return svc.get_summary(empresa, ejercicio, until)

@router.get("/pool/concentration", response=Dict[str, Any])
def pool_concentration(request: HttpRequest, empresa: int, ejercicio: int, hasta_mes: int = None):
    svc = BankingService()
    until = int(hasta_mes) if hasta_mes is not None else None
    if until is not None and (until < 1 or until > 12):
        until = None
    return svc.get_concentration(empresa, ejercicio, until)

@router.get("/pool/maturities", response=Dict[str, Any])
def pool_maturities(request: HttpRequest, empresa: int, horizon: int = 12):
    svc = BankingService()
    return svc.get_maturities(empresa, int(horizon or 12))
