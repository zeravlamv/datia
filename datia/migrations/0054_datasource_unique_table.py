from django.db import migrations, models
import django.db.models.functions


class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0053_significado'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='datasource',
            constraint=models.UniqueConstraint(
                django.db.models.functions.Lower('source_table'),
                'empresa_id',
                name='uniq_tpl_data_source_empresa_tabla',
            ),
        ),
    ]
