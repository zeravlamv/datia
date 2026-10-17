import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from datia.services.etl_service import ETLService
from datia.models.master import Empresa

s = ETLService()
print("Restoring companies...")
s.sync_empresas(empresas_filter=None)
print("Companies restored:", list(Empresa.objects.values_list('codigo', flat=True)))
