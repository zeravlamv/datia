import logging
from typing import Dict, Any
from django.db import connections
from django.utils import timezone
from datia.services.embedding_service import EmbeddingService
from datia.services.ai.dsl_query import DSLQueryExecutor
from datia.services.query_builder import QueryBuilder
from datia.services.ai.handlers.generative_handler import GenerativeHandler
from datia.services.ai.formatter import ResponseFormatter
from datia.services.ai.language import LanguageService
from datia.models.ai import MetricsLLMConsultas
from datia.services.security.sql_guard import SQLGuard

logger = logging.getLogger('datia')

class BusinessAgent:
    def __init__(self):
        self.emb = EmbeddingService()
        self.formatter = ResponseFormatter()
        try:
            self.emb.index_schema()
        except Exception:
            pass
        try:
            self.emb.index_templates()
        except Exception:
            pass

    def ensure_schema_index(self, table_name: str | None = None) -> Dict[str, Any]:
        try:
            self.emb.index_schema(table_name=table_name)
            return {"status": "indexed", "table": table_name}
        except Exception as e:
            logger.error(f"Schema index failed: {e}")
            return {"status": "error", "message": str(e)}

    def answer(self, question: str, empresa: int, ejercicio: int, limit: int = 20, training_enabled: bool = False, model: str | None = None, lang: str = 'es') -> Dict[str, Any]:
        context = {"empresa": empresa, "ejercicio": ejercicio, "limit": limit, "training_enabled": training_enabled, "model": model, "lang": lang}
        try:
            match = QueryBuilder.build_from_nl(question, context)
            if match and not match.get('error'):
                sql = match.get('sql')
                data = []
                cols = []
                try:
                    SQLGuard.ensure_allowed(sql)
                    with connections['analytics'].cursor() as cursor:
                        cursor.execute(sql)
                        cols = [c[0] for c in cursor.description] if cursor.description else []
                        rows = cursor.fetchall() if cursor.description else []
                        data = [dict(zip(cols, r)) for r in rows]
                except Exception as e:
                    logger.error(f"Deterministic SQL failed: {e}")
                    return {"text": f"Error ejecutando consulta: {e}", "sql": sql, "type": "error"}
                MetricsLLMConsultas.objects.create(empresa=empresa, ejercicio=ejercicio, pregunta=question, respuesta=str({"count": len(data)}), sql_generado=sql)
                return {"type": match.get('type', 'table'), "sql": sql, "data": data, "label": match.get('label'), "source": match.get('source', 'deterministic_v2')}
        except Exception as e:
            logger.error(f"QueryBuilder error: {e}")
        try:
            dsl = DSLQueryExecutor.generate_dsl_from_text(question, empresa, ejercicio)
            result = DSLQueryExecutor.compile_and_execute(dsl, empresa, ejercicio)
            info = DSLQueryExecutor.persist_result(empresa, ejercicio, question, dsl, result)
            MetricsLLMConsultas.objects.create(empresa=empresa, ejercicio=ejercicio, pregunta=question, respuesta=str({"count": len(result)}), sql_generado=None)
            return {"type": "table", "data": result, "dsl": dsl, "source": "dsl", "persist_path": info.get("path")}
        except Exception as e:
            logger.warning(f"DSL path failed: {e}")
        try:
            handler = GenerativeHandler(self.formatter)
            intent = {"query": question}
            res = handler.handle(intent, context)
            MetricsLLMConsultas.objects.create(empresa=empresa, ejercicio=ejercicio, pregunta=question, respuesta=str(res.get("data") or res.get("answer") or {}), sql_generado=res.get("sql"))
            return res
        except Exception as e:
            msg = LanguageService.get_text('unavailable_error', lang) if hasattr(LanguageService, 'get_text') else "No se pudo generar una respuesta válida."
            logger.error(f"Generative failed: {e}")
            return {"text": msg, "type": "error"}
