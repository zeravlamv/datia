from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = 'Imprime columnas de tablas DatiaDB_ para diagnóstico.'

    def add_arguments(self, parser):
        parser.add_argument('--tables', nargs='*', default=[
            'datiadb_cabecerapedidocliente',
            'datiadb_cabeceraalbarancliente',
            'datiadb_lineaspedidocliente',
            'datiadb_lineasalbarancliente',
        ])

    def handle(self, *args, **opts):
        db_alias = 'analytics' if 'analytics' in connections.databases else 'default'
        with connections[db_alias].cursor() as c:
            for tbl in opts['tables']:
                try:
                    c.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema='public' AND table_name=%s
                        ORDER BY ordinal_position
                    """, [tbl])
                    cols = [r[0] for r in c.fetchall()]
                    self.stdout.write(self.style.SUCCESS(f"{tbl}: {len(cols)} cols"))
                    for col in cols:
                        self.stdout.write(f" - {col}")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"{tbl}: ERROR {e}"))
