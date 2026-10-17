from django.core.management.base import BaseCommand
from django.db import transaction
from datia.models.semantic import BusinessContext, DataSource
from datia.models.financial import (
    DatiaPlanCuentas, DatiaAcumuladosConta, DatiaGrupos,
    DatiaCarteraEfectos, DatiaPresupuestos, DatiaPresupuestoNotas
)
from datia.models.totales import (
    MetricsTotalesEmpresaEjercicio,
    MetricsTotalesEmpresaEjercicioMes,
    MetricsTotalesEmpresaEjercicioCliente,
    MetricsTotalesEmpresaEjercicioClienteMes,
    MetricsTotalesEmpresaEjercicioProveedor,
    MetricsTotalesEmpresaEjercicioProveedorMes,
    MetricsTotalesEmpresaEjercicioArticuloCompra,
    MetricsTotalesEmpresaEjercicioCompraMes,
    MetricsTotalesEmpresaEjercicioCodigoPostal,
)
from datia.models.ai import MetricsLLMConsultas

class Command(BaseCommand):
    help = "Elimina todos los registros de la empresa 'DEMO' en tablas clave."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra conteos sin borrar'
        )

    def handle(self, *args, **options):
        dry = options.get('dry_run', False)
        total_deleted = 0
        with transaction.atomic():
            # Semántica
            total_deleted += self._purge_qs(BusinessContext.objects.filter(empresa_id='DEMO'), dry, 'BusinessContext')
            total_deleted += self._purge_qs(DataSource.objects.filter(empresa_id='DEMO'), dry, 'DataSource')
            # Financieros
            total_deleted += self._purge_qs(DatiaPlanCuentas.objects.filter(empresa='DEMO'), dry, 'DatiaPlanCuentas')
            total_deleted += self._purge_qs(DatiaAcumuladosConta.objects.filter(empresa='DEMO'), dry, 'DatiaAcumuladosConta')
            total_deleted += self._purge_qs(DatiaGrupos.objects.filter(empresa='DEMO'), dry, 'DatiaGrupos')
            total_deleted += self._purge_qs(DatiaCarteraEfectos.objects.filter(empresa='DEMO'), dry, 'DatiaCarteraEfectos')
            total_deleted += self._purge_qs(DatiaPresupuestos.objects.filter(empresa='DEMO'), dry, 'DatiaPresupuestos')
            total_deleted += self._purge_qs(DatiaPresupuestoNotas.objects.filter(empresa='DEMO'), dry, 'DatiaPresupuestoNotas')
            # Métricas Totales
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicio.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicio')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioMes')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioCliente')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioClienteMes.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioClienteMes')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioProveedor')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioProveedorMes.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioProveedorMes')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioArticuloCompra.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioArticuloCompra')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioCompraMes')
            total_deleted += self._purge_qs(MetricsTotalesEmpresaEjercicioCodigoPostal.objects.filter(empresa='DEMO'), dry, 'MetricsTotalesEmpresaEjercicioCodigoPostal')
            # AI
            total_deleted += self._purge_qs(MetricsLLMConsultas.objects.filter(empresa='DEMO'), dry, 'MetricsLLMConsultas')

        if dry:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Registros 'DEMO' detectados: {total_deleted}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Eliminados registros 'DEMO': {total_deleted}"))

    def _purge_qs(self, qs, dry, label):
        count = qs.count()
        if count == 0:
            self.stdout.write(f"{label}: 0")
            return 0
        if dry:
            self.stdout.write(f"{label}: {count} (sin borrar)")
            return count
        deleted = qs.delete()
        # deleted returns (num_deleted, details)
        self.stdout.write(f"{label}: {count} -> borrados")
        return count
