import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import connections

c = connections['analytics'].cursor()
c.execute("""
SELECT pid, state, wait_event_type, wait_event, now()-query_start AS age, left(regexp_replace(query,'\\s+',' ','g'),160)
FROM pg_stat_activity
WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'
""")
for r in c.fetchall():
    print(r)
