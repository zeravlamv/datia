from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0048_audit_logging'),
    ]
    atomic = False

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            DECLARE r record;
            BEGIN
              PERFORM set_config('lock_timeout', '5s', true);
              PERFORM set_config('statement_timeout', '60000', true);
              FOR r IN
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema='public'
                  AND (
                        table_name LIKE 'datia_raw\\_%' ESCAPE '\\'
                     OR table_name LIKE 'datiadb\\_%' ESCAPE '\\'
                  )
              LOOP
                BEGIN
                  EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.table_name||'_ai', r.table_schema, r.table_name);
                  EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.table_name||'_au', r.table_schema, r.table_name);
                  EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.table_name||'_ad', r.table_schema, r.table_name);
                  EXECUTE format('CREATE TRIGGER %I AFTER INSERT ON %I.%I REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION datia_audit.trg_log_dml();', r.table_name||'_ai', r.table_schema, r.table_name);
                  EXECUTE format('CREATE TRIGGER %I AFTER UPDATE ON %I.%I REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION datia_audit.trg_log_dml();', r.table_name||'_au', r.table_schema, r.table_name);
                  EXECUTE format('CREATE TRIGGER %I AFTER DELETE ON %I.%I REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION datia_audit.trg_log_dml();', r.table_name||'_ad', r.table_schema, r.table_name);
                EXCEPTION 
                  WHEN lock_not_available THEN
                    PERFORM datia_audit.log_event('migration_0049', r.table_name, 'STATUS', 0, 'error', 'Trigger skipped due to lock_not_available', NULL, r.table_schema);
                  WHEN query_canceled THEN
                    PERFORM datia_audit.log_event('migration_0049', r.table_name, 'STATUS', 0, 'error', 'Trigger skipped due to query_canceled (timeout)', NULL, r.table_schema);
                  WHEN others THEN
                    PERFORM datia_audit.log_event('migration_0049', r.table_name, 'STATUS', 0, 'error', SQLERRM, NULL, r.table_schema);
                END;
              END LOOP;
            END $$;
            """,
            reverse_sql="""
            DO $$
            DECLARE r record;
            BEGIN
              FOR r IN
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema='public'
                  AND (
                        table_name LIKE 'datia_raw\\_%' ESCAPE '\\'
                     OR table_name LIKE 'datiadb\\_%' ESCAPE '\\'
                  )
              LOOP
                EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.table_name||'_ai', r.table_schema, r.table_name);
                EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.table_name||'_au', r.table_schema, r.table_name);
                EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I', r.table_name||'_ad', r.table_schema, r.table_name);
              END LOOP;
            END $$;
            """
        )
    ]
