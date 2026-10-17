import os
import sys
import django
import logging

# Setup Django Environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.embedding_service import EmbeddingService
from datia.models import MetricsEmbeddings

# Configure Console Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def seed_templates():
    logger.info("--- SEEDING & INDEXING TEMPLATES ---")
    print("DEBUG: Script started.")
    try:
        service = EmbeddingService()
        
        # 1. Clear old templates (optional, but good for clean state)
        # We only clear kind='template' to preserve learned 'qa'
        MetricsEmbeddings.objects.filter(kind='template').delete()
        logger.info("Cleared existing templates.")
        
        # 2. Index new templates
        service.index_templates()
        logger.info("✅ Templates indexed successfully.")
        
        # 3. Verify
        count = MetricsEmbeddings.objects.filter(kind='template').count()
        logger.info(f"Total Templates: {count}")
        
    except Exception as e:
        logger.error(f"❌ Failed to seed templates: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    seed_templates()
