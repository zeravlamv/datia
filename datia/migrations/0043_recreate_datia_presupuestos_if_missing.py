from django.db import migrations


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS datia_financial_presupuestos (
    id BIGSERIAL PRIMARY KEY,
    empresa INTEGER NOT NULL,
    ejercicio INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cuenta VARCHAR(20) NOT NULL,
    periodo INTEGER NOT NULL,
    importe NUMERIC(18,4) NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    agosto_full BOOLEAN NOT NULL DEFAULT FALSE,
    line_pct NUMERIC(6,2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS datia_finan_empresa_5a0f94_idx
    ON datia_financial_presupuestos (empresa, ejercicio, cuenta, periodo);

CREATE INDEX IF NOT EXISTS datia_finan_empresa_16cf98_idx
    ON datia_financial_presupuestos (empresa, ejercicio, version);

CREATE UNIQUE INDEX IF NOT EXISTS datia_financial_presupuestos_uq
    ON datia_financial_presupuestos (empresa, ejercicio, cuenta, periodo, version);
"""


class Migration(migrations.Migration):
    dependencies = [
        ("datia", "0050_remove_bankinginstrumentaccountmap_uniq_instr_prefix_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            CREATE_TABLE_SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
