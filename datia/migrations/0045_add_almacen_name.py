from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0044_add_stock_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='datiaacumuladosstocks',
            name='almacen_name',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
    ]
