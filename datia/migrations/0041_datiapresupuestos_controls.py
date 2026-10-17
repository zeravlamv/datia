from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0040_datiapresupuestos'),
    ]

    operations = [
        migrations.AddField(
            model_name='datiapresupuestos',
            name='agosto_full',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='datiapresupuestos',
            name='line_pct',
            field=models.DecimalField(max_digits=6, decimal_places=2, default=0),
        ),
    ]

