from django.core.management.base import BaseCommand
from django.conf import settings
import os
import json
from datia.services.ai.context_builders.financial_context import FinancialContextBuilder

class Command(BaseCommand):
    help = "Reconstruye el contexto IA financiera y guarda el JSON en disco."

    def add_arguments(self, parser):
        parser.add_argument("--empresa", type=int, required=True)
        parser.add_argument("--ejercicio", type=int, required=True)
        parser.add_argument("--fast", action="store_true")

    def handle(self, *args, **options):
        empresa = options["empresa"]
        ejercicio = options["ejercicio"]
        fast = options.get("fast", False)
        builder = FinancialContextBuilder()
        context = builder.build_context(empresa, ejercicio, fast_mode=fast)
        ctx_dir = getattr(settings, "DATIA_AI_CONTEXT_DIR", settings.BASE_DIR)
        path = os.path.join(ctx_dir, f"datia_ai_context_financiera_{empresa}_{ejercicio}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(context, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Contexto financiera generado: {path}"))
        except Exception as e:
            raise SystemExit(f"Error guardando JSON: {e}")
