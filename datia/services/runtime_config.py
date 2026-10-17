"""Lectura de la configuración de plataforma guardada en el admin."""

def mssql_params():
    from django.conf import settings
    fallback = {
        'driver': settings.MSSQL_DRIVER,
        'host': settings.MSSQL_HOST,
        'port': settings.MSSQL_PORT,
        'name': settings.MSSQL_NAME,
        'user': settings.MSSQL_USER,
        'password': settings.MSSQL_PASSWORD,
        'sync_enabled': True,
    }
    try:
        from datia.models.master import GlobalConfig
        cfg = GlobalConfig.load()
        params = cfg.mssql_params()
        params['sync_enabled'] = bool(cfg.mssql_sync_enabled)
        return params
    except Exception:
        return fallback


def mssql_sync_disabled():
    import os
    if os.environ.get('DATIA_DISABLE_MSSQL_SYNC', '').lower() in ('1', 'true', 'yes'):
        return True
    try:
        return not bool(mssql_params().get('sync_enabled', True))
    except Exception:
        return False


def mssql_connection_string(database=None):
    params = mssql_params()
    db_name = database or params['name']
    return (
        f"DRIVER={params['driver']};"
        f"SERVER={params['host']},{params['port']};"
        f"DATABASE={db_name};"
        f"UID={params['user']};"
        f"PWD={params['password']};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=5;"
    )


def public_runtime():
    """Valores que la app puede aplicar al arrancar. Sin contraseñas."""
    empty = {
        'llm_chat': '',
        'llm_report': '',
        'llm_semantic': '',
        'llm_sql_training': '',
        'ai_provider': 'ollama',
        'ollama_host': '',
        'gemini_model': '',
        'show_sql': False,
        'training_mode': False,
        'auto_load_actualidad': True,
        'fast_bulk': False,
        'mobile_specialized': False,
        'perf_preset': 'auto',
        'app_name': '',
        'erp_name': '',
    }
    try:
        from datia.models.master import GlobalConfig
        cfg = GlobalConfig.load()
        data = cfg.implanter_settings or {}
        return {
            'llm_chat': cfg.llm_chat or '',
            'llm_report': cfg.llm_report or '',
            'llm_semantic': cfg.llm_semantic or '',
            'llm_sql_training': cfg.llm_sql_training or '',
            'ai_provider': cfg.ai_provider or 'ollama',
            'ollama_host': cfg.ollama_host or '',
            'gemini_model': cfg.gemini_model or '',
            'show_sql': bool(cfg.show_sql),
            'training_mode': bool(cfg.training_mode),
            'auto_load_actualidad': bool(cfg.auto_load_actualidad),
            'fast_bulk': bool(cfg.fast_bulk),
            'mobile_specialized': bool(cfg.mobile_specialized),
            'perf_preset': cfg.perf_preset or 'auto',
            'app_name': cfg.app_name or data.get('app_name') or '',
            'erp_name': cfg.erp_name or data.get('erp_name') or '',
        }
    except Exception:
        return empty
