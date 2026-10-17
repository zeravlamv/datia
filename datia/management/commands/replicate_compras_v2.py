from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Comando obsoleto. Usa el ETL basado en datiadb_* para preparar datos de ejemplo."

    def handle(self, *args, **options):
        self.stdout.write(self.help)
