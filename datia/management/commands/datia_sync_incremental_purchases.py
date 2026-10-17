from django.core.management.base import BaseCommand
from datia.services.etl_service import ETLService

class Command(BaseCommand):
    help = 'Sincroniza incrementalmente Compras para empresa/ejercicio'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, required=True)
        parser.add_argument('--ejercicio', type=int, required=True)
        parser.add_argument('--days_back', type=int, default=7)

    def handle(self, *args, **options):
        empresa = options['empresa']
        ejercicio = options['ejercicio']
        days_back = options['days_back']
        svc = ETLService()
        self.stdout.write(f"Incremental Compras {empresa}/{ejercicio} (days_back={days_back})")
        try:
            steps = 0
            for update in svc.sync_mssql_purchases_incremental_generator(empresa, ejercicio, days_back=days_back):
                self.stdout.write(str(update))
                steps += 1
            self.stdout.write(self.style.SUCCESS(f"Completado. Pasos: {steps}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
