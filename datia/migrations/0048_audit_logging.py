from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0047_create_banking_models'),
    ]
    atomic = False

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE SCHEMA IF NOT EXISTS datia_audit;
            CREATE EXTENSION IF NOT EXISTS pgcrypto;
            CREATE TABLE IF NOT EXISTS datia_audit.oplog (
              id bigserial PRIMARY KEY,
              ts timestamptz NOT NULL DEFAULT now(),
              process_name text NOT NULL,
              table_schema text DEFAULT 'public',
              table_name text,
              operation text NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE','STATUS')),
              rows_count bigint DEFAULT 0,
              state text NOT NULL CHECK (state IN ('started','running','completed','error')),
              duration_ms bigint,
              batch_id uuid DEFAULT COALESCE(NULLIF(current_setting('datia.batch_id', true), '')::uuid, gen_random_uuid()),
              message text
            );
            CREATE INDEX IF NOT EXISTS idx_oplog_ts ON datia_audit.oplog (ts DESC);
            CREATE INDEX IF NOT EXISTS idx_oplog_proc_ts ON datia_audit.oplog (process_name, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_oplog_tbl_ts ON datia_audit.oplog (table_name, ts DESC);
            CREATE INDEX IF NOT EXISTS idx_oplog_state_ts ON datia_audit.oplog (state, ts DESC);

            CREATE OR REPLACE FUNCTION datia_audit.log_event(
              p_process text,
              p_table text,
              p_operation text,
              p_rows bigint,
              p_state text,
              p_message text,
              p_duration_ms bigint,
              p_schema text DEFAULT 'public'
            ) RETURNS void LANGUAGE sql AS $$
              INSERT INTO datia_audit.oplog(process_name, table_schema, table_name, operation, rows_count, state, message, duration_ms)
              VALUES (p_process, p_schema, p_table, upper(p_operation), COALESCE(p_rows,0), lower(p_state), p_message, p_duration_ms);
            $$;

            CREATE OR REPLACE FUNCTION datia_audit.raise_alert(
              p_process text, p_table text, p_message text
            ) RETURNS void LANGUAGE plpgsql AS $$
            BEGIN
              PERFORM datia_audit.log_event(p_process, p_table, 'STATUS', 0, 'error', p_message, NULL, 'public');
              PERFORM pg_notify('datia_alerts', json_build_object('process', p_process, 'table', p_table, 'state', 'error', 'message', p_message, 'ts', now())::text);
            END;
            $$;

            CREATE OR REPLACE FUNCTION datia_audit.trg_log_dml() RETURNS trigger
            LANGUAGE plpgsql AS $$
            DECLARE cnt bigint := 0;
            BEGIN
              IF TG_OP = 'INSERT' THEN
                SELECT count(*) INTO cnt FROM new_rows;
              ELSIF TG_OP = 'DELETE' THEN
                SELECT count(*) INTO cnt FROM old_rows;
              ELSE
                SELECT count(*) INTO cnt FROM new_rows;
              END IF;
              PERFORM datia_audit.log_event('db_trigger', TG_TABLE_NAME, TG_OP, cnt, 'completed', NULL, NULL, TG_TABLE_SCHEMA);
              RETURN NULL;
            END;
            $$;

            CREATE OR REPLACE VIEW datia_audit.logs_24h AS
            SELECT * FROM datia_audit.oplog WHERE ts >= now() - interval '24 hours' ORDER BY ts DESC;

            CREATE OR REPLACE VIEW datia_audit.process_progress AS
            SELECT process_name, state, count(*) AS events, sum(rows_count) AS rows_total, max(ts) AS last_event
            FROM datia_audit.oplog
            GROUP BY process_name, state;

            CREATE OR REPLACE FUNCTION datia_audit.get_progress(p_process text, p_since interval DEFAULT '7 days')
            RETURNS TABLE(table_name text, last_state text, last_ts timestamptz, rows_total bigint)
            LANGUAGE sql AS $$
              SELECT o.table_name,
                     (array_agg(o.state ORDER BY o.ts DESC))[1],
                     max(o.ts),
                     sum(o.rows_count)
              FROM datia_audit.oplog o
              WHERE o.process_name = p_process
                AND o.ts >= now() - p_since
              GROUP BY o.table_name;
            $$;

            CREATE OR REPLACE FUNCTION datia_audit.rotate_oplog(p_keep_days integer DEFAULT 30)
            RETURNS integer LANGUAGE plpgsql AS $$
            DECLARE v_deleted integer := 0;
            BEGIN
              DELETE FROM datia_audit.oplog
              WHERE ts < now() - make_interval(days => p_keep_days);
              GET DIAGNOSTICS v_deleted = ROW_COUNT;
              PERFORM pg_notify('datia_audit', json_build_object('event','rotation','deleted',v_deleted,'ts',now())::text);
              RETURN v_deleted;
            END;
            $$;
            """,
            reverse_sql="""
            DROP VIEW IF EXISTS datia_audit.process_progress;
            DROP VIEW IF EXISTS datia_audit.logs_24h;
            DROP FUNCTION IF EXISTS datia_audit.get_progress(text, interval);
            DROP FUNCTION IF EXISTS datia_audit.rotate_oplog(integer);
            DROP FUNCTION IF EXISTS datia_audit.trg_log_dml();
            DROP FUNCTION IF EXISTS datia_audit.raise_alert(text, text, text);
            DROP FUNCTION IF EXISTS datia_audit.log_event(text, text, text, bigint, text, text, bigint, text);
            DROP TABLE IF EXISTS datia_audit.oplog;
            DROP SCHEMA IF EXISTS datia_audit CASCADE;
            """
        )
    ]
