from django.core.management.base import BaseCommand
from datia.factories import ServiceFactory
import time

class Command(BaseCommand):
    help = 'Synchronizes sales data from MSSQL to Datia Totals'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, required=False, help='Company Code')
        parser.add_argument('--ejercicio', type=int, required=False, help='Fiscal Year')

    def handle(self, *args, **options):
        empresa = options.get('empresa')
        ejercicio = options.get('ejercicio')
        
        etl_service = ServiceFactory.get_etl_service()

        if empresa and ejercicio:
             self.stdout.write(f"Starting Sync for {empresa}/{ejercicio}...")
             try:
                etl_service.sync_mssql_sales(empresa, ejercicio)
                self.stdout.write(self.style.SUCCESS("Sync Completed Successfully"))
             except Exception as e:
                self.stdout.write(self.style.ERROR(f"Sync Failed: {str(e)}"))
        else:
            self.stdout.write("Starting Global Sync (All Companies & Exercises)...")
            try:
                etl_service.sync_all()
                self.stdout.write(self.style.SUCCESS("Global Sync Completed Successfully"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Global Sync Failed: {str(e)}"))
