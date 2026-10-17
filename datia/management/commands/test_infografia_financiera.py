from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import json
from statistics import mean

class Command(BaseCommand):
    help = "Genera una infografía financiera desde los JSON de contexto y exporta HTML."

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=int, required=True)
        parser.add_argument("--ejercicio", type=int, required=True)

    def handle(self, *args, **options):
        empresa = options["empresa"]
        ejercicio = options["ejercicio"]
        ai_dir = getattr(settings, "DATIA_AI_CONTEXT_DIR", settings.BASE_DIR)
        fin_path = os.path.join(ai_dir, f"datia_ai_context_financiera_{empresa}_{ejercicio}.json")
        ven_path = os.path.join(ai_dir, f"datia_ai_context_ventas_{empresa}_{ejercicio}.json")
        if not os.path.exists(fin_path):
            raise CommandError("JSON financiero no encontrado")
        try:
            with open(fin_path, "r", encoding="utf-8") as f:
                fin = json.load(f)
        except Exception as e:
            raise CommandError(f"Error leyendo JSON financiero: {e}")
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
        alerta_txt = ""
        if margen_op_pct < 0:
            alerta_txt = "Alerta de Rentabilidad Crítica. Margen operativo negativo."
        elif margen_op_pct < 5:
            alerta_txt = "Alerta de Rentabilidad Crítica. Requiere revisión de precios."
        css_path = os.path.join(str(settings.BASE_DIR), "datia", "static", "css", "infografia_financiera.css")
        css_href = f"file:///{css_path.replace(os.sep, '/')}"
        header = f"<div class='header'><h1>Informe Financiero {ejercicio}</h1><div class='subtitle'>Basado en JSON de contexto</div></div>"
        kpis_html = (
            "<div class='kpi-grid'>"
            + f"<div class='kpi'><div class='kpi-val'>{ventas_totales:,.2f} €</div><div class='kpi-label'>Ventas Totales</div></div>"
            + f"<div class='kpi'><div class='kpi-val'>{yoy_global:.2f} %</div><div class='kpi-label'>Crecimiento YoY</div></div>"
            + f"<div class='kpi'><div class='kpi-val'>{solvencia:.2f}</div><div class='kpi-label'>Ratio de Solvencia</div></div>"
            + f"<div class='kpi'><div class='kpi-val'>{margen_op_pct:.2f} %</div><div class='kpi-label'>Margen Operativo</div></div>"
            + "</div>"
        )
        alerta_html = f"<div class='alert'>{alerta_txt}</div>" if alerta_txt else ""
        tri_html = (
            "<div class='section'><h2>Resultados Trimestrales</h2>"
            + "<div class='quarter-grid'>"
            + "".join([
                f"<div class='quarter'><div class='q-title'>{q}</div>"
                f"<div class='q-line'>Ventas: { (v_q.get(q) if v_q.get(q) is not None else 0):,.2f} €</div>"
                f"<div class='q-line'>Margen: { (m_q.get(q) if m_q.get(q) is not None else 0):.2f} %</div>"
                f"<div class='q-line'>EBITDA: { (e_q.get(q) if e_q.get(q) is not None else 0):,.2f} €</div>"
                "</div>"
                for q in ["Q1","Q2","Q3","Q4"]
            ])
            + "</div></div>"
        )
        prod_html = ""
        if productos_top:
            prod_html = (
                "<div class='section'><h2>Rendimiento por Producto</h2>"
                + "<div class='product-grid'>"
                + "".join([
                    f"<div class='product'><div class='prod-name'>{p['nombre']}</div><div class='prod-val'>{p['ingresos']:,.2f} €</div></div>"
                    for p in productos_top
                ])
                + "</div></div>"
            )
        audit_model = "JSON"
        footer = f"<div class='footer'>Empresa {empresa} • {ejercicio} • Basado en 1 fuente • Origen: {audit_model}</div>"
        body = header + kpis_html + alerta_html + tri_html + prod_html + footer
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Infografia_Financiera_{empresa}_{ejercicio}.html</title><link rel='stylesheet' href='{css_href}'></head><body>{body}</body></html>"
        out_name = f"Infografia_Financiera_{empresa}_{ejercicio}.html"
        out_path = os.path.join(ai_dir, out_name)
        try:
            with open(out_path, "w", encoding="utf-8") as hf:
                hf.write(html)
        except Exception as e:
            raise CommandError(f"Error exportando HTML: {e}")
        self.stdout.write(self.style.SUCCESS(f"[OK] HTML guardado en: {out_path}"))
