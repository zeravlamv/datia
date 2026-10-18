from django.db import migrations, models
import django.db.models.functions


class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0054_datasource_unique_table'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='datasource',
            name='uniq_tpl_data_source_empresa_tabla',
        ),
        migrations.AddConstraint(
            model_name='datasource',
            constraint=models.UniqueConstraint(
                django.db.models.functions.Lower('source_table'),
                name='uniq_tpl_data_source_tabla',
            ),
        ),
    ]
