from django.core.management.base import BaseCommand
from django.conf import settings
from datia.services.banking_import_service import BankingImportService


class Command(BaseCommand):
    help = 'Importa cuentas bancarias desde MSSQL bancos/bancosconta por empresa.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, required=True, help='ID empresa o "all"')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        if getattr(settings, 'DATIA_DISABLE_MSSQL_SYNC', False):
            self.stdout.write(self.style.WARNING('MSSQL sync desactivado por DATIA_DISABLE_MSSQL_SYNC'))
            return
        svc = BankingImportService()
        empresas = []
        val = opts['empresa']
        if str(val).lower() == 'all':
            from datia.models import Empresa
            empresas = list(Empresa.objects.values_list('codigo', flat=True))
        else:
            empresas = [int(val)]
        final_report = []
        for emp in empresas:
            try:
                rep = svc.import_empresa(emp, dry_run=opts.get('dry_run', False))
                final_report.append(rep)
                self.stdout.write(self.style.SUCCESS(f"Empresa {emp}: {rep}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Empresa {emp}: ERROR {e}"))
        self.stdout.write(self.style.SUCCESS('Finalizado'))
