from .settings import *  # Reutiliza toda la configuración base

# Enrutado específico para la versión móvil
ROOT_URLCONF = 'config.urls_mobile'

# Opcional: facilitar diagnóstico en entorno móvil
# (hereda DEBUG de settings si viene de .env)
CSRF_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
