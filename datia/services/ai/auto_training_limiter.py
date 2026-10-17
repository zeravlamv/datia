"""
Limitador de Auto-Training.
Controla frecuecia, duplicados y reglas de seguridad para el entrenamiento automático.
"""
from typing import Dict
from django.core.cache import cache

class AutoTrainingLimiter:
    """Gestiona límites de intentos y seguridad para auto-training."""
    
    msg_prefix = "auto_train_limit:"
    MAX_ATTEMPTS = 3
    TIMEOUT_SECONDS = 3600 # 1 hora de memoria para intentos
    
    @classmethod
    def should_attempt(cls, query_hash: str) -> bool:
        """
        Verifica si se debe intentar el auto-training para esta query.
        Basado en número de intentos previos fallidos.
        """
        key = f"{cls.msg_prefix}{query_hash}"
        attempts = cache.get(key, 0)
        
        if attempts >= cls.MAX_ATTEMPTS:
            return False
        
        return True

    @classmethod
    def record_attempt(cls, query_hash: str):
        """Incrementa el contador de intentos para esta query."""
        key = f"{cls.msg_prefix}{query_hash}"
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=cls.TIMEOUT_SECONDS)

    @classmethod
    def clear_attempts(cls, query_hash: str):
        """Limpia el historial (ej: si se logró éxito)."""
        key = f"{cls.msg_prefix}{query_hash}"
        cache.delete(key)
