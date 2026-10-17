import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.api.system_endpoints import save_config, load_config, CONFIG_FILE

print(f"Current Config: {load_config()}")
print("Resetting to 'auto'...")
save_config({'preset': 'auto'})
print(f"New Config: {load_config()}")
