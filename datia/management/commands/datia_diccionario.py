from django.core.management.base import BaseCommand

from datia.services.ai.diccionario import fichas, resumen


class Command(BaseCommand):
    help = 'Muestra el diccionario que el plan puede leer: mapeo más operaciones ya cargadas.'

    def handle(self, *args, **options):
        cuentas = resumen()
        self.stdout.write('Diccionario')
        for papel, cuenta in sorted(cuentas.items()):
            self.stdout.write(f'  {papel}: {cuenta}')
        self.stdout.write('Operaciones')
        for ficha in fichas():
            if ficha['origen'] == 'mapeo':
                continue
            self.stdout.write(f"  {ficha['frase']} -> {ficha['tabla']}")
