import os
import sys
import django
from django.db import connection

# Force current directory to sys.path
sys.path.append(os.getcwd())

# Setup Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

TABLES = [
    'metrics_totales_empresa_ejercicio_compra',
    'metrics_totales_empresa_ejercicio_compra_mes',
    'metrics_totales_empresa_ejercicio_proveedor',
    'metrics_totales_empresa_ejercicio_articulo',
    'datia_raw_cabecera_compra',
    'datia_financial_presupuesto_notas',
    'metrics_totales_empresa_ejercicio_articulo_compra',
    'metrics_totales_empresa_ejercicio_cliente',
    'metrics_totales_empresa_ejercicio_cliente_mes',
    'metrics_totales_empresa_ejercicio_cod_postal',
    'metrics_totales_empresa_ejercicio_mes',
    'datia_raw_lineas',
    'datia_raw_cabecera',
    'datia_raw_lineas_compra',
    'metrics_totales_empresa_ejercicio_proveedor_mes',
    'datia_financial_plan',
    'datia_datiadiario',
    'datia_financial_groups',
    'datia_financial_cartera',
    'metrics_llm_consultas',
    'metrics_totales_empresa_ejercicio',
    'datia_financial_acumulados',
    'datia_financial_presupuestos'
]

def fix_tables():
    print("Starting fix_tables...")
    with connection.cursor() as cursor:
        for table in TABLES:
            print(f"Processing {table}...")
            try:
                # 1. Check if column exists and is not integer
                cursor.execute(f"""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}' AND column_name = 'empresa'
                """)
                row = cursor.fetchone()
                if not row:
                    print(f"  - Column 'empresa' not found in {table}. Skipping.")
                    continue
                
                if row[0] == 'integer':
                    print(f"  - Already integer. Skipping.")
                    continue

                # 2. Clean non-numeric data
                print(f"  - Cleaning non-numeric data...")
                cursor.execute(f"DELETE FROM {table} WHERE empresa !~ '^[0-9]+$'")
                
                # 3. Alter column type
                print(f"  - Altering column type to INTEGER...")
                cursor.execute(f"ALTER TABLE {table} ALTER COLUMN empresa TYPE INTEGER USING empresa::integer")
                print(f"  - Done.")
                
            except Exception as e:
                print(f"ERROR processing {table}: {e}")

if __name__ == '__main__':
    fix_tables()
