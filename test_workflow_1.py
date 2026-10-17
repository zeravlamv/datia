import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from datia.api.etl_endpoints import workflow_worker, ETL_JOBS
import time

job_id = f"test-job-{int(time.time())}"
print(f"Iniciando workflow_worker para Empresa 1, job_id={job_id}")

ETL_JOBS[job_id] = {}

workflow_worker(
    job_id=job_id,
    mssql_database='CAFE', # or whatever their default is, None means use default
    years_count=3,
    include_domains='ventas',
    empresa_id='1',
    empresas_filter='1'
)

print("Workflow worker terminado.")
