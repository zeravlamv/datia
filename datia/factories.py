from typing import Any
import os

class ServiceFactory:
    """
    Singleton Factory for Service instantiation.
    Ensures services are singleton (cached) where appropriate.
    """
    _instances = {}

    @classmethod
    def get_etl_service(cls):
        # Local import to avoid circular dep
        from datia.services.etl_service import ETLService
        if 'etl_service' not in cls._instances:
            cls._instances['etl_service'] = ETLService()
        return cls._instances['etl_service']

    @classmethod
    def get_totals_service(cls):
        from datia.services.totals_service import TotalsService
        if 'totals_service' not in cls._instances:
            cls._instances['totals_service'] = TotalsService()
        return cls._instances['totals_service']
    
    @classmethod
    def get_ai_service(cls):
        from datia.services.ai_service import IAService
        if 'ai_service' not in cls._instances:
            cls._instances['ai_service'] = IAService()
        return cls._instances['ai_service']

    @classmethod
    def get_embedding_service(cls):
        from datia.services.embedding_service import EmbeddingService
        if 'embedding_service' not in cls._instances:
            cls._instances['embedding_service'] = EmbeddingService()
        return cls._instances['embedding_service']

    @classmethod
    def get_dashboard_service(cls):
        from datia.services.dashboard_service import DashboardService
        if 'dashboard_service' not in cls._instances:
            cls._instances['dashboard_service'] = DashboardService()
        return cls._instances['dashboard_service']

    @classmethod
    def get_report_llm_service(cls, kind: str = ""):
        provider = (os.environ.get("DATIA_REPORT_LLM_PROVIDER") or os.environ.get("DATIA_LLM_PROVIDER") or "ollama").strip().lower()
        cache_key = f"llm_report:{provider}"
        if cache_key in cls._instances:
            return cls._instances[cache_key]
        if provider == "gemini":
            from datia.services.gemini_service import GeminiService
            cls._instances[cache_key] = GeminiService()
        else:
            from datia.services.ollama_service import OllamaService
            cls._instances[cache_key] = OllamaService()
        return cls._instances[cache_key]

class RepositoryFactory:
    """
    Singleton Factory for Repository instantiation.
    """
    _instances = {}

    @classmethod
    def get_totals_repository(cls):
        from datia.repositories.totals_repository import TotalsRepository
        if 'totals_repository' not in cls._instances:
            cls._instances['totals_repository'] = TotalsRepository()
        return cls._instances['totals_repository']
