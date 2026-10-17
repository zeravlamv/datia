from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0017_userempresapermission'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                -- 1. Rename source_field -> field_name
                IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='source_field') THEN
                    ALTER TABLE datia_datafield RENAME COLUMN source_field TO field_name;
                END IF;
                
                -- 2. Rename semantic_description -> description
                IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='semantic_description') THEN
                    ALTER TABLE datia_datafield RENAME COLUMN semantic_description TO description;
                END IF;

                -- 3. Migrate is_ignored -> usage_type
                IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='is_ignored') THEN
                    -- Assuming usage_type exists (verified in inspection)
                    UPDATE datia_datafield SET usage_type = 'none' WHERE is_ignored = true;
                    ALTER TABLE datia_datafield DROP COLUMN is_ignored;
                END IF;
            END $$;
            """,
            reverse_sql="""
            -- Reverse (Approximate)
            DO $$
            BEGIN
                IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='field_name') THEN
                    ALTER TABLE datia_datafield RENAME COLUMN field_name TO source_field;
                END IF;
                
                IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='datia_datafield' AND column_name='description') THEN
                    ALTER TABLE datia_datafield RENAME COLUMN description TO semantic_description;
                END IF;
                
                -- We cannot easily restore is_ignored without potentially losing data if we modified usage_type further, 
                -- so we just add it back as False.
                ALTER TABLE datia_datafield ADD COLUMN IF NOT EXISTS is_ignored BOOLEAN DEFAULT FALSE;
            END $$;
            """
        )
    ]
