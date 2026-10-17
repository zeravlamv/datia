import os, sys, django, json
sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connections

db = 'analytics' if 'analytics' in connections.databases else 'default'
with connections[db].cursor() as cur:
    try:
        cur.execute("SELECT id, user_id, empresa, ejercicio, state FROM datiadb_ai_conversations ORDER BY updated_at DESC LIMIT 3")
        rows = cur.fetchall()
        for r in rows:
            print('conv:', r[0], r[1], r[2], r[3], json.dumps(r[4]))
    except Exception as e:
        print('error:', str(e))
