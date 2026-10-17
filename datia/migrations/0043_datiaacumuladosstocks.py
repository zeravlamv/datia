from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('datia', '0042_globalconfig_userpreference_visible_tabs_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DatiaAcumuladosStocks',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('empresa', models.IntegerField(db_index=True)),
                ('ejercicio', models.IntegerField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('periodo', models.IntegerField()),
                ('articulo', models.CharField(db_index=True, max_length=64)),
                ('almacen', models.CharField(blank=True, max_length=64, null=True)),
                ('ubicacion', models.CharField(blank=True, max_length=64, null=True)),
                ('tipologia', models.CharField(blank=True, max_length=64, null=True)),
                ('importesaldo', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'datia_acumulados_stocks',
                'indexes': [
                    models.Index(fields=['empresa', 'ejercicio', 'periodo'], name='datia_acum_empresa_0f49ef_idx'),
                    models.Index(fields=['articulo'], name='datia_acum_articulo_9df2c0_idx'),
                    models.Index(fields=['almacen', 'ubicacion'], name='datia_acum_almacen_ubicacion_1b2b6e_idx'),
                ],
                'unique_together': {('empresa', 'ejercicio', 'periodo', 'articulo', 'almacen', 'ubicacion')},
            },
        ),
    ]
