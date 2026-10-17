from django.core.management.base import BaseCommand
from datia.services.etl_service import ETLService

class Command(BaseCommand):
    help = 'Sincroniza Compras (full/incremental según baseline) para todos los ejercicios de una empresa'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, required=True, help='Código de empresa (entero o cadena equivalente)')
        parser.add_argument('--years_count', type=int, default=50, help='Número máximo de ejercicios a procesar (por defecto 50)')
        parser.add_argument('--fast_bulk', action='store_true', help='Usar modo de copia rápida (COPY CSV) cuando esté disponible')

    def handle(self, *args, **options):
        empresa = options['empresa']
        years_count = options['years_count']
        fast_bulk = options['fast_bulk']

        svc = ETLService()
        self.stdout.write(f"Inicio sincronización Compras empresa={empresa} years_count={years_count} fast_bulk={fast_bulk}")
        steps = 0
        try:
            for update in svc.sync_all_years_for_empresa_generator(
                empresa_id=empresa,
                sync_type='standard',
                standard_tables=['compras'],
                years_count=years_count,
                fast_bulk=fast_bulk
            ):
                self.stdout.write(str(update))
                steps += 1
            self.stdout.write(self.style.SUCCESS(f"Sincronización de Compras completada. Pasos: {steps}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en sincronización de Compras: {e}"))
