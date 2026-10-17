from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0026_alter_datafield_usage_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasource',
            name='is_virtual',
            field=models.BooleanField(
                default=False,
                help_text='Si True, esta tabla NO se migra a PostgreSQL. Se consulta directamente desde MSSQL.'
            ),
        ),
    ]
