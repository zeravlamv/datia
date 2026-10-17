import os
import sys
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from datia.services.etl_service import ETLService
from datia.services.totals_service import TotalsService
from django.db import connections

def test_migration(empresa_id=1, target_year=2025):
    print(f"=== INICIANDO TEST MIGRACION EMPRESA {empresa_id} ===")
    
    print("1. Limpiando...")
    with connections['analytics'].cursor() as c:
        for t in [
            'metrics_totales_empresa_ejercicio',
            'metrics_totales_empresa_ejercicio_mes',
            'metrics_totales_empresa_ejercicio_cliente',
            'metrics_totales_empresa_ejercicio_cliente_mes',
            'metrics_totales_empresa_ejercicio_articulo',
            'metrics_totales_empresa_ejercicio_cod_postal',
            'datiadb_cabeceraalbarancliente',
            'datiadb_lineasalbarancliente',
        ]:
            try:
                c.execute(f"DELETE FROM {t} WHERE empresa=%s", [empresa_id]) if t.startswith('metrics') else c.execute(f"DELETE FROM {t} WHERE codigoempresa=%s", [empresa_id])
            except Exception as e:
                pass
    
    print("2. Importando datos desde MSSQL...")
    etl = ETLService()
    # Using 'all' to copy datiadb_ tables
    gen = etl.sync_all_years_for_empresa_generator(
        empresa_id=empresa_id,
        sync_type='all',
        target_year=target_year,
        years_count=3,
        standard_tables=['ventas']
    )
    
    for msg in gen:
        if '"message":' in msg:
            import json
            try:
                data = json.loads(msg.replace('data: ', '').strip())
                print(f"  -> {data.get('message')}")
            except:
                pass

    print("3. Recalculando métricas...")
    totals = TotalsService()
    for y in range(target_year, target_year-3, -1):
        t0 = time.time()
        print(f"  -> Agregando Ventas {empresa_id}/{y}...")
        try:
            totals.aggregate_from_datiadb_sales(empresa_id, y)
            t1 = time.time()
            print(f"     OK ({t1-t0:.2f}s)")
        except Exception as e:
            import traceback
            print(f"     ERROR: {e}")
            traceback.print_exc()

    # VERIFY
    with connections['analytics'].cursor() as c:
        c.execute('SELECT COUNT(*) FROM datiadb_cabeceraalbarancliente WHERE codigoempresa=%s', [empresa_id])
        print("Cabeceras:", c.fetchone()[0])
        c.execute('SELECT COUNT(*) FROM metrics_totales_empresa_ejercicio WHERE empresa=%s', [empresa_id])
        print("Métricas Ventas:", c.fetchone()[0])

    print("=== FIN DEL TEST ===")

if __name__ == "__main__":
    test_migration(1, 2025)
