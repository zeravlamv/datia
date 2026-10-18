from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0055_datasource_global'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsultaConversacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('usuario_id', models.IntegerField()),
                ('empresa', models.IntegerField()),
                ('ejercicio', models.IntegerField()),
                ('titulo', models.CharField(max_length=180)),
                ('mensajes', models.JSONField(default=list)),
                ('creado_at', models.DateTimeField(auto_now_add=True)),
                ('actualizado_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'datia_consulta_conversacion',
                'ordering': ['-actualizado_at'],
                'indexes': [models.Index(fields=['usuario_id', 'empresa', 'ejercicio'], name='datia_conv_usuario_emp_eje')],
            },
        ),
    ]
