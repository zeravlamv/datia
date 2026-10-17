
import os
import sys
import django
from django.db import connections

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def optimize_indices():
    print("--- STARTING INDEX OPTIMIZATION ---")
    
    with connections['analytics'].cursor() as cursor:
        # 1. Get all dynamic tables
        cursor.execute("SELECT tablename FROM pg_tables WHERE tablename LIKE 'datiadb_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"Found {len(tables)} dynamic tables: {tables}")
        
        for table in tables:
            print(f"\nAnalyzing {table}...")
            
            # Get columns
            cursor.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}'
            """)
            columns = cursor.fetchall()
            
            # Identify targets
            targets = []
            for col_name, dtype in columns:
                lower_col = col_name.lower()
                
                # Rules for Indexing
                should_index = False
                
                # 1. Dates (Critical for filtering)
                if 'fecha' in lower_col or 'date' in lower_col:
                    should_index = True
                    
                # 2. Foreign Keys / IDs (Critical for Joins)
                elif ('codigo' in lower_col or 'id' in lower_col or 'cliente' in lower_col or 'proveedor' in lower_col or 'articulo' in lower_col) and 'nombre' not in lower_col and 'desc' not in lower_col:
                    should_index = True
                    
                # 3. Tenant ID (Always filter)
                elif 'sync_empresa' in lower_col:
                    should_index = True
                    
                if should_index:
                    targets.append(col_name)
            
            # Create Indices
            for col in targets:
                # Sanitized index name
                clean_col = "".join(x for x in col if x.isalnum())
                idx_name = f"idx_{table}_{clean_col}"[:63] # Postgres limit 63 chars
                
                # Check if exists
                cursor.execute(f"SELECT 1 FROM pg_indexes WHERE indexname = '{idx_name}'")
                if cursor.fetchone():
                    print(f"  - Index {idx_name} already exists.")
                else:
                    print(f"  - Creating Index {idx_name} on {col}...")
                    try:
                        # Use double quotes for identifiers to handle casing
                        cursor.execute(f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{idx_name}" ON "{table}" ("{col}")')
                        print("    ✅ Created.")
                    except Exception as e:
                        # Fallback without CONCURRENTLY if transaction block issue (though script is autocommit usually? Django manages trans)
                        print(f"    ⚠️ Failed concurrent: {e}. Retrying standard...")
                        try:
                            cursor.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ("{col}")')
                            print("    ✅ Created (Standard).")
                        except Exception as e2:
                            print(f"    ❌ Failed: {e2}")

    print("\n--- OPTIMIZATION COMPLETE ---")

if __name__ == "__main__":
    optimize_indices()
