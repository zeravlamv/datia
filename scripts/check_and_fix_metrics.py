
import os
import django
import sys

# Setup Django
# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

def check_and_fix():
    print("--- Verificando Métricas ---")
    print("Este script trabaja únicamente con métricas locales recalculadas desde datiadb_*.") 
    
if __name__ == "__main__":
    check_and_fix()
