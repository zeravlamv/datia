import os
import sys
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from datia.services.query_builder import QueryBuilder

db_alias = 'analytics' if 'analytics' in connections.databases else 'default'
with connections[db_alias].cursor() as cur:
    for tbl in ['datiadb_lineaspedidocliente', 'datiadb_cabecerapedidocliente', 'datiadb_lineasalbarancliente', 'datiadb_cabeceraalbarancliente']:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [tbl])
        cols = [r[0] for r in cur.fetchall()]
        print(tbl, '=>', ','.join(cols))

config = QueryBuilder._resolve_entity_semantics('articulo', 1)
print('Resolved table:', config.get('table'))
print('Label candidates:', config.get('label_candidates'))
label_col, col_map = QueryBuilder._validate_table_columns(config['table'], config['label_candidates'])
print('Label match:', label_col)

ctx = {'empresa': 1, 'ejercicio': 2024}
r = QueryBuilder.build_from_nl('rentabilidad productos septiembre 2024 top 20', ctx)
print('SQL:', r['sql'] if r else 'NO RESULT')
if r and 'sql' in r:
    with connections[db_alias].cursor() as cur:
        try:
            cur.execute(r['sql'])
            rows = cur.fetchmany(5)
            print('Sample rows:', rows)
        except Exception as e:
            print('Execute error:', str(e))
