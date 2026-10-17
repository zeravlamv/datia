from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = 'Adjunta triggers de auditoría en tablas datiadb_* con tolerancia a locks.'

    def add_arguments(self, parser):
        parser.add_argument('--schema', default='public')
        parser.add_argument('--lock_timeout', default='5s')
        parser.add_argument('--statement_timeout_ms', default='60000')

    def handle(self, *args, **opts):
        schema = opts['schema']
        lt = opts['lock_timeout']
        stm = str(opts['statement_timeout_ms'])
        db_alias = 'analytics' if 'analytics' in connections.databases else 'default'
        ok = 0
        skipped = 0
        with connections[db_alias].cursor() as c:
            c.execute("SELECT set_config('lock_timeout', %s, true)", [lt])
            c.execute("SELECT set_config('statement_timeout', %s, true)", [stm])
            c.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema=%s AND table_name LIKE 'datiadb\\_%' ESCAPE '\\'
                ORDER BY table_name
            """, [schema])
            tables = [r[0] for r in c.fetchall()]
            for tn in tables:
                try:
                    c.execute(f'DROP TRIGGER IF EXISTS "{tn}_ai" ON "{schema}"."{tn}"')
                    c.execute(f'DROP TRIGGER IF EXISTS "{tn}_au" ON "{schema}"."{tn}"')
                    c.execute(f'DROP TRIGGER IF EXISTS "{tn}_ad" ON "{schema}"."{tn}"')
                    c.execute(f'CREATE TRIGGER "{tn}_ai" AFTER INSERT ON "{schema}"."{tn}" REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION datia_audit.trg_log_dml()')
                    c.execute(f'CREATE TRIGGER "{tn}_au" AFTER UPDATE ON "{schema}"."{tn}" REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION datia_audit.trg_log_dml()')
                    c.execute(f'CREATE TRIGGER "{tn}_ad" AFTER DELETE ON "{schema}"."{tn}" REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION datia_audit.trg_log_dml()')
                    ok += 1
                except Exception as e:
                    skipped += 1
                    try:
                        c.execute("SELECT datia_audit.log_event(%s,%s,'STATUS',0,'error',%s,NULL,%s)", ['attach_cmd', tn, str(e), schema])
                    except Exception:
                        pass
        self.stdout.write(self.style.SUCCESS(f"Adjuntos: {ok}, Omitidos: {skipped}"))
