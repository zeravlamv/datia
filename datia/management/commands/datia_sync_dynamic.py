from django.core.management.base import BaseCommand
from datia.factories import ServiceFactory

class Command(BaseCommand):
    help = 'Sincroniza tablas dinámicas DatiaDB_ desde MSSQL según DataSource/Fields.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, required=True, help='Código de empresa (entero)')
        parser.add_argument('--fast', action='store_true', default=False, help='Activar copia rápida (bulk)')
        parser.add_argument('--table_ids', nargs='*', type=int, help='IDs de DataSource a sincronizar (opcional)')

    def handle(self, *args, **opts):
        empresa = opts['empresa']
        fast_bulk = bool(opts.get('fast'))
        table_ids = opts.get('table_ids')
        etl = ServiceFactory.get_etl_service()
        self.stdout.write(f"Iniciando sincronización dinámica para empresa {empresa}...")
        try:
            gen = etl.sync_dynamic_tables_generator(
                empresa_id=empresa,
                sync_data=True,
                table_ids=table_ids,
                fast_bulk=fast_bulk,
            )
            for chunk in gen:
                # Los generadores devuelven texto SSE; imprimimos resumen
                self.stdout.write(str(chunk).strip())
            self.stdout.write(self.style.SUCCESS("✅ Sincronización dinámica completada"))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"❌ Error en sincronización dinámica: {e}"))
