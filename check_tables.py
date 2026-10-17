from django.db import connections
c = connections['analytics'].cursor()
c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'datia_%'")
print([r[0] for r in c.fetchall()])
