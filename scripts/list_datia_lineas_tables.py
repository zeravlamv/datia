import os
import sys
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections

db_alias = 'analytics' if 'analytics' in connections.databases else 'default'
with connections[db_alias].cursor() as cur:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'datia%linea%'")
    rows = [r[0] for r in cur.fetchall()]
    print(','.join(rows))
