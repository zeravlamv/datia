from typing import Dict, Any
from .base import BaseHandler
import os
import logging
from django.conf import settings
from django.db import connections

class SnapshotHandler(BaseHandler):
    def __init__(self, formatter=None):
        super().__init__(formatter)

    def handle(self, intent_data: Dict, context: Dict) -> Dict:
        # Not used via checking intent directly
        return {}

    def _importe_compra_con_datos(self, table, cols, candidatos, emp_col, year_col, empresa, ejercicio):
        existentes = [cols[c] for c in candidatos if c in cols]
        if not existentes:
            return None
        for nombre in existentes:
            rows = self.exec_sql(
                f'SELECT COALESCE(SUM("{nombre}"), 0) AS total FROM {table} '
                f'WHERE {emp_col} = {int(empresa)} AND {year_col} = {int(ejercicio)}'
            )
            total = float((rows and rows[0].get('total')) or 0)
            if total != 0:
                return nombre
        return existentes[0]

    def get_snapshot_metrics(self, empresa: int, ejercicio: int, kind: str = 'sales') -> Dict[str, Any]:
        try:
            logger = logging.getLogger('datia.snapshot')
            log_enabled = os.environ.get('DATIA_LOG_SNAPSHOT', '').lower() in ('1', 'true', 'yes')
            def _dbg(msg):
                if log_enabled:
                    logger.info(msg)

            if kind == 'compras':
                tbl_cab = 'datiadb_cabeceraalbaranproveedor'
                tbl_lin = 'datiadb_lineasalbaranproveedor'
            else:
                tbl_cab = 'datiadb_cabeceraalbarancliente'
                tbl_lin = 'datiadb_lineasalbarancliente'

            try:
                with connections['analytics'].cursor() as c:
                    c.execute(
                        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                        [tbl_cab],
                    )
                    raw_cols = [r[0] for r in c.fetchall()]
                cols = {str(x).lower(): str(x) for x in raw_cols}
            except Exception:
                cols = {}

            def pick(cands):
                for c in cands:
                    k = str(c).lower()
                    if k in cols:
                        return cols[k]
                return None

            emp_col = pick(['codigoempresa', 'empresa', 'empresacodigo'])
            year_col = pick(['ejercicioalbaran', 'ejercicio', 'ejerciciopedido', 'year'])
            date_col = pick(['fechaalbaran', 'fechapedido', 'fecha', 'fecharegistro'])
            num_col = pick(['numeroalbaran', 'numero', 'numalbaran'])
            if not emp_col:
                emp_col = 'codigoempresa'
            if not year_col:
                year_col = 'ejercicioalbaran'
            if not date_col:
                date_col = 'fechaalbaran'
            if not num_col:
                num_col = 'numeroalbaran'

            sql_date = f"""
                SELECT MAX({date_col}) as max_date
                FROM {tbl_cab}
                WHERE {emp_col} = {empresa} AND {year_col} = {ejercicio} AND {date_col} IS NOT NULL
            """
            _dbg(f"DEBUG SNAPSHOT: Executing {sql_date}")
            rows_date = self.exec_sql(sql_date)
            _dbg(f"DEBUG SNAPSHOT: Result {rows_date}")
            
            if not rows_date or not rows_date[0].get('max_date'):
                from datia.models import MetricsTotalesEmpresaEjercicioCompra, MetricsTotalesEmpresaEjercicioProveedor
                from datia.models import MetricsTotalesEmpresaEjercicio, MetricsTotalesEmpresaEjercicioCliente
                MetricModel = MetricsTotalesEmpresaEjercicioCompra if kind == 'compras' else MetricsTotalesEmpresaEjercicio
                metric_cy = MetricModel.objects.filter(empresa=empresa, ejercicio=ejercicio).first()
                if metric_cy:
                    cy_n = float(metric_cy.importe_neto_total) if metric_cy else 0
                    cy_c = float(metric_cy.importe_coste_total) if metric_cy else 0
                    cy_alb = metric_cy.albaranes_count if metric_cy else 0
                    cy_entities = MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa=empresa, ejercicio=ejercicio).count() if kind == 'compras' else MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=ejercicio).count()
                    cy_margin_eur = 0 if kind == 'compras' else cy_n - cy_c
                    cy_margin_pct = 0 if kind == 'compras' else ((cy_margin_eur / cy_n * 100) if cy_n > 0 else 0)
                    cy_ticket = (cy_n / cy_alb) if cy_alb > 0 else 0
                    metric_py = MetricModel.objects.filter(empresa=empresa, ejercicio=ejercicio - 1).first()
                    py_n = float(metric_py.importe_neto_total) if metric_py else 0
                    yoy_growth = ((cy_n - py_n) / py_n * 100) if py_n > 0 else 0
                    zero_metrics = {"neto": 0, "margin": 0, "ticket": 0, "albaranes": 0}
                    return {
                        "latest_date": "-",
                        "date_day": "-", "date_week": "-", "date_month": "-",
                        "m_1d": zero_metrics,
                        "m_7d": zero_metrics,
                        "m_30d": zero_metrics,
                        "global_neto": cy_n,
                        "global_coste": cy_c,
                        "global_margin_eur": cy_margin_eur,
                        "global_margin_pct": cy_margin_pct,
                        "global_albaranes": cy_alb,
                        "global_ticket": cy_ticket,
                        "global_entities": cy_entities,
                        "global_yoy": yoy_growth
                    }
                sql_max_year = f"SELECT MAX({year_col}) as max_year FROM {tbl_cab} WHERE {emp_col} = {empresa}"
                rows_year = self.exec_sql(sql_max_year)
                if rows_year and rows_year[0].get('max_year'):
                    fallback_year = int(rows_year[0]['max_year'])
                    if fallback_year != ejercicio:
                        result = self.get_snapshot_metrics(empresa, fallback_year, kind)
                        result['is_fallback'] = True
                        result['displayed_ejercicio'] = fallback_year
                        result['original_ejercicio'] = ejercicio
                        return result
                zero_metrics = {"neto": 0, "margin": 0, "ticket": 0, "albaranes": 0}
                return {
                    "latest_date": "-",
                    "date_day": "-", "date_week": "-", "date_month": "-",
                    "m_1d": zero_metrics,
                    "m_7d": zero_metrics,
                    "m_30d": zero_metrics,
                    "global_neto": 0,
                    "global_coste": 0,
                    "global_margin_eur": 0,
                    "global_margin_pct": 0,
                    "global_albaranes": 0,
                    "global_ticket": 0,
                    "global_entities": 0,
                    "global_yoy": 0
                }
            
            latest_raw = rows_date[0]['max_date']
            try:
                from datetime import date, datetime
                if isinstance(latest_raw, datetime):
                    latest_date_str = latest_raw.strftime("%Y-%m-%d")
                elif isinstance(latest_raw, date):
                    latest_date_str = latest_raw.strftime("%Y-%m-%d")
                else:
                    latest_date_str = str(latest_raw)[:10]
            except Exception:
                latest_date_str = str(latest_raw)[:10]
            
            # Helper Helper to get metrics for a date range
            def get_metrics_for_range(start_date, end_date):
                if kind == 'compras':
                    compras_net_col = self._importe_compra_con_datos(
                        tbl_cab, cols, ['importeliquido', 'importeneto', 'baseimponible', 'importebruto'],
                        emp_col, year_col, empresa, ejercicio,
                    ) or "importeliquido"
                    try:
                        override = getattr(settings, "DATIA_SNAPSHOT_PURCHASES_NET_COL", None)
                        if override and str(override).lower() in cols:
                            compras_net_col = cols[str(override).lower()]
                    except Exception:
                        pass
                    sql = f"""
                        SELECT 
                            SUM("{compras_net_col}") as neto,
                            0 as coste,
                            COUNT(DISTINCT {num_col}) as albaranes
                        FROM {tbl_cab} T
                        WHERE {emp_col} = {empresa} AND {year_col} = {ejercicio}
                        AND {date_col} >= '{start_date}' AND {date_col} <= '{end_date}'
                    """
                else:
                    net_col = pick(['importeneto', 'importeliquido', 'baseimponible']) or "importeneto"
                    coste_col = None
                    try:
                        override = getattr(settings, "DATIA_SNAPSHOT_SALES_NET_COL", None)
                        if override and str(override).lower() in cols:
                            net_col = cols[str(override).lower()]
                    except Exception:
                        pass
                    try:
                        override_cost = getattr(settings, "DATIA_SNAPSHOT_SALES_COSTE_COL", None)
                        if override_cost and str(override_cost).lower() in cols:
                            coste_col = cols[str(override_cost).lower()]
                    except Exception:
                        coste_col = None
                    select_coste = f'SUM("{coste_col}")' if coste_col else """
                        SUM(
                            COALESCE(
                                (to_jsonb(T)->>'importecosdte')::numeric,
                                (to_jsonb(T)->>'importecoste')::numeric,
                                (to_jsonb(T)->>'costetotal')::numeric,
                                (to_jsonb(T)->>'importe_coste')::numeric,
                                (to_jsonb(T)->>'importecostetotal')::numeric,
                                (to_jsonb(T)->>'importetotalcoste')::numeric,
                                0
                            )
                        )
                    """
                    sql = f"""
                        SELECT 
                            SUM("{net_col}") as neto,
                            {select_coste} as coste,
                            COUNT(DISTINCT {num_col}) as albaranes
                        FROM {tbl_cab} T
                        WHERE {emp_col} = {empresa} AND {year_col} = {ejercicio}
                        AND {date_col} >= '{start_date}' AND {date_col} <= '{end_date}'
                    """
                rows = self.exec_sql(sql)
                n = float((rows and rows[0].get('neto')) or 0)
                c = float((rows and rows[0].get('coste')) or 0) if kind != 'compras' else 0.0
                alb = int((rows and rows[0].get('albaranes')) or 0)
                
                if kind == 'compras':
                    margin = 0 # No margin concept on pure spend snapshot
                else:
                    margin = ((n - c) / n * 100) if n > 0 else 0

                ticket = (n / alb) if alb > 0 else 0
                
                result = {
                    "neto": n,
                    "coste": c,
                    "margin": round(margin, 2),
                    "margin_eur": (n - c) if kind != 'compras' else 0,
                    "ticket": round(ticket, 2),
                    "albaranes": alb,
                }
                return result

            from datetime import datetime, timedelta
            latest_dt = datetime.strptime(latest_date_str, "%Y-%m-%d")
            
            # 1. Day Stats (1d)
            m_1d = get_metrics_for_range(latest_date_str, latest_date_str)
            
            # 2. Week Stats (7d)
            start_7d = (latest_dt - timedelta(days=6)).strftime("%Y-%m-%d")
            m_7d = get_metrics_for_range(start_7d, latest_date_str)
            
            # 3. Month Stats (30d)
            start_30d = (latest_dt - timedelta(days=29)).strftime("%Y-%m-%d")
            m_30d = get_metrics_for_range(start_30d, latest_date_str)
            
            prev_1d_start = (latest_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            prev_1d_end = prev_1d_start
            prev_1d = get_metrics_for_range(prev_1d_start, prev_1d_end)
            
            prev_7d_start = (latest_dt - timedelta(days=13)).strftime("%Y-%m-%d")
            prev_7d_end = (latest_dt - timedelta(days=7)).strftime("%Y-%m-%d")
            prev_7d = get_metrics_for_range(prev_7d_start, prev_7d_end)
            
            prev_30d_start = (latest_dt - timedelta(days=59)).strftime("%Y-%m-%d")
            prev_30d_end = (latest_dt - timedelta(days=30)).strftime("%Y-%m-%d")
            prev_30d = get_metrics_for_range(prev_30d_start, prev_30d_end)
            
            def _add_comp(curr, prev):
                pn = float(prev.get('neto') or 0)
                pt = float(prev.get('ticket') or 0)
                po = int(prev.get('albaranes') or 0)
                cn = float(curr.get('neto') or 0)
                ct = float(curr.get('ticket') or 0)
                co = int(curr.get('albaranes') or 0)
                curr['prev'] = pn
                curr['pct'] = round(((cn - pn) / pn * 100) if pn > 0 else 0, 2)
                curr['prev_ticket'] = pt
                curr['pct_ticket'] = round(((ct - pt) / pt * 100) if pt > 0 else 0, 2)
                curr['prev_ops'] = po
                curr['pct_ops'] = round(((co - po) / po * 100) if po > 0 else 0, 2)
                return curr
            
            m_1d = _add_comp(m_1d, prev_1d)
            m_7d = _add_comp(m_7d, prev_7d)
            m_30d = _add_comp(m_30d, prev_30d)

            # 5. Global KPIs & YoY (Current Year vs Previous Year)
            # Use Aggregated Metrics (NF-023 Refactor)
            from datia.models import MetricsTotalesEmpresaEjercicioCompra, MetricsTotalesEmpresaEjercicioProveedor
            from datia.models import MetricsTotalesEmpresaEjercicio # [FIX] Import Sales Model

            # Determine Model Class based on Kind
            if kind == 'compras':
                MetricModel = MetricsTotalesEmpresaEjercicioCompra
            else:
                MetricModel = MetricsTotalesEmpresaEjercicio

            # Current Year Stats
            cy_neto = 0
            cy_coste = 0
            cy_albaranes = 0
            cy_entities = 0
            
            # Fetch Global Totals
            metric_cy = MetricModel.objects.filter(empresa=empresa, ejercicio=ejercicio).first()
            if metric_cy:
                cy_neto = float(metric_cy.importe_neto_total)
                cy_coste = float(metric_cy.importe_coste_total)
                cy_albaranes = metric_cy.albaranes_count
            
            # Fetch Entities Count
            if kind == 'compras':
                cy_entities = MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa=empresa, ejercicio=ejercicio).count()
            else:
                try:
                    from datia.models import MetricsTotalesEmpresaEjercicioCliente
                    cy_entities = MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=ejercicio).count()
                except Exception:
                    cy_entities = 0

            # Margins & Averages
            cy_margin_eur = cy_neto - cy_coste
            cy_margin_pct = (cy_margin_eur / cy_neto * 100) if cy_neto > 0 else 0
            if kind == 'compras' and cy_albaranes == 0:
                try:
                    sql_ops = f"""
                        SELECT COUNT(DISTINCT "numeroalbaran") as ops
                        FROM {tbl_cab}
                        WHERE "codigoempresa" = {empresa} AND "ejercicio" = {ejercicio}
                    """
                    rows_ops = self.exec_sql(sql_ops)
                    ops_year = int((rows_ops and rows_ops[0].get('ops')) or 0)
                    if ops_year > 0:
                        cy_albaranes = ops_year
                except Exception:
                    pass

            if kind == 'compras':
                cur = connections['analytics'].cursor()
                cur.execute(
                    "SELECT COALESCE(SUM(importe_neto_total),0), COUNT(*) FROM metrics_totales_empresa_ejercicio_compra_mes WHERE empresa=%s AND ejercicio=%s AND mes BETWEEN 1 AND 12",
                    [empresa, ejercicio]
                )
                row = cur.fetchone()
                s, m = float(row[0] or 0), int(row[1] or 0)
                cy_ticket = (s / m) if m > 0 else (cy_neto / cy_albaranes if cy_albaranes > 0 else 0)
            else:
                cy_ticket = (cy_neto / cy_albaranes) if cy_albaranes > 0 else 0
            if kind == 'compras':
                cy_margin_eur = 0
                cy_margin_pct = 0
            
            metric_py = MetricModel.objects.filter(empresa=empresa, ejercicio=ejercicio - 1).first()
            py_neto = float(metric_py.importe_neto_total) if metric_py else 0
            
            # Growth
            yoy_growth = ((cy_neto - py_neto) / py_neto * 100) if py_neto > 0 else 0

            # Date Strings
            day_str = latest_dt.strftime("%d/%m")
            week_str = f"{start_7d[8:]}/{start_7d[5:7]} - {latest_dt.strftime('%d/%m')}"
            month_str = f"{start_30d[8:]}/{start_30d[5:7]} - {latest_dt.strftime('%d/%m')}"

            return {
                "latest_date": latest_date_str,
                "date_day": day_str,
                "date_week": week_str,
                "date_month": month_str,
                
                # New Structured Data for 3x3 Grid
                "m_1d": m_1d,
                "m_7d": m_7d,
                "m_30d": m_30d,

                # Legacy/Fallbacks
                "day": m_1d['neto'],
                "week": m_7d['neto'],
                "month": m_30d['neto'],

                "global_neto": cy_neto,
                "global_coste": cy_coste,
                "global_margin_eur": cy_margin_eur,
                "global_margin_pct": cy_margin_pct,
                "global_albaranes": cy_albaranes,
                "global_ticket": cy_ticket,
                "global_entities": cy_entities,
                "global_yoy": yoy_growth
            }

        except Exception as e:
            return {"error": str(e)}
