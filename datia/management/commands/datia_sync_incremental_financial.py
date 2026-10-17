from django.core.management.base import BaseCommand
from datia.services.etl_service import ETLService

class Command(BaseCommand):
    help = 'Sincroniza incrementalmente Financiera (Plan y Acumulados) para empresa/ejercicio'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, required=True)
        parser.add_argument('--ejercicio', type=int, required=True)

    def handle(self, *args, **options):
        empresa = options['empresa']
        ejercicio = options['ejercicio']
        svc = ETLService()
        self.stdout.write(f"Incremental Financiera {empresa}/{ejercicio}")
        try:
            steps = 0
            for update in svc.sync_mssql_financial_incremental_generator(empresa, ejercicio):
                self.stdout.write(str(update))
                steps += 1
            self.stdout.write(self.style.SUCCESS(f"Completado. Pasos: {steps}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
