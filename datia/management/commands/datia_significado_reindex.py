from django.core.management.base import BaseCommand, CommandError

from datia.services.significado_service import SignificadoService


class Command(BaseCommand):
    help = 'Reconstruye el índice de significados de una empresa con el modelo local de Ollama.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, required=True)

    def handle(self, *args, **options):
        def avance(hechos, total):
            self.stdout.write(f'{hechos}/{total}')
            self.stdout.flush()

        resultado = SignificadoService.reindex(options['empresa'], on_progress=avance)
        if not resultado.get('ok'):
            raise CommandError(resultado.get('message') or 'El índice no queda listo.')
        self.stdout.write(self.style.SUCCESS(resultado['message']))
