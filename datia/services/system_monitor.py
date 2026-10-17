import psutil
import platform
import logging
from typing import Dict, Any
from django.db import connections

logger = logging.getLogger(__name__)


class SystemMonitorService:
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count(logical=True)
            mem = psutil.virtual_memory()
            ram_total_gb = round(mem.total / (1024**3), 2)
            ram_used_gb = round(mem.used / (1024**3), 2)
            ram_percent = mem.percent
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            health_score = 100 - max(cpu_percent, ram_percent, disk_percent)
            health_score = max(0, health_score)
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "cores": cpu_count,
                },
                "memory": {
                    "total_gb": ram_total_gb,
                    "used_gb": ram_used_gb,
                    "percent": ram_percent,
                },
                "disk": {
                    "percent": disk_percent,
                },
                "health_score": round(health_score, 1),
                "platform": platform.system(),
            }
        except Exception as e:
            logger.error(f"Error gathering system metrics: {e}")
            return {
                "error": str(e),
                "health_score": 50,
            }

    @staticmethod
    def get_adaptive_config(metrics: Dict[str, Any], preset: str = "auto") -> Dict[str, Any]:
        config = {
            "rag_k": 5,
            "timeout": 30,
            "max_tokens": 2000,
        }
        if preset == "turbo":
            config = {
                "rag_k": 8,
                "timeout": 60,
                "max_tokens": 4096,
            }
        elif preset == "eco":
            config = {
                "rag_k": 3,
                "timeout": 15,
                "max_tokens": 1024,
            }
        elif preset == "auto":
            score = metrics.get("health_score", 50)
            if score > 80:
                config["rag_k"] = 6
                config["timeout"] = 45
            elif score > 50:
                config["rag_k"] = 4
                config["timeout"] = 30
            else:
                config["rag_k"] = 2
                config["timeout"] = 15
                config["max_tokens"] = 512
        return config

    @staticmethod
    def get_database_schema_status() -> Dict[str, Any]:
        alias = "analytics" if "analytics" in connections.databases else "default"
        try:
            with connections[alias].cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s LIMIT 1",
                    ["datia_empresa"],
                )
                exists = cursor.fetchone() is not None
            if not exists:
                return {
                    "ok": False,
                    "missing_tables": ["datia_empresa"],
                    "message": "Tabla base datia_empresa no encontrada en el esquema public.",
                    "db_alias": alias,
                }
            return {
                "ok": True,
                "missing_tables": [],
                "message": "Esquema base correcto.",
                "db_alias": alias,
            }
        except Exception as e:
            logger.error(f"Error checking database schema: {e}")
            return {
                "ok": False,
                "missing_tables": ["datia_empresa"],
                "message": str(e),
                "db_alias": alias,
            }
