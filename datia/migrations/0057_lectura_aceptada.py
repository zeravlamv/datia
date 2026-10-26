from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0056_consulta_conversacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='consultaconversacion',
            name='lectura_aceptada',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
