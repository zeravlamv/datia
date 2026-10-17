from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import os
import json
from datia.factories import ServiceFactory
from datia.services.ai.reports.financial import FinancialReportGenerator
from datia.services.dashboard_service import DashboardService

class Command(BaseCommand):
    help = "Genera un informe IA2 (Financiera) usando el JSON de contexto y exporta un HTML."

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=int, required=True, help="ID de la empresa")
        parser.add_argument("--ejercicio", type=int, required=True, help="Ejercicio (año)")
        parser.add_argument("--context", type=str, default=None, help="Ruta al JSON de contexto (opcional)")
        parser.add_argument("--model", type=str, default=None, help="Modelo LLM (opcional)")
        parser.add_argument("--force_fallback", action="store_true", help="Forzar modo fallback (sin LLM)")

    def handle(self, *args, **options):
        empresa = options["empresa"]
        ejercicio = options["ejercicio"]
        context_path_opt = options.get("context")
        model = options.get("model")
        force_fallback = bool(options.get("force_fallback"))

        self.stdout.write("=== TEST IA2 → Informe Financiero + PDF ===")
        self.stdout.write(f"Empresa: {empresa} | Ejercicio: {ejercicio}")

        # 1. Localizar ruta del contexto (financiera)
        ctx_filename = f"datia_ai_context_financiera_{empresa}_{ejercicio}.json"
        ctx_dir = getattr(settings, "DATIA_AI_CONTEXT_DIR", settings.BASE_DIR)
        candidates = []
        if context_path_opt:
            candidates.append(context_path_opt)
        candidates.append(os.path.join(ctx_dir, ctx_filename))
        candidates.append(os.path.join(settings.BASE_DIR, ctx_filename))
        candidates.append(os.path.join(os.getcwd(), ctx_filename))

        context_path = None
        for p in candidates:
            if os.path.exists(p):
                context_path = p
                break

        # 2. Si no existe, construirlo
        if not context_path:
            self.stdout.write("[INFO] Contexto no encontrado. Construyendo...")
            try:
                svc = ServiceFactory.get_dashboard_service()
                res = svc.build_context(empresa=empresa, ejercicio=ejercicio, kind="financiera")
                if res.get("status") == "built":
                    context_path = res.get("path")
                    self.stdout.write(self.style.SUCCESS(f"[OK] Contexto construido en: {context_path}"))
                else:
                    raise CommandError(f"Error construyendo contexto: {res}")
            except Exception as e:
                raise CommandError(f"No se pudo construir el contexto: {e}")

        # 3. Cargar JSON de contexto
        self.stdout.write(f"[LOAD] {context_path}")
        try:
            with open(context_path, "r", encoding="utf-8") as f:
                context = json.load(f)
        except Exception as e:
            raise CommandError(f"Error leyendo contexto: {e}")

        # 4. Generar informe IA2 (Financiera)
        self.stdout.write("[GEN] Generando informe IA2 (Financiera)...")
        try:
            gen = FinancialReportGenerator()
            res = gen.generate(context=context, ejercicio=ejercicio, model=model, force_fallback=force_fallback, role="Controller Financiero / CFO")
            html = res.get("html") or ""
            used_model = res.get("model_used") or res.get("selected_model") or "unknown"
            self.stdout.write(self.style.SUCCESS(f"[DONE] Informe generado (modelo: {used_model})"))
        except Exception as e:
            raise CommandError(f"Error generando informe: {e}")

        if not html.strip():
            raise CommandError("Informe vacío")

        # 5. Exportar a HTML (página única con estilos separados)
        self.stdout.write("[HTML] Exportando a HTML...")
        try:
            out_name = f"Informe_Financiero_{empresa}_{ejercicio}_IA2.html"
            out_path = os.path.join(ctx_dir, out_name)
            css_path = os.path.join(settings.BASE_DIR, "datia", "static", "css", "infografia_story.css").replace("\\", "/")
            css_href = f"file:///{css_path}"
            header_meta = f"<meta charset='utf-8'><title>{out_name}</title><link href='{css_href}' rel='stylesheet'>"
            header_brand = f"<div style='color:#71717a; font-size:12px;'>Empresa {empresa} • Ejercicio {ejercicio} • Modelo: {used_model}</div>"
            # Página única con autoescala y contenedor editorial
            doc = f"<!DOCTYPE html><html><head>{header_meta}</head><body class='story-root'><div class='story-stage'><main class='story-container'><section class='story-hero'><div class='story-hero-content'><div class='story-hero-brand'><div class='story-brand-text'><h1 class='story-title'>Informe Financiero {ejercicio}</h1><p class='story-subtitle'>{header_brand}</p><p class='story-claim'>Basado en JSON de contexto</p></div></div><div class='story-timeline'></div></div></section>{html}</main></div></body></html>"
            with open(out_path, "w", encoding="utf-8") as hf:
                hf.write(doc)
            self.stdout.write(self.style.SUCCESS(f"[OK] HTML guardado en: {out_path}"))
        except Exception as e:
            raise CommandError(f"Error exportando HTML: {e}")

        self.stdout.write(self.style.SUCCESS("=== TEST COMPLETADO ==="))
