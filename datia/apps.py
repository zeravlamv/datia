from django.apps import AppConfig
import logging
import os
from django.conf import settings

class DatiaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'datia'

    def ready(self):
        # Avoid running on migration commands or imports
        import sys
        if 'runserver' not in sys.argv:
            return
            
        from datia.factories import ServiceFactory
        import threading
        
        logger = logging.getLogger('datia.startup')
        log_enabled = (os.environ.get('DATIA_LOG_STARTUP', '').lower() in ('1', 'true', 'yes')) or getattr(settings, 'DEBUG', False)

        def load_ai():
            try:
                if log_enabled:
                    logger.info("Pre-cargando modelo AI en segundo plano…")
                # accessing the service instantiates the singleton and loads the model
                ServiceFactory.get_embedding_service()
                if log_enabled:
                    logger.info("Modelo AI listo.")
            except Exception as e:
                logger.warning("Error precargando modelo AI: %s", e)

        # Optional preload: enable only if DATIA_PRELOAD_AI=1/true/yes
        if os.environ.get('DATIA_PRELOAD_AI', '').lower() in ('1', 'true', 'yes'):
            threading.Thread(target=load_ai, daemon=True).start()
