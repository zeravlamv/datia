
import os
import django
import sys

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.etl_service import ETLService
from django.db import connections

etl = ETLService()
print("Connecting to MSSQL...")
conn = etl.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
tables = [row[0] for row in cursor.fetchall()]

print("--- MSSQL TABLES ---")
for t in sorted(tables):
    print(t)
print("--------------------")

if 'Grupos' in tables:
    print("Found 'Grupos' table!")
    print("Columns:")
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='Grupos'")
    cols = [row[0] for row in cursor.fetchall()]
    print(cols)
else:
    print("'Grupos' table NOT FOUND in list.")

print("--- Analytics Columns: datiadb_lineaspedidocliente ---")
db_alias = 'analytics' if 'analytics' in connections.databases else 'default'
with connections[db_alias].cursor() as cursor_pg:
    cursor_pg.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='datiadb_lineaspedidocliente'")
    cols_pg = [row[0] for row in cursor_pg.fetchall()]
    print(",".join(cols_pg))
