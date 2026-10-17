from django.core.management.base import BaseCommand
from datia.models import MetricsTotalesEmpresaEjercicioCompra, MetricsTotalesEmpresaEjercicioCompraMes
from datia.services.etl_service import ETLService

class Command(BaseCommand):
    help = 'Muestra el estado de métricas de Compras para una empresa (por ejercicio)'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, required=True, help='Código de empresa (entero)')

    def handle(self, *args, **options):
        empresa = options['empresa']
        svc = ETLService()
        try:
            years = svc.get_available_exercises(str(empresa)) or []
        except Exception:
            years = []
        self.stdout.write(f"Empresa {empresa}. Ejercicios detectados: {years}")
        total_annual = MetricsTotalesEmpresaEjercicioCompra.objects.filter(empresa=empresa).count()
        total_monthly = MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa=empresa).count()
        self.stdout.write(f"Total registros métricos (Anual): {total_annual}")
        self.stdout.write(f"Total registros métricos (Mensual): {total_monthly}")
        for y in years:
            ann = MetricsTotalesEmpresaEjercicioCompra.objects.filter(empresa=empresa, ejercicio=y).first()
            monthly = MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa=empresa, ejercicio=y).count()
            neto = float(ann.importe_neto_total) if ann else 0
            alb = ann.albaranes_count if ann else 0
            self.stdout.write(f"{y}: Neto={neto:.2f}€, Albaranes={alb}, Meses={monthly}")
