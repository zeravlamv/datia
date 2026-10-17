from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datia', '0043_recreate_datia_presupuestos_if_missing'),
    ]

    operations = [
        migrations.AddField(model_name='globalconfig', name='mssql_driver', field=models.CharField(blank=True, default='', help_text='Vacío: se usa MSSQL_DRIVER del entorno.', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='mssql_host', field=models.CharField(blank=True, default='', help_text='Vacío: se usa el servidor del entorno.', max_length=255)),
        migrations.AddField(model_name='globalconfig', name='mssql_port', field=models.CharField(blank=True, default='', help_text='Vacío: se usa el puerto del entorno.', max_length=10)),
        migrations.AddField(model_name='globalconfig', name='mssql_name', field=models.CharField(blank=True, default='', help_text='Base de origen en SQL Server. Vacío: se usa MSSQL_NAME.', max_length=255)),
        migrations.AddField(model_name='globalconfig', name='mssql_user', field=models.CharField(blank=True, default='', max_length=255)),
        migrations.AddField(model_name='globalconfig', name='mssql_password', field=models.CharField(blank=True, default='', help_text='Vacío: se usa la contraseña del entorno.', max_length=255)),
        migrations.AddField(model_name='globalconfig', name='mssql_sync_enabled', field=models.BooleanField(default=True, help_text='Si se desmarca, no se lanza la sincronización estándar contra SQL Server.')),
        migrations.AddField(model_name='globalconfig', name='ai_provider', field=models.CharField(blank=True, default='ollama', help_text='ollama o gemini.', max_length=20)),
        migrations.AddField(model_name='globalconfig', name='ollama_host', field=models.CharField(blank=True, default='', help_text='Ejemplo: http://127.0.0.1:11434', max_length=255)),
        migrations.AddField(model_name='globalconfig', name='llm_chat', field=models.CharField(blank=True, default='', help_text='Modelo de chat y SQL.', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='llm_report', field=models.CharField(blank=True, default='', help_text='Modelo de informes.', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='llm_semantic', field=models.CharField(blank=True, default='', help_text='Modelo de descripciones semánticas.', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='llm_sql_training', field=models.CharField(blank=True, default='', help_text='Modelo entrenador de SQL.', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='gemini_model', field=models.CharField(blank=True, default='', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='show_sql', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='globalconfig', name='training_mode', field=models.BooleanField(default=False, help_text='La IA aprende de las preguntas del usuario.')),
        migrations.AddField(model_name='globalconfig', name='auto_load_actualidad', field=models.BooleanField(default=True)),
        migrations.AddField(model_name='globalconfig', name='mobile_specialized', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='globalconfig', name='perf_preset', field=models.CharField(blank=True, default='auto', help_text='eco, auto o turbo.', max_length=20)),
        migrations.AddField(model_name='globalconfig', name='fast_bulk', field=models.BooleanField(default=False, help_text='COPY masivo en líneas de ventas y compras.')),
        migrations.AddField(model_name='globalconfig', name='app_name', field=models.CharField(blank=True, default='', max_length=32)),
        migrations.AddField(model_name='globalconfig', name='erp_name', field=models.CharField(blank=True, default='', max_length=120)),
        migrations.AddField(model_name='globalconfig', name='global_logo_url', field=models.CharField(blank=True, default='', max_length=500)),
        migrations.AddField(model_name='globalconfig', name='global_accent', field=models.CharField(blank=True, default='', max_length=20)),
    ]
