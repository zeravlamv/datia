from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Retirado. El examen de preguntas sustituye al entrenamiento masivo.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'El entrenamiento masivo está retirado. No guarda consultas de ejemplo. '
            'El examen de preguntas está en Auto Entreno.'
        ))
