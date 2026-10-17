from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0043_datiaacumuladosstocks'),
    ]

    operations = [
        migrations.AddField(
            model_name='datiaacumuladosstocks',
            name='unidadsaldo',
            field=models.DecimalField(max_digits=18, decimal_places=4, default=0),
        ),
        migrations.AddField(
            model_name='datiaacumuladosstocks',
            name='preciomedio',
            field=models.DecimalField(max_digits=18, decimal_places=4, default=0),
        ),
        migrations.AddField(
            model_name='datiaacumuladosstocks',
            name='precioultimaentrada',
            field=models.DecimalField(max_digits=18, decimal_places=4, default=0),
        ),
        migrations.AddField(
            model_name='datiaacumuladosstocks',
            name='preciocompra',
            field=models.DecimalField(max_digits=18, decimal_places=4, default=0),
        ),
    ]
