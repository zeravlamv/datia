from django.core.management.base import BaseCommand
from datia.services.etl_service import ETLService

class Command(BaseCommand):
    help = 'Imprime columnas de tablas MSSQL para diagnóstico rápido.'

    def add_arguments(self, parser):
        parser.add_argument('--tables', nargs='*', required=True, help='Lista de tablas MSSQL a inspeccionar')

    def handle(self, *args, **opts):
        tables = opts['tables'] or []
        svc = ETLService()
        conn = svc.get_connection()
        cur = conn.cursor()
        for t in tables:
            try:
                cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (t,))
                cols = [r[0] for r in cur.fetchall()]
                self.stdout.write(self.style.SUCCESS(f"{t}: {len(cols)} columnas"))
                for c in cols:
                    self.stdout.write(f" - {c}")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"{t}: ERROR {e}"))
        conn.close()
