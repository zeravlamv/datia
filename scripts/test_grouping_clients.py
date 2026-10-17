import os
import sys
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.query_builder import QueryBuilder
from django.db import connections

ctx = {'empresa': 1, 'ejercicio': 2024}
res = QueryBuilder.build_from_nl('margen clientes octubre', ctx)
print('Result:', res)
if res and 'sql' in res:
    alias = 'analytics' if 'analytics' in connections.databases else 'default'
    with connections[alias].cursor() as cur:
        try:
            cur.execute(res['sql'])
            rows = cur.fetchmany(5)
            print('Rows:', rows)
        except Exception as e:
            print('Execute error:', str(e))
