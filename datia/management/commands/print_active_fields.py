from django.core.management.base import BaseCommand
from datia.models.semantic import DataSource, DataField

class Command(BaseCommand):
    help = 'Imprime campos activos de un DataSource por empresa y tabla origen.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, required=True, help='Código de empresa')
        parser.add_argument('--table', type=str, required=True, help='Nombre de tabla MSSQL (source_table)')

    def handle(self, *args, **opts):
        empresa = int(opts['empresa'])
        table = opts['table']
        ds = DataSource.objects.filter(empresa_id=empresa, source_table=table).first()
        if not ds:
            self.stderr.write(self.style.ERROR(f"No existe DataSource para empresa={empresa}, table={table}"))
            return
        self.stdout.write(self.style.SUCCESS(f"DataSource: id={ds.id}, name={ds.name}, source_table={ds.source_table}, is_virtual={ds.is_virtual}"))
        fields = DataField.objects.filter(source=ds).order_by('field_name')
        active = [f for f in fields if f.is_active]
        self.stdout.write(self.style.SUCCESS(f"Activos ({len(active)}):"))
        for f in active:
            self.stdout.write(f" - {f.field_name} | type={f.data_type} | usage={f.usage_type}")
        inactive = [f for f in fields if not f.is_active]
        self.stdout.write(self.style.WARNING(f"Inactivos ({len(inactive)}):"))
        for f in inactive:
            self.stdout.write(f" - {f.field_name} | type={f.data_type} | usage={f.usage_type}")
