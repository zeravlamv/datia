from django.core.management.base import BaseCommand
from datia.services.etl_service import ETLService
from datia.models import Empresa

class Command(BaseCommand):
    help = "Borra acumulados financieros y reimporta CarteraEfectos desde MSSQL para todas las empresas y ejercicios."

    def add_arguments(self, parser):
        parser.add_argument("--skip_clear", action="store_true", help="No borrar acumulados, solo reimportar cartera")
        parser.add_argument("--empresa", type=str, default=None, help="Código de empresa a limitar (opcional)")
        parser.add_argument("--years_count", type=int, default=None, help="Limitar número de ejercicios hacia atrás (opcional)")

    def handle(self, *args, **options):
        svc = ETLService()
        empresa_filter = options.get("empresa")
        years_count = options.get("years_count")
        if not options.get("skip_clear", False):
            self.stdout.write("Borrando acumulados financieros (datia_financial_acumulados)...")
            try:
                res = svc.clear_financial_acumulados()
                self.stdout.write(self.style.SUCCESS("Acumulados borrados (TRUNCATE)"))
            except Exception as e:
                raise SystemExit(f"Error al borrar acumulados: {e}")
        else:
            self.stdout.write("Saltando borrado de acumulados por opción --skip_clear")

        qs = Empresa.objects.all()
        if empresa_filter:
            try:
                val = int(empresa_filter)
                qs = qs.filter(codigo=val)
            except Exception:
                qs = qs.filter(codigo=empresa_filter)

        total_empresas = qs.count()
        if total_empresas == 0:
            self.stdout.write(self.style.WARNING("No hay empresas en el sistema"))
            return

        processed = 0
        for emp in qs:
            processed += 1
            self.stdout.write(f"[{processed}/{total_empresas}] Empresa {emp.codigo} - {emp.nombre}")
            try:
                years = svc.get_available_exercises(emp.codigo)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error obteniendo ejercicios para empresa {emp.codigo}: {e}"))
                years = []
            if years_count is not None and isinstance(years_count, int) and years_count > 0:
                years = sorted(years, reverse=True)[:years_count]
            else:
                years = sorted(years, reverse=True)
            if not years:
                self.stdout.write(self.style.WARNING(f"Sin ejercicios disponibles en MSSQL para empresa {emp.codigo}"))
                continue
            for year in years:
                self.stdout.write(f"  - Reimportando CarteraEfectos (Inicial) ejercicio {year}...")
                try:
                    steps = 0
                    for update in svc.sync_mssql_cartera_generator(emp.codigo, year):
                        # Generador puede devolver dict o string (SSE-like). Simplificamos el log.
                        msg = update
                        if isinstance(update, dict):
                            msg = update.get("message", "")
                        if isinstance(msg, str) and msg:
                            self.stdout.write(f"    > {msg}")
                        steps += 1
                    self.stdout.write(self.style.SUCCESS(f"    ✓ CarteraEfectos {emp.codigo}/{year} reimportada (pasos: {steps})"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    ✗ Error reimportando CarteraEfectos {emp.codigo}/{year}: {e}"))
                    # Continuar con otras empresas/años
                    continue
        self.stdout.write(self.style.SUCCESS("Proceso completado"))
