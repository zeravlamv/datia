from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0018_fix_postgres_schema'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                -- Add metadata_tag
                IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='metadata_tag') THEN
                    ALTER TABLE datia_datafield ADD COLUMN metadata_tag varchar(50);
                END IF;
                
                -- Add is_active
                IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='is_active') THEN
                    ALTER TABLE datia_datafield ADD COLUMN is_active boolean DEFAULT true;
                END IF;

                -- Add is_pii
                IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='is_pii') THEN
                    ALTER TABLE datia_datafield ADD COLUMN is_pii boolean DEFAULT false;
                END IF;
            END $$;
            """,
            reverse_sql="""
            ALTER TABLE datia_datafield DROP COLUMN IF EXISTS metadata_tag;
            ALTER TABLE datia_datafield DROP COLUMN IF EXISTS is_active;
            ALTER TABLE datia_datafield DROP COLUMN IF EXISTS is_pii;
            """
        )
    ]
