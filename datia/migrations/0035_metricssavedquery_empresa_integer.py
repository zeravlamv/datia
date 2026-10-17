from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0042_globalconfig_userpreference_visible_tabs_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DELETE FROM metrics_saved_queries WHERE empresa IS NULL OR empresa !~ '^[0-9]+$';",
            reverse_sql=""
        ),
        migrations.AlterField(
            model_name='metricssavedquery',
            name='empresa',
            field=models.IntegerField(),
        ),
    ]
