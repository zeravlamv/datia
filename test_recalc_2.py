import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from datia.services.etl_service import ETLService
from datia.services.totals_service import TotalsService
import time

s = ETLService()
print("Optimizando tablas...")
s._ensure_datiadb_perf('datiadb_cabeceraalbarancliente')
s._ensure_datiadb_perf('datiadb_lineasalbarancliente')
print("Tablas optimizadas.")

print("Recalculando Ventas empresa 2 / 2026...")
t = TotalsService()
t0 = time.time()
t.aggregate_from_datiadb_sales(2, 2026)
print(f"Recálculo terminado en {time.time()-t0:.2f}s")
