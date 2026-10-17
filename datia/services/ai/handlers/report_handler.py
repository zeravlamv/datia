from datia.services.ai.handlers.base import BaseHandler
from datia.models import DataSource, DataField
from django.utils import translation
import logging
from typing import Dict, Any, List
import datetime
from django.db import connections

logger = logging.getLogger(__name__)

class ReportHandler(BaseHandler):
    """
    Handler especializado en generar 'Dossiers Ejecutivos' (Reportes Completos).
    Utiliza el mapeo semántico (DataSource/DataField) para encontrar las tablas correctas
    dinámicamente, en lugar de asumir nombres fijos.
    """
    
    # Internal Translation Dictionary (Avoids .po compilation dependency for dynamic content)
    TRANS = {
        'es': {
            'exec_summary': "Resumen Ejecutivo",
            'net_sales': "Ventas Netas",
            'gross_margin': "Margen Bruto",
            'avg_ticket': "Ticket Medio",
            'situation_report': "Informe de Situación",
            'positive': "positivo",
            'challenging': "retador",
            'closing_vol': "cerrando con un volumen de negocio de",
            'prev_year': "vs año anterior",
            'health_robust': "La salud financiera es robusta, manteniendo un margen bruto del",
            'health_pressure': "Se observa presión en la rentabilidad con un margen del",
            'suggest_review': "lo que sugiere revisar la estructura de costes o precios",
            'gen_profit': "generando un beneficio bruto de",
            'ops_efficiency': "Eficiencia y Compras",
            'ops_managed': "Se han gestionado",
            'ops_sales': "operaciones de venta",
            'purch_vol': "El volumen de compras asciende a",
            'coverage_ratio': "Ratio de cobertura",
            'best_quarter': "El mejor trimestre ha sido el",
            'market_pos': "Posición de Mercado",
            'comm_leader': "Liderazgo comercial",
            'star_prod': "Producto estrella",
            'observation': "Observación",
            'rec_sales_drop': "La caída en ventas requiere un plan de acción comercial inmediato para recuperar cuota de mercado.",
            'rec_margin_low': "Prioridad: Optimizar el mix de productos para elevar el margen bruto por encima del 15%.",
            'rec_consolidate': "Estrategia: Consolidar el crecimiento fidelizando a los clientes del Tier 1 (Pareto).",
            'top_clients': "Top Clientes",
            'top_products': "Top Productos",
            'concentration': "Concentración Clientes",
            'evolution': "Evolución Mensual de Ventas",
            'quarterly': "Comparativa Trimestral",
            'purchases': "Compras",
            'processed': "Datos procesados correctamente. Visualice los gráficos adjuntos para más detalle.",
            'months': ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
            'unknown': "Desconocido"
        },
        'en': {
            'exec_summary': "Executive Summary",
            'net_sales': "Net Sales",
            'gross_margin': "Gross Margin",
            'avg_ticket': "Avg Ticket",
            'situation_report': "Situation Report",
            'positive': "positive",
            'challenging': "challenging",
            'closing_vol': "closing with a business volume of",
            'prev_year': "vs prev year",
            'health_robust': "Financial health is robust, maintaining a gross margin of",
            'health_pressure': "Profitability pressure is observed with a margin of",
            'suggest_review': "suggesting a review of cost or pricing structure",
            'gen_profit': "generating a gross profit of",
            'ops_efficiency': "Efficiency & Purchases",
            'ops_managed': "Managed",
            'ops_sales': "sales operations",
            'purch_vol': "Purchase volume amounts to",
            'coverage_ratio': "Coverage ratio",
            'best_quarter': "The best quarter was",
            'market_pos': "Market Position",
            'comm_leader': "Commercial leadership",
            'star_prod': "Star product",
            'observation': "Observation",
            'rec_sales_drop': "The drop in sales requires an immediate commercial action plan to recover market share.",
            'rec_margin_low': "Priority: Optimize product mix to raise gross margin above 15%.",
            'rec_consolidate': "Strategy: Consolidate growth by retaining Tier 1 (Pareto) customers.",
            'top_clients': "Top Clients",
            'top_products': "Top Products",
            'concentration': "Client Concentration",
            'evolution': "Monthly Sales Evolution",
            'quarterly': "Quarterly Comparison",
            'purchases': "Purchases",
            'processed': "Data processed successfully. See attached charts for details.",
            'unknown': "Unknown",
            'estimated': "Estimated",
            'sales_eur': "Sales (€)",
            'months': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        },
        'ca': {
            'exec_summary': "Resum Executiu",
            'net_sales': "Vendes Netes",
            'gross_margin': "Marge Brut",
            'avg_ticket': "Tiquet Mig",
            'situation_report': "Informe de Situació",
            'positive': "positiu",
            'challenging': "reptador",
            'closing_vol': "tancant amb un volum de negoci de",
            'prev_year': "vs any anterior",
            'health_robust': "La salut financera és robusta, mantenint un marge brut del",
            'health_pressure': "S'observa pressió en la rendibilitat amb un marge del",
            'suggest_review': "el que suggereix revisar l'estructura de costos o preus",
            'gen_profit': "generant un benefici brut de",
            'ops_efficiency': "Eficiència i Compres",
            'ops_managed': "S'han gestionat",
            'ops_sales': "operacions de venda",
            'purch_vol': "El volum de compres ascendeix a",
            'coverage_ratio': "Ràtio de cobertura",
            'best_quarter': "El millor trimestre ha estat el",
            'market_pos': "Posició de Mercat",
            'comm_leader': "Lideratge comercial",
            'star_prod': "Producte estrella",
            'observation': "Observació",
            'rec_sales_drop': "La caiguda en vendes requereix un pla d'acció comercial immediat per recuperar quota de mercat.",
            'rec_margin_low': "Prioritat: Optimitzar el mix de productes per elevar el marge brut per sobre del 15%.",
            'rec_consolidate': "Estratègia: Consolidar el creixement fidelitzant els clients del Tier 1 (Pareto).",
            'top_clients': "Top Clients",
            'top_products': "Top Productes",
            'concentration': "Concentració Clients",
            'evolution': "Evolució Mensual de Vendes",
            'quarterly': "Comparativa Trimestral",
            'purchases': "Compres",
            'processed': "Dades processades correctament. Visualitzeu els gràfics adjunts per a més detalls.",
            'unknown': "Desconegut",
            'estimated': "Estimat",
            'sales_eur': "Vendes (€)",
            'months': ['Gen', 'Feb', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Des']
        }
    }

    def _t(self, key):
        """Translate key based on active language"""
        lang = translation.get_language() or 'es'
        # Fallback to 'es' if lang not found
        if lang not in self.TRANS: lang = 'es'
        return self.TRANS[lang].get(key, key)

    def handle(self, intent_data: Dict, context: Dict) -> Dict[str, Any]:
        """
        Genera el payload completo del reporte alineando KPIs con PGC (Financiera).
        Versión: Consultor Experto V4 (PGC-first + visualización ECharts)
        """
        try:
            import os
            from django.conf import settings
            if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                print("DEBUG: ReportHandler.handle started (Consultant V3 - Safe Mode)")
            empresa = context.get('empresa')
            try:
                empresa = int(str(empresa).strip())
            except Exception:
                empresa = 0
            ejercicio = context.get('ejercicio')
            
            try:
                year_curr = int(ejercicio)
            except:
                year_curr = datetime.datetime.now().year
                
            year_prev = year_curr - 1
            
            # 1. KPIs Globales
            kpis_data = self._get_pgc_kpis_advanced(empresa, year_curr, year_prev)
            kpis = kpis_data['cards']
            stats = kpis_data['stats'] 
            
            # 2. Evolución
            evolution = self._get_pgc_monthly_kpis(empresa, year_curr, year_prev)
            quarterly = self._get_pgc_quarterly(empresa, year_curr, year_prev)
            
            # 3. Rankings
            rank_clients = self._get_metrics_rankings(empresa, year_curr)
            rank_products = self._get_metrics_top_products(empresa, year_curr)
            
            # 4. Compras
            purchases = self._get_metrics_purchases_advanced(empresa, year_curr, year_prev)
            
            # 5. PGC drivers (P&L masas + per100)
            pl_masses = self._get_pgc_pl_masses(int(empresa), int(year_curr), int(year_prev))
            per100 = self._get_pgc_per100(int(empresa), int(year_curr))

            # --- NARRATIVA CONSULTOR (SAFE WRAPPED) ---
            try:
                consultant_text = self._generate_consultant_narrative(year_curr, stats, rank_clients, rank_products, purchases, quarterly, pl_masses=pl_masses, per100=per100)
            except Exception as narrative_error:
                logger.error(f"Narrative Generation Failed: {narrative_error}")
                consultant_text = f"**Resumen Ejecutivo {year_curr}**\n\nDatos procesados correctamente. Visualice los gráficos adjuntos para más detalle."

            data = {
                'type': 'report',
                'source': 'ai_gen',
                'key': 'report_executive',
                'text': consultant_text,
                'answer': consultant_text,
                'sql': None,
                'empresa': empresa,
                'ejercicio': year_curr,
                'generated_at': datetime.datetime.now().isoformat(),
                'kpis': kpis,
                'evolution': evolution,
                'rankings': rank_clients,
                'top_products': rank_products,
                'purchases': purchases,
                'pl_masses': pl_masses,
                'per100': per100,
                'chart_config': self._build_chart_financial_monthly(evolution, year_curr),
                'chart_quarters': self._build_chart_quarters(quarterly, year_curr, year_prev),
                'chart_pareto_clients': self._build_chart_pareto(rank_clients['clients'], "Top Clientes"),
                'chart_pareto_products': self._build_chart_pareto(rank_products, "Top Productos"),
                'chart_concentration': self._build_chart_pie(
                    rank_clients['clients'][:5],
                    f"{self._t('concentration')} (Top {min(5, len(rank_clients['clients']))})"
                )
            }
            return data

        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"ReportHandler Critical Error: {e}")
            raise e

    def _get_pgc_pl_masses(self, empresa: int, year_curr: int, year_prev: int) -> Dict[str, Any]:
        from datia.services.financial_service import FinancialService
        svc = FinancialService()
        cy = svc.get_pl_report(int(empresa), int(year_curr), level=2) or {}
        py = svc.get_pl_report(int(empresa), int(year_prev), level=2) or {}
        cy_rows = [r for r in (cy.get('rows') or []) if r.get('is_header')]
        py_rows = [r for r in (py.get('rows') or []) if r.get('is_header')]
        cy_map = {str(r.get('descripcion') or ''): float(r.get('valor') or 0) for r in cy_rows}
        py_map = {str(r.get('descripcion') or ''): float(r.get('valor') or 0) for r in py_rows}
        labels = list(dict.fromkeys([str(r.get('descripcion') or '') for r in cy_rows if r.get('descripcion')]))
        return {
            'empresa': int(empresa),
            'year_curr': int(year_curr),
            'year_prev': int(year_prev),
            'labels': labels,
            'cy': cy_map,
            'py': py_map,
        }

    def _get_pgc_per100(self, empresa: int, year_curr: int) -> Dict[str, Any]:
        from datia.services.financial_service import FinancialService
        return FinancialService().get_per100(int(empresa), int(year_curr), eq_mode=False) or {}

    def _fmt(self, val, decimals=0):
        """Helper para formato europeo (1.234,56)"""
        if val is None: return "0"
        try:
            f_val = float(val)
        except:
            return str(val)
            
        # US Format first: 1,234.56
        s = f"{f_val:,.{decimals}f}"
        # Swap chars
        return s.replace(',', 'X').replace('.', ',').replace('X', '.')

    def _get_pgc_kpis_advanced(self, empresa, year_curr, year_prev):
        from datia.services.financial_service import FinancialService
        snap = FinancialService().get_snapshot(int(empresa), int(year_curr))
        curr = {
            'ingresos': float(snap.get('ingresos') or 0),
            'otros_ingresos': float(snap.get('otros_ingresos') or 0),
            'gastos': float(snap.get('gastos') or 0),
            'otros_gastos': float(snap.get('otros_gastos') or 0),
            'resultado': float(snap.get('resultado') or 0),
            'variacion': float(snap.get('variacion') or 0),
        }
        py = snap.get('py') or {}
        prev = {
            'ingresos': float(py.get('ingresos') or 0),
            'otros_ingresos': float(py.get('otros_ingresos') or 0),
            'gastos': float(py.get('gastos') or 0),
            'otros_gastos': float(py.get('otros_gastos') or 0),
            'resultado': float(py.get('resultado') or 0),
            'variacion': float(py.get('variacion') or 0),
        }
        var = snap.get('var') or {}
        ratios = snap.get('ratios') or {}
        margin_pct = float(ratios.get('margen') or 0)

        def pct(key: str) -> float:
            try:
                return float((var.get(key) or {}).get('pct') or 0)
            except Exception:
                return 0.0

        cards = [
            {'label': 'Ingresos Totales', 'value': curr['ingresos'], 'suffix': '€', 'change': pct('ingresos'), 'color': '#3b82f6'},
            {'label': 'Gastos Totales', 'value': curr['gastos'], 'suffix': '€', 'change': pct('gastos'), 'color': '#ef4444'},
            {'label': 'Resultado de Explotación', 'value': curr['resultado'], 'suffix': '€', 'change': pct('resultado'), 'color': '#10b981'},
            {'label': 'Otros Ingresos', 'value': curr['otros_ingresos'], 'suffix': '€', 'change': pct('otros_ingresos'), 'color': '#60a5fa'},
            {'label': 'Otros Gastos', 'value': curr['otros_gastos'], 'suffix': '€', 'change': pct('otros_gastos'), 'color': '#f97316'},
        ]

        return {
            'cards': cards,
            'stats': {
                'empresa': int(empresa),
                'curr': curr,
                'prev': prev,
                'var': {k: (var.get(k) or {}) for k in ['ingresos', 'otros_ingresos', 'gastos', 'otros_gastos', 'resultado', 'variacion']},
                'margin_pct': margin_pct,
                'year_curr': int(year_curr),
                'year_prev': int(year_prev),
            }
        }

    def _get_pgc_monthly_kpis(self, empresa, year_curr, year_prev):
        from datia.services.financial_service import FinancialService
        svc = FinancialService()
        cy = svc.get_monthly_kpis(int(empresa), int(year_curr))
        py = svc.get_monthly_kpis(int(empresa), int(year_prev))
        return {
            'labels': cy.get('labels') or self._t('months'),
            'cy': {'ingresos': cy.get('ingresos') or [], 'gastos': cy.get('gastos') or [], 'ebitda': cy.get('ebitda') or []},
            'py': {'ingresos': py.get('ingresos') or [], 'gastos': py.get('gastos') or [], 'ebitda': py.get('ebitda') or []},
        }

    def _get_pgc_quarterly(self, empresa, year_curr, year_prev):
        from datia.services.financial_service import FinancialService
        out = FinancialService().get_quarterly_report(int(empresa), int(year_curr), departamento='todos')
        
        quarters_list = out.get('quarters') or []
        quarters = {q.get('quarter'): q for q in quarters_list} if isinstance(quarters_list, list) else quarters_list
        
        comp = out.get('comparison') or {}
        prev_q = ((comp.get('prev_values') or {}).get('quarters') or {})
        labels = ['Q1', 'Q2', 'Q3', 'Q4']
        curr_vals = [float((quarters.get(q) or {}).get('ingresos') or 0) for q in labels]
        prev_vals = [float((prev_q.get(q) or {}).get('ingresos') or 0) for q in labels]
        
        curr_res = [float((quarters.get(q) or {}).get('beneficio_neto') or 0) for q in labels]
        
        return {'curr': curr_vals, 'prev': prev_vals, 'curr_res': curr_res, 'labels': labels}

    def _build_chart_financial_monthly(self, evolution, year_curr):
        from datia.services.ai.echarts_builder import build_monthly_financial_option
        labels = evolution.get('labels') or self._t('months')
        cy = evolution.get('cy') or {}
        option = build_monthly_financial_option(
            title=f"Ingresos, Gastos y EBITDA mensual ({year_curr})",
            labels=labels,
            ingresos=[float(x or 0) for x in (cy.get('ingresos') or [])],
            gastos=[float(x or 0) for x in (cy.get('gastos') or [])],
            ebitda=[float(x or 0) for x in (cy.get('ebitda') or [])],
            series_suffix="€",
        )
        return {'echarts_option': option}

    def _generate_consultant_narrative(self, year, stats, clients, products, purchases, quarterly, anomalies=[], trend=None, segmentation=None, recs=[], pl_masses=None, per100=None):
        curr = stats.get('curr') or {}
        var = stats.get('var') or {}
        margin_pct = float(stats.get('margin_pct') or 0)
        ingresos_var = float((var.get('ingresos') or {}).get('pct') or 0)
        resultado_var = float((var.get('resultado') or {}).get('pct') or 0)
        curr_resultado = float(curr.get('resultado') or 0)

        if curr_resultado < 0:
            if ingresos_var >= 0:
                sentiment = "mixto (crecimiento en ventas pero con déficit neto)"
            else:
                sentiment = "crítico (caída en ventas y pérdidas netas)"
        else:
            sentiment = "positivo" if ingresos_var >= 0 else "de contracción pero rentable"

        intro = f"<h2>📊 {self._t('situation_report')} {year}</h2>"
        intro += "<p><small>Fuente principal: Contabilidad (PGC). Indicadores operacionales (Top clientes/artículos, operaciones y ticket) se calculan desde albaranes.</small></p>"
        intro += f"<p><strong>Resumen ejecutivo:</strong> {self._generate_intro_text(year, sentiment, float(curr.get('ingresos') or 0), ingresos_var)}</p>"
        
        if curr_resultado < 0:
            intro += f"<p class='alert' style='color: #dc2626;'>⚠️ <strong>Atención:</strong> El ejercicio registra <strong>pérdidas operativas de {self._fmt(abs(curr_resultado))} €</strong>. A pesar de los hitos de facturación, la estructura de costes está penalizando la rentabilidad.</p>"

        intro += f"<p><strong>Margen operativo:</strong> {self._fmt(margin_pct, 1)}% · <strong>Resultado:</strong> {self._fmt(curr_resultado)} € (Δ {self._fmt(resultado_var, 1)}% {self._t('prev_year')}).</p>"

        diag = ""
        try:
            pm = pl_masses or {}
            cy = pm.get('cy') or {}
            py = pm.get('py') or {}
            if cy and py:
                def getv(label):
                    return float(cy.get(label) or 0)
                def getp(label):
                    return float(py.get(label) or 0)
                drivers = [
                    ('COMPRAS Y APROVISIONAMIENTOS', getv('COMPRAS Y APROVISIONAMIENTOS') - getp('COMPRAS Y APROVISIONAMIENTOS')),
                    ('GASTOS DE PERSONAL', getv('GASTOS DE PERSONAL') - getp('GASTOS DE PERSONAL')),
                    ('OTROS GASTOS DE EXPLOTACIÓN', getv('OTROS GASTOS DE EXPLOTACIÓN') - getp('OTROS GASTOS DE EXPLOTACIÓN')),
                    ('AMORTIZACIONES Y DETERIOROS', getv('AMORTIZACIONES Y DETERIOROS') - getp('AMORTIZACIONES Y DETERIOROS')),
                    ('RESULTADO FINANCIERO', getv('RESULTADO FINANCIERO') - getp('RESULTADO FINANCIERO')),
                    ('Variación de existencias', getv('Variación de existencias') - getp('Variación de existencias')),
                ]
                drivers_sorted = sorted(drivers, key=lambda x: abs(x[1]), reverse=True)
                top = [d for d in drivers_sorted if abs(d[1]) > 0][:3]
                if top:
                    diag = "<h3>🔎 Diagnóstico de rentabilidad (PGC)</h3><ul>"
                    for name, delta in top:
                        if name == 'Variación de existencias':
                            diag += f"<li><strong>{name}:</strong> Δ {self._fmt(delta)} € vs PY (impacta el margen por ajuste de inventario).</li>"
                        else:
                            diag += f"<li><strong>{name}:</strong> Δ {self._fmt(delta)} € vs PY.</li>"
                    diag += "</ul>"
        except Exception:
            diag = ""

        per100_txt = ""
        try:
            p100 = per100 or {}
            if (p100.get('status') == 'ok') and ((p100.get('cy') or {}).get('parts')):
                parts = (p100.get('cy') or {}).get('parts') or []
                label_map = {
                    'costo_ventas': 'Coste de ventas (60)',
                    'gastos_admin': 'Gastos de explotación (62+65+69)',
                    'impuestos': 'Impuestos (63)',
                    'personal': 'Personal (64)',
                    'amort': 'Amortización (68)',
                    'financiero': 'Financiero (66+67)',
                    'otros_gastos_exp': 'Otros gastos de explotación (OGDE)',
                    'utilidad_neta': 'Utilidad neta',
                }
                bits = []
                for p in parts:
                    key = str(p.get('key') or '')
                    pct = float(p.get('pct') or 0)
                    if not key:
                        continue
                    bits.append(f"{label_map.get(key, key)}: <strong>{self._fmt(pct, 1)}%</strong>")
                if bits:
                    per100_txt = "<h3>💶 Por cada 100 € de ventas</h3><p>" + " · ".join(bits) + "</p>"
        except Exception:
            per100_txt = ""

        purch_total = float(purchases.get('total', 0) or 0)
        purch_var = float(purchases.get('variation', 0) or 0)

        ops_curr = 0
        ticket_curr = 0.0
        try:
            empresa = int(stats.get('empresa') or 0)
            sql_ops = f"""
                SELECT ejercicio, importe_neto_total, albaranes_count
                FROM metrics_totales_empresa_ejercicio
                WHERE empresa = {empresa} AND ejercicio = {int(year)}
            """
            rows_ops = self._execute_sql(sql_ops)
            if rows_ops:
                r0 = rows_ops[0]
                ops_curr = int(r0.get('albaranes_count') or 0)
                sales_curr = float(r0.get('importe_neto_total') or 0)
                ticket_curr = (sales_curr / ops_curr) if ops_curr > 0 else 0.0
        except Exception:
            ops_curr = 0
            ticket_curr = 0.0

        ops_text = f"<h3>⚙️ {self._t('ops_efficiency')} (Operacional)</h3>"
        ops_bits = []
        if ops_curr > 0:
            ops_bits.append(f"{self._t('ops_managed')} <strong>{ops_curr} {self._t('ops_sales')}</strong> (Ticket medio: <strong>{self._fmt(ticket_curr)} €</strong>).")
        ops_bits.append(f"{self._t('purch_vol')} <strong>{self._fmt(purch_total)} €</strong> (Δ {self._fmt(purch_var, 1)}% {self._t('prev_year')}).")
        if purch_total > 0:
            coverage = (float(curr.get('ingresos') or 0) / purch_total) * 100
            ops_bits.append(f"{self._t('coverage_ratio')}: <strong>{self._fmt(coverage, 0)}%</strong>.")
        ops_text += "<p>" + " ".join(ops_bits) + "</p>"

        q_curr = quarterly.get('curr') or []
        q_res = quarterly.get('curr_res') or []
        if q_curr and any(q_curr):
            best_q_idx = q_curr.index(max(q_curr))
            best_q_val = q_curr[best_q_idx]
            ops_text += f"<p>El trimestre de mayor facturación ha sido el <strong>Q{best_q_idx + 1}</strong> con <strong>{self._fmt(best_q_val)} €</strong>"
            if q_res and len(q_res) > best_q_idx:
                ops_text += f" (Resultado: <strong>{self._fmt(q_res[best_q_idx])} €</strong>)"
            ops_text += ".</p>"
            
            if q_res and min(q_res) < 0:
                worst_q_idx = q_res.index(min(q_res))
                worst_q_val = q_res[worst_q_idx]
                ops_text += f"<p style='color: #dc2626;'>📉 El trimestre con mayor impacto negativo ha sido el <strong>Q{worst_q_idx + 1}</strong>, registrando pérdidas de <strong>{self._fmt(abs(worst_q_val))} €</strong>.</p>"

        strat_text = "<h3>🧠 Análisis Estratégico</h3><ul>"
        if trend:
            direction_map = {'growing': 'Creciente', 'declining': 'Decreciente', 'stable': 'Estable', 'flat': 'Plana'}
            t_dir = direction_map.get(trend.get('direction', 'flat'), 'Estable')
            strat_text += f"<li><strong>Tendencia anual:</strong> {t_dir} (pendiente {trend.get('slope', 0):.2f}).</li>"
        if anomalies:
            strat_text += f"<li><strong>Anomalías:</strong> {len(anomalies)} meses atípicos detectados.</li>"
        else:
            strat_text += "<li><strong>Estabilidad:</strong> sin anomalías estadísticas significativas en la serie mensual.</li>"
        if segmentation:
            count_a = len(segmentation.get('A', []))
            if count_a:
                strat_text += f"<li><strong>Concentración:</strong> categoría A con {count_a} clientes.</li>"
        strat_text += "</ul>"

        market_text = f"<h3>🏆 {self._t('market_pos')} (Operacional)</h3>"
        top_client = (clients.get('clients') or [{}])[0] if clients else {'name': 'N/A', 'value': 0}
        top_prod = (products or [{}])[0] if products else {'name': 'N/A', 'value': 0}
        market_text += f"<p>{self._t('comm_leader')}: <strong>{top_client.get('name', 'N/A')}</strong> ({self._fmt(top_client.get('value', 0))} €). "
        market_text += f"{self._t('star_prod')}: <strong>{top_prod.get('name', 'N/A')}</strong> ({self._fmt(top_prod.get('value', 0))} €).</p>"

        if recs:
            rec_text = "<h3>🚀 Conclusiones y Recomendaciones</h3><ul>" + "".join([f"<li>{r}</li>" for r in recs]) + "</ul>"
        else:
            if ingresos_var < 0:
                msg = self._t('rec_sales_drop')
            elif margin_pct < 15 or float(curr.get('resultado') or 0) < 0:
                msg = self._t('rec_margin_low')
            else:
                msg = self._t('rec_consolidate')
            rec_text = f"<h3>💡 {self._t('observation')}</h3><p>{msg}</p>"

        actions = ""
        try:
            if curr_resultado < 0:
                actions = "<h3>✅ Acciones prioritarias (CFO)</h3><ul>"
                actions += "<li><strong>Precio/mix:</strong> revisar top 20% clientes y top 20% productos para elevar margen bruto (objetivo: +2–3 pts margen).</li>"
                actions += "<li><strong>Compras:</strong> renegociación y control de mermas/escandallos en aprovisionamientos (objetivo: -1–2% sobre ventas).</li>"
                actions += "<li><strong>Gasto fijo:</strong> limitar crecimiento de estructura (personal/OGDE) con presupuesto base-cero por centros.</li>"
                actions += "</ul>"
        except Exception:
            actions = ""

        return intro + diag + per100_txt + ops_text + strat_text + market_text + actions + rec_text

    def _generate_intro_text(self, year, sentiment, sales, sales_var):
        lang = translation.get_language()
        if lang == 'en':
            return f"The year {year} presents a {sentiment} performance, {self._t('closing_vol')} {self._fmt(sales)} € (Δ {self._fmt(sales_var, 1)}% {self._t('prev_year')})."
        if lang == 'ca':
            return f"L'exercici {year} presenta un rendiment {sentiment}, {self._t('closing_vol')} {self._fmt(sales)} € (Δ {self._fmt(sales_var, 1)}% {self._t('prev_year')})."
        return f"El ejercicio {year} presenta un desempeño {sentiment}, {self._t('closing_vol')} {self._fmt(sales)} € (Δ {self._fmt(sales_var, 1)}% {self._t('prev_year')})."

    def _build_chart_evolution(self, evolution, year_curr, year_prev):
        return {
            'type': 'bar',
            'data': {
                'labels': evolution['categories'],
                'datasets': [
                    {'label': str(year_prev), 'data': evolution['series'][0]['data'], 'borderColor': '#94a3b8', 'backgroundColor': 'transparent', 'type': 'line', 'smooth': True},
                    {'label': str(year_curr), 'data': evolution['series'][1]['data'], 'backgroundColor': '#3b82f6', 'borderRadius': 4}
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {'display': True, 'position': 'bottom'},
                    'title': {'display': True, 'text': self._t('evolution')}
                },
                'scales': {'y': {'beginAtZero': True, 'grid': {'color': '#334155'}}, 'x': {'grid': {'display': False}}}
            }
        }


    def _get_metrics_evolution(self, empresa, year_curr, year_prev):
        sql = f"""
            SELECT ejercicio, mes, importe_neto_total 
            FROM metrics_totales_empresa_ejercicio_mes 
            WHERE empresa = {empresa} AND ejercicio IN ({year_curr}, {year_prev})
            ORDER BY mes
        """
        rows = self._execute_sql(sql)
        data_curr = [0]*12
        data_prev = [0]*12
        
        for r in rows:
            m = int(r['mes']) - 1
            if 0 <= m < 12:
                if r['ejercicio'] == year_curr: data_curr[m] = r['importe_neto_total'] or 0
                elif r['ejercicio'] == year_prev: data_prev[m] = r['importe_neto_total'] or 0
                
        return {
            'categories': self._t('months'),
            'series': [
                {'name': str(year_prev), 'data': data_prev, 'type': 'line', 'smooth': True, 'opacity': 0.5},
                {'name': str(year_curr), 'data': data_curr, 'type': 'bar', 'color': '#3b82f6'}
            ]
        }

    def _get_metrics_rankings(self, empresa, year_curr):
        sql = f"""
            SELECT nombre, importe_neto_total 
            FROM metrics_totales_empresa_ejercicio_cliente 
            WHERE empresa = {empresa} AND ejercicio = {year_curr}
            ORDER BY importe_neto_total DESC 
            LIMIT 5
        """
        rows = self._execute_sql(sql)
        # Handle None names
        return {'clients': [{'name': r['nombre'] or self._t('unknown'), 'value': r['importe_neto_total'] or 0} for r in rows]}

    def _get_metrics_top_products(self, empresa, year_curr):
        sql = f"""
            SELECT descripcion, importe_neto_total, albaranes_count
            FROM metrics_totales_empresa_ejercicio_articulo 
            WHERE empresa = {empresa} AND ejercicio = {year_curr}
            ORDER BY importe_neto_total DESC 
            LIMIT 5
        """
        rows = self._execute_sql(sql)
        # Handle None descriptions
        return [{'name': r['descripcion'] or self._t('unknown'), 'value': r['importe_neto_total'] or 0, 'count': r['albaranes_count'] or 0} for r in rows]
        
    def _build_chart_pareto(self, data, title):
        if not data: return None
        try:
            # Safe label truncation
            labels = []
            values = []
            for d in data[:10]:
                name = str(d.get('name') or 'N/A')
                val = d.get('value') or 0
                label = name[:15] + '...' if len(name) > 15 else name
                labels.append(label)
                values.append(val)
            
            return {
                'type': 'bar',
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': self._t('sales_eur'),
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
        except Exception as e:
            logger.error(f"Error building pareto chart: {e}")
            return None

    def _build_chart_pie(self, data, title):
        if not data: return None
        try:
            return {
                'type': 'doughnut',
                'data': {
                    'labels': [str(d.get('name') or 'N/A')[:15] for d in data],
                    'datasets': [{
                        'data': [d.get('value') or 0 for d in data],
                        'backgroundColor': ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
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
        except:
            return None

    def _find_best_source(self, keywords: List[str], exclude_id=None):
        """
        Busca el DataSource más relevante basado en keywords y disponibilidad de datos.
        """
        candidates = DataSource.objects.filter(is_active=True).exclude(is_virtual=True)
        if exclude_id:
            candidates = candidates.exclude(id=exclude_id)
            
        # 1. Match Exacto en Keywords
        for kw in keywords:
            for ds in candidates:
                # Check name or stored keywords
                if kw.lower() in ds.name.lower() or any(kw.lower() in k.lower() for k in ds.keywords):
                    # Verificar si la tabla fisica existe realmente
                    if self._table_exists(ds.get_local_table_name()):
                        return ds
        
        # 2. Fallback: Primer DataSource activo si no hay match
        if candidates.exists():
             for ds in candidates:
                 if self._table_exists(ds.get_local_table_name()):
                     return ds
                     
        return None

    def _table_exists(self, table_name):
        if not table_name: return False
        try:
            with connections['analytics'].cursor() as cursor:
                cursor.execute(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'")
                return cursor.fetchone() is not None
        except:
            return False

    def _map_fields(self, source):
        """
        Identifica los nombres físicos de las columnas clave (Fecha, Importe, Cliente, etc.)
        """
        fields = {
            'date': None,
            'amount': None,
            'cost': None,
            'client': None,
            'client_name': None,
            'is_date_year': False # Flag to detect if column is already a Year Integer
        }
        
        # Buscar por usage_type
        date_field = source.fields.filter(usage_type='date').first()
        if date_field: 
            fields['date'] = date_field.field_name
            # Check if it looks like a Year column
            if 'ejercicio' in date_field.field_name.lower() or 'year' in date_field.field_name.lower() or 'ano' in date_field.field_name.lower():
                 fields['is_date_year'] = True
        
        metric_field = source.fields.filter(usage_type='metric', business_name__icontains='neto').first()
        if not metric_field:
             metric_field = source.fields.filter(usage_type='metric').first() # Fallback
        if metric_field: fields['amount'] = metric_field.field_name
        
        cost_field = source.fields.filter(usage_type='metric', business_name__icontains='coste').first()
        if cost_field: fields['cost'] = cost_field.field_name
        
        dim_field = source.fields.filter(usage_type='dimension', business_name__icontains='cliente').first()
        if dim_field: fields['client_name'] = dim_field.field_name
        
        # Fallbacks por nombre comun si no hay metadatos ricos
        if not fields['date']: fields['date'] = 'Fecha' # Adivinanza
        if not fields['amount']: fields['amount'] = 'ImporteNeto'
        
        return fields

    def _get_kpis_globales(self, empresa, year_curr, year_prev, source, fields) -> List[Dict]:
        """
        KPIs usando nombres de tabla y campos dinámicos.
        """
        table = source.get_local_table_name()
        col_amount = fields['amount'] or 'Importe'
        col_cost = fields['cost']
        col_date = fields['date'] or 'Fecha'
        
        # Smart Date Logic
        if fields.get('is_date_year'):
            date_expr = f'"{col_date}"' # Already an integer year
        else:
            date_expr = f'EXTRACT(YEAR FROM "{col_date}")'
        
        # SQL para obtener totales por año
        sql = f"""
        SELECT 
            {date_expr} as ejercicio,
            SUM("{col_amount}") as total_ventas
            {f', SUM("{col_cost}") as total_coste' if col_cost else ''}
        FROM "{table}"
        WHERE "CodigoEmpresa" = '{empresa}' 
          AND {date_expr} IN ({year_curr}, {year_prev})
        GROUP BY 1
        """
        
        # Fallback si falla por nombre de columna empresa
        try:
            rows = self._execute_sql(sql)
        except:
            # Reintentar con "Empresa" en vez de "CodigoEmpresa"
             sql = sql.replace('"CodigoEmpresa"', '"Empresa"')
             rows = self._execute_sql(sql)
        
        curr_sales = 0
        prev_sales = 0
        curr_cost = 0
        
        for r in rows:
            yr = str(int(r.get('ejercicio', 0)))
            if yr == str(year_curr):
                curr_sales = r.get('total_ventas') or 0
                curr_cost = r.get('total_coste') or 0
            elif yr == str(year_prev):
                prev_sales = r.get('total_ventas') or 0

        sales_var = ((curr_sales - prev_sales) / prev_sales * 100) if prev_sales else 100
        curr_margin_pct = 0
        if col_cost and curr_sales:
             curr_margin = curr_sales - curr_cost
             curr_margin_pct = (curr_margin / curr_sales * 100)
        
        kpis = [
            {
                'label': self._t('net_sales'),
                'value': f"{curr_sales:,.0f} €",
                'trend': 'up' if sales_var >= 0 else 'down',
                'sub': f"{sales_var:+.1f}% vs {year_prev}",
                'color': 'blue'
            }
        ]
        
        if col_cost:
            kpis.append({
                'label': self._t('gross_margin'),
                'value': f"{curr_margin_pct:.1f}%",
                'trend': 'up' if curr_margin_pct > 20 else 'down',
                'sub': self._t('estimated'),
                'color': 'green'
            })
            
        return kpis

    def _get_evolution_monthly(self, empresa, year_curr, year_prev, source, fields) -> Dict:
        table = source.get_local_table_name()
        col_amount = fields['amount']
        col_date = fields['date']
        
        # If date is YEAR only (integer), we CANNOT get months. Return empty evolution.
        if fields.get('is_date_year'):
             return {
                'categories': self._t('months'),
                'series': []
            }

        sql = f"""
        SELECT 
            EXTRACT(YEAR FROM "{col_date}") as ejercicio,
            EXTRACT(MONTH FROM "{col_date}") as mes,
            SUM("{col_amount}") as total
        FROM "{table}"
        WHERE "CodigoEmpresa" = '{empresa}'
          AND EXTRACT(YEAR FROM "{col_date}") IN ({year_curr}, {year_prev})
        GROUP BY 1, 2
        ORDER BY 2
        """
        
        try:
            rows = self._execute_sql(sql)
        except:
             sql = sql.replace('"CodigoEmpresa"', '"Empresa"')
             rows = self._execute_sql(sql)
        
        data_curr = [0] * 12
        data_prev = [0] * 12
        
        for r in rows:
            try:
                m = int(r.get('mes', 1)) - 1
                yr = str(int(r.get('ejercicio', 0)))
                if 0 <= m < 12:
                    if yr == str(year_curr):
                        data_curr[m] = r.get('total') or 0
                    else:
                        data_prev[m] = r.get('total') or 0
            except:
                continue
                    
        return {
            'categories': self._t('months'),
            'series': [
                {'name': str(year_prev), 'data': data_prev, 'type': 'line', 'smooth': True, 'opacity': 0.5},
                {'name': str(year_curr), 'data': data_curr, 'type': 'bar', 'color': '#3b82f6'}
            ]
        }

    def _get_rankings(self, empresa, year_curr, source, fields) -> Dict:
        table = source.get_local_table_name()
        col_amount = fields['amount']
        col_date = fields['date']
        col_client = fields['client_name'] or 'NombreCliente' # Fallback default
        
        # Smart Date Logic
        if fields.get('is_date_year'):
            date_expr = f'"{col_date}"'
        else:
            date_expr = f'EXTRACT(YEAR FROM "{col_date}")'

        sql_cli = f"""
        SELECT "{col_client}" as nombre, SUM("{col_amount}") as total
        FROM "{table}"
        WHERE "CodigoEmpresa" = '{empresa}' 
          AND {date_expr} = {year_curr}
        GROUP BY "{col_client}"
        ORDER BY total DESC
        LIMIT 5
        """
        
        try:
            top_cli = self._execute_sql(sql_cli)
        except:
             # Try simple replace
             sql_cli = sql_cli.replace('"CodigoEmpresa"', '"Empresa"')
             top_cli = self._execute_sql(sql_cli)
        
        return {
            'clients': [{'name': r.get('nombre', self._t('unknown')), 'value': r.get('total', 0)} for r in top_cli]
        }

    def _get_metrics_purchases_advanced(self, empresa, year_curr, year_prev):
        """Calcula Compras actuales y anteriores para variación"""
        sql = f"""
            SELECT ejercicio, importe_neto_total 
            FROM metrics_totales_empresa_ejercicio_compra
            WHERE empresa = {empresa} AND ejercicio IN ({year_curr}, {year_prev})
        """
        rows = self._execute_sql(sql)
        
        curr = 0
        prev = 0
        
        for r in rows:
            val = r['importe_neto_total'] or 0
            if r['ejercicio'] == year_curr:
                curr = val
            elif r['ejercicio'] == year_prev:
                prev = val
                
        var_pct = ((curr - prev) / prev * 100) if prev else 100
        
        return {
            'total': curr,
            'prev': prev,
            'variation': var_pct,
            'label': f"{self._t('purchases')} {year_curr}"
        }

    def _get_metrics_quarterly(self, empresa, year_curr, year_prev):
        """Agrupa por trimestres usando la tabla mensual"""
        sql = f"""
            SELECT ejercicio, mes, importe_neto_total 
            FROM metrics_totales_empresa_ejercicio_mes 
            WHERE empresa = {empresa} AND ejercicio IN ({year_curr}, {year_prev})
        """
        rows = self._execute_sql(sql)
        
        q_curr = [0, 0, 0, 0]
        q_prev = [0, 0, 0, 0]
        
        for r in rows:
            m = int(r['mes'])
            q_idx = (m - 1) // 3
            val = r['importe_neto_total'] or 0
            
            if r['ejercicio'] == year_curr:
                q_curr[q_idx] += val
            elif r['ejercicio'] == year_prev:
                q_prev[q_idx] += val
                
        return {'curr': q_curr, 'prev': q_prev, 'labels': ['Q1', 'Q2', 'Q3', 'Q4']}

    def _build_chart_quarters(self, data, year_curr, year_prev):
        return {
            'type': 'bar',
            'data': {
                'labels': data['labels'],
                'datasets': [
                    {'label': str(year_prev), 'data': data['prev'], 'backgroundColor': '#94a3b8'},
                    {'label': str(year_curr), 'data': data['curr'], 'backgroundColor': '#8b5cf6'}
                ]
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'plugins': {
                    'legend': {'display': True},
                    'title': {'display': True, 'text': self._t('quarterly')}
                }
            }
        }

    def _execute_sql(self, query) -> List[Dict]:
        """Helper para ejecutar SQL crudo y devolver Dicts"""
        try:
            from datia.services.security.sql_guard import SQLGuard
            SQLGuard.ensure_allowed(query)
            with connections['analytics'].cursor() as cursor:
                cursor.execute(query)
                if cursor.description:
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
                return []
        except Exception as e:
            # logger.warning(f"ReportHandler SQL Failed: {e} | Query: {query}")
            # Rethrow to allow fallback logic in caller
            raise e
