from django.core.management.base import BaseCommand
from datia.factories import ServiceFactory

class Command(BaseCommand):
    help = 'Rebuilds totals from raw data (placeholder for future postgres staging logic)'

    def handle(self, *args, **options):
        self.stdout.write("Rebuilding Totals...")
        # In strict V2, this would read from datia_lineas_albaran_cliente (Postgres)
        # For now, it's a stub as we are syncing directly to Totals in ETLService
        self.stdout.write(self.style.SUCCESS("Totals Rebuilt (No-op in SQLite Direct Mode)"))
