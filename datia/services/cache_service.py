import hashlib
import json
from django.core.cache import cache
from typing import Optional, Dict, Any
from django.conf import settings

def compute_mssql_fingerprint() -> str:
    host = getattr(settings, 'MSSQL_HOST', '')
    port = str(getattr(settings, 'MSSQL_PORT', ''))
    user = getattr(settings, 'MSSQL_USER', '')
    name = getattr(settings, 'MSSQL_NAME', '')
    raw = f"{host}:{port}:{user}:{name}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()[:8]

class CacheService:
    """
    Generic Cache Wrapper.
    """
    def get(self, key: str) -> Any:
        return cache.get(key)

    def set(self, key: str, value: Any, ttl: int = 3600):
        cache.set(key, value, timeout=ttl)

    def delete(self, key: str):
        cache.delete(key)

class QueryCacheService:
    """
    Service to cache generated SQL queries based on user questions and context.
    TTL: 24 hours (86400 seconds)
    """
    CACHE_TTL = 86400 

    @staticmethod
    def _generate_key(question: str, empresa: int) -> str:
        # Normalize inputs
        q_norm = question.strip().lower()
        key_str = f"{str(empresa)}:{q_norm}"
        return f"sql_cache:{hashlib.md5(key_str.encode('utf-8')).hexdigest()}"

    @staticmethod
    def get(question: str, empresa: int) -> Optional[Dict[str, Any]]:
        key = QueryCacheService._generate_key(question, empresa)
        return cache.get(key)

    @staticmethod
    def set(question: str, empresa: int, data: Dict[str, Any]):
        key = QueryCacheService._generate_key(question, empresa)
        cache.set(key, data, timeout=QueryCacheService.CACHE_TTL)
        
    @staticmethod
    def invalidate(question: str, empresa: int):
        key = QueryCacheService._generate_key(question, empresa)
        cache.delete(key)
