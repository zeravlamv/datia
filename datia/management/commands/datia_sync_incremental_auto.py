from django.core.management.base import BaseCommand
from django.utils import timezone

from datia.models.master import GlobalConfig, Empresa
from datia.services.etl_service import ETLService


class Command(BaseCommand):
    help = "Ejecuta sincronización incremental automática según configuración global."

    def add_arguments(self, parser):
        parser.add_argument(
            "--empresa",
            type=str,
            default=None,
            help="Código de empresa (entero). Si se omite, se procesan todas.",
        )
        parser.add_argument(
            "--ejercicio",
            type=int,
            default=None,
            help="Ejercicio a sincronizar. Si se omite, se usa el año actual.",
        )

    def handle(self, *args, **options):
        now = timezone.now()

        config = GlobalConfig.load()
        settings = config.implanter_settings or {}

        enabled = settings.get("etl_auto_incremental_enabled", True)
        interval_hours = int(settings.get("etl_auto_incremental_interval_hours", 4))
        last_run_iso = settings.get("etl_auto_incremental_last_run")

        if not enabled:
            self.stdout.write("Auto-incremental deshabilitado en GlobalConfig (etl_auto_incremental_enabled=false).")
            return

        if last_run_iso:
            try:
                last_run = timezone.datetime.fromisoformat(last_run_iso)
                if timezone.is_naive(last_run):
                    last_run = timezone.make_aware(last_run, timezone.get_current_timezone())
                delta_hours = (now - last_run).total_seconds() / 3600.0
                if delta_hours < float(interval_hours):
                    self.stdout.write(
                        f"Saltando ejecución automática: solo han pasado {delta_hours:.2f}h "
                        f"(intervalo configurado: {interval_hours}h)."
                    )
                    return
            except Exception:
                self.stderr.write("Advertencia: no se pudo parsear etl_auto_incremental_last_run; se forzará ejecución.")

        qs_empresas = Empresa.objects.all()
        empresa_arg = options.get("empresa")
        if empresa_arg is not None:
            try:
                codigo = int(empresa_arg)
                qs_empresas = qs_empresas.filter(codigo=codigo)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Empresa inválida: {empresa_arg}"))
                return

        empresas = list(qs_empresas)
        if not empresas:
            self.stdout.write("No se han encontrado empresas para sincronizar.")
            return

        ejercicio = options.get("ejercicio") or now.year

        days_back_sales = int(settings.get("etl_auto_incremental_days_back_sales", 1))
        days_back_purchases = int(settings.get("etl_auto_incremental_days_back_purchases", 7))
        days_back_cartera = int(settings.get("etl_auto_incremental_days_back_cartera", 90))

        etl = ETLService()

        for empresa in empresas:
            emp_id = int(empresa.codigo)
            self.stdout.write(f"== Empresa {emp_id} / Ejercicio {ejercicio} ==")

            try:
                if etl.has_baseline(emp_id, ejercicio, "ventas"):
                    self.stdout.write(
                        f"- Ventas incremental (days_back={days_back_sales})"
                    )
                    for _ in etl.sync_mssql_sales_incremental_generator(
                        emp_id, ejercicio, days_back=days_back_sales
                    ):
                        pass
                else:
                    self.stdout.write(
                        "- Ventas: se omite incremental (no existe baseline)."
                    )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error en Ventas incremental: {e}"))

            try:
                if etl.has_baseline(emp_id, ejercicio, "compras"):
                    self.stdout.write(
                        f"- Compras incremental (days_back={days_back_purchases})"
                    )
                    for _ in etl.sync_mssql_purchases_incremental_generator(
                        emp_id, ejercicio, days_back=days_back_purchases
                    ):
                        pass
                else:
                    self.stdout.write(
                        "- Compras: se omite incremental (no existe baseline)."
                    )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error en Compras incremental: {e}"))

            try:
                if etl.has_baseline(emp_id, ejercicio, "financiera"):
                    self.stdout.write("- Financiera incremental")
                    for _ in etl.sync_mssql_financial_incremental_generator(
                        emp_id, ejercicio
                    ):
                        pass
                else:
                    self.stdout.write(
                        "- Financiera: se omite incremental (no existe baseline)."
                    )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error en Financiera incremental: {e}")
                )

            try:
                if etl.has_baseline(emp_id, ejercicio, "cartera"):
                    self.stdout.write(
                        f"- CarteraEfectos incremental (days_back={days_back_cartera})"
                    )
                    for _ in etl.sync_mssql_cartera_incremental_generator(
                        emp_id, ejercicio, days_back=days_back_cartera
                    ):
                        pass
                else:
                    self.stdout.write(
                        "- CarteraEfectos: se omite incremental (no existe baseline)."
                    )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error en CarteraEfectos incremental: {e}")
                )

        settings["etl_auto_incremental_enabled"] = enabled
        settings["etl_auto_incremental_interval_hours"] = interval_hours
        settings["etl_auto_incremental_last_run"] = now.isoformat()
        settings.setdefault("etl_auto_incremental_days_back_sales", days_back_sales)
        settings.setdefault("etl_auto_incremental_days_back_purchases", days_back_purchases)
        settings.setdefault("etl_auto_incremental_days_back_cartera", days_back_cartera)

        config.implanter_settings = settings
        config.save()

        self.stdout.write(self.style.SUCCESS("Sincronización incremental automática completada."))

