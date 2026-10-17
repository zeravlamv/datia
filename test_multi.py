import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import connections
from datia.api.etl_endpoints import full_sync_worker, ETL_JOBS
import time
import uuid

job_id = str(uuid.uuid4())
ETL_JOBS[job_id] = {"status": "pending", "progress": 0}

print("Running full_sync_worker for companies 1 and 2...")
full_sync_worker(
    job_id=job_id,
    empresa_id=None,
    table_name=None,
    sync_type="all",
    table_ids=None,
    sync_data=True,
    target_year=2026,
    fast_bulk=True,
    years_count=3,
    standard_tables=None,
    force_reset=False,
    mssql_database='CAFE',
    delete_users=False,
    reload_companies=False,
    empresas_filter="1,2",
    skip_cleanup=False
)

with connections['analytics'].cursor() as c:
    c.execute('SELECT codigoempresa, COUNT(*) FROM datiadb_cabeceraalbarancliente GROUP BY codigoempresa')
    print("Cabeceras:", c.fetchall())
    c.execute('SELECT empresa, COUNT(*) FROM metrics_totales_empresa_ejercicio GROUP BY empresa')
    print("Metrics:", c.fetchall())
