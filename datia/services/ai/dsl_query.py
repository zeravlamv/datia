import json
import uuid
from typing import Any, Dict, List, Tuple
from django.conf import settings
from django.db.models import Sum, Avg, Count, F
from datia.models.totales import (
    MetricsTotalesEmpresaEjercicioCliente,
    MetricsTotalesEmpresaEjercicioArticulo,
    MetricsTotalesEmpresaEjercicioMes,
)
from datia.models.financial import DatiaAcumuladosConta
from datia.services.ollama_service import OllamaService
import os
from datia.services.embedding_service import EmbeddingService
from django.db.models import IntegerField, F
from django.db.models.functions import ExtractMonth, ExtractDay
try:
    from django.db.models.functions import ExtractWeek, ExtractQuarter
except Exception:
    ExtractWeek = None
    ExtractQuarter = None

ALLOWED_SOURCES = {
    "metrics_clientes": MetricsTotalesEmpresaEjercicioCliente,
    "metrics_articulos": MetricsTotalesEmpresaEjercicioArticulo,
    "metrics_mensual": MetricsTotalesEmpresaEjercicioMes,
    "financial_acumulados": DatiaAcumuladosConta,
}

ALLOWED_FUNCS = {"sum": Sum, "avg": Avg, "count": Count}

TABLE_TO_SOURCE = {
    "metrics_totales_empresa_ejercicio_cliente": "metrics_clientes",
    "metrics_totales_empresa_ejercicio_articulo": "metrics_articulos",
    "metrics_totales_empresa_ejercicio_mes": "metrics_mensual",
}

class DSLQueryError(Exception):
    pass

class DSLQueryExecutor:
    """
    Ejecuta consultas IA mediante un DSL seguro compilado a Django ORM.
    """
    @staticmethod
    def generate_dsl_from_text(query_text: str, empresa: int, ejercicio: int) -> Dict[str, Any]:
        """
        Usa el modelo IA para transformar la consulta natural en un JSON-DSL.
        """
        schema_hint = {
            "source": "",
            "filters": [{"field": "campo", "op": "eq|gt|lt|in|contains", "value": "valor"}],
            "group_by": ["campo1", "campo2"],
            "aggregations": [{"field": "campo", "func": "sum|avg|count", "alias": "nombre"}],
            "order_by": [{"field": "campo|alias", "dir": "asc|desc"}],
            "limit": 100,
            "time": {
                "group": "day|week|month|quarter|semester|year",
                "date_field": "Fecha|FechaPedido|FechaAlbaran",
                "range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
                "interval": "days|months|quarters|years"
            }
        }
        emb = EmbeddingService()
        schema_hits = emb.search_schema(query_text, threshold=0.35, limit=3)
        template_hit = emb.search_template(query_text, threshold=0.35) or {}
        recommended_sources = []
        recommended_fields = []
        try:
            for hit in (schema_hits or []):
                meta = hit.get("metadata") if isinstance(hit.get("metadata"), dict) else hit.get("metadata")
                tbl = (meta or {}).get("table") or hit.get("table")
                src = TABLE_TO_SOURCE.get(tbl)
                if src and src not in recommended_sources:
                    recommended_sources.append(src)
                fields = (meta or {}).get("fields") or []
                for f in fields:
                    if f not in recommended_fields:
                        recommended_fields.append(f)
        except Exception:
            pass
        if not recommended_sources:
            recommended_sources = []
        hints = {
            "schema_hits": schema_hits,
            "template_hit": template_hit,
            "recommended_sources": recommended_sources,
            "recommended_fields": recommended_fields,
            "empresa": empresa,
            "ejercicio": ejercicio,
        }
        prompt = (
            "Convierte la siguiente consulta a un JSON estricto siguiendo este DSL."
            " Devuelve solo JSON válido, sin comentarios ni texto adicional.\n"
            f"DSL Schema Ejemplo: {json.dumps(schema_hint)}\n"
            f"Contexto: empresa={empresa}, ejercicio={ejercicio}.\n"
            "Fuentes válidas (elige siempre UNA de estas en 'source'):\n"
            "- 'metrics_mensual': métricas agregadas por mes (importe_neto_total, margen, etc.).\n"
            "- 'metrics_clientes': métricas agregadas por cliente.\n"
            "- 'metrics_articulos': métricas agregadas por artículo.\n"
            "- 'financial_acumulados': acumulados contables por cuenta/periodo.\n"
            f"Fuentes preferidas según el contexto (subset de las anteriores): {', '.join(recommended_sources)}.\n"
            f"Columnas sugeridas: {', '.join(recommended_fields) if recommended_fields else '(usar columnas estándar)'}.\n"
            "Reglas:\n"
            "1) 'source' debe ser exactamente una de: metrics_mensual, metrics_clientes, metrics_articulos o financial_acumulados.\n"
            "2) Incluye siempre filtros compatibles con 'empresa' y 'ejercicio' cuando existan en el modelo.\n"
            "3) Usa 'group_by' y 'aggregations' coherentes con columnas numéricas agregables.\n"
            "4) Devuelve SOLO JSON.\n"
            "Ejemplos de consultas que debes cubrir con el DSL:\n"
            "- \"ventas mensuales del año\" -> source=metrics_mensual, group_by=['mes'], aggregations sobre importe_neto_total.\n"
            "- \"top clientes por importe neto\" -> source=metrics_clientes, group_by=['cliente'], aggregations sobre importe_neto_total, order_by por alias descendente.\n"
            "- \"evolución del margen por artículo\" -> source=metrics_articulos, group_by=['articulo'], time.group='month'.\n"
            "- \"ingresos totales por trimestre\" -> source=financial_acumulados o metrics_mensual, usando time.group='quarter'.\n"
            "Consulta del usuario:\n"
            f"{query_text}\n"
        )
        svc = OllamaService()
        res = svc.generate_text_with_policy(prompt, kind="dsl", requested_model=None, force_fallback=False, deadline=60)
        text = res.get("text") or "{}"
        try:
            dsl = json.loads(text)
        except Exception as e:
            raise DSLQueryError(f"JSON inválido del modelo: {e}")
        dsl = DSLQueryExecutor._enforce_hints(dsl, hints)
        dsl["_hints"] = hints
        return dsl

    @staticmethod
    def validate_dsl(dsl: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        src = dsl.get("source")
        if src not in ALLOWED_SOURCES:
            raise DSLQueryError("source no permitido")
        filters = dsl.get("filters") or []
        group_by = dsl.get("group_by") or []
        aggs = dsl.get("aggregations") or []
        order_by = dsl.get("order_by") or []
        limit = dsl.get("limit") or 100
        time = dsl.get("time") or {}
        # Validar bloque temporal
        if time:
            grp = (time.get("group") or "").lower()
            if grp and grp not in ("day", "week", "month", "quarter", "semester", "year"):
                raise DSLQueryError("time.group inválido")
            rng = time.get("range") or {}
            if rng:
                if not (rng.get("from") and rng.get("to")):
                    raise DSLQueryError("time.range requiere from y to")
        if not isinstance(filters, list) or not isinstance(group_by, list) or not isinstance(aggs, list):
            raise DSLQueryError("Estructura DSL inválida")
        if not isinstance(order_by, list) or not isinstance(limit, int):
            raise DSLQueryError("order_by/limit inválidos")
        for a in aggs:
            if a.get("func") not in ALLOWED_FUNCS:
                raise DSLQueryError("Función de agregación no permitida")
        return src, {"filters": filters, "group_by": group_by, "aggs": aggs, "order_by": order_by, "limit": limit, "time": time}

    @staticmethod
    def compile_and_execute(dsl: Dict[str, Any], empresa: int, ejercicio: int) -> List[Dict[str, Any]]:
        src, spec = DSLQueryExecutor.validate_dsl(dsl)
        Model = ALLOWED_SOURCES[src]
        qs = Model.objects.filter(empresa=int(empresa))
        # Asegurar ejercicio por defecto si existe el campo
        if hasattr(Model, "ejercicio"):
            qs = qs.filter(ejercicio=int(ejercicio))
        # Resolución y filtros temporales
        time = spec.get("time") or {}
        date_field_name = (time.get("date_field") or "").strip()
        model_fields = {f.name.lower(): f for f in Model._meta.get_fields() if hasattr(f, 'name')}
        # Candidatos de fecha si no se especifica
        if not date_field_name:
            for cand in ("fechapedido", "fechaalbaran", "fechadocumento", "fecha", "date"):
                if cand in model_fields:
                    date_field_name = cand
                    break
        # Rango temporal
        rng = time.get("range") or {}
        if rng:
            import datetime as _dt
            try:
                dt_from = _dt.datetime.fromisoformat(rng["from"])
                dt_to = _dt.datetime.fromisoformat(rng["to"])
                if date_field_name:
                    # Si es DateTimeField, forzar __date; si es DateField, rango directo
                    qs = qs.filter(**{f"{date_field_name}__date__range": (dt_from.date(), dt_to.date())}) \
                        if str(model_fields.get(date_field_name)).find("DateTimeField") >= 0 \
                        else qs.filter(**{f"{date_field_name}__range": (dt_from.date(), dt_to.date())})
                elif ("mes" in model_fields) and hasattr(Model, "ejercicio"):
                    # Fallback a métricas mensuales (mes + ejercicio)
                    if dt_from.year == dt_to.year:
                        qs = qs.filter(mes__gte=dt_from.month, mes__lte=dt_to.month, ejercicio=dt_from.year)
                    else:
                        qs = qs.filter(ejercicio__gte=dt_from.year, ejercicio__lte=dt_to.year)
                # Si no hay campo temporal, no aplicar rango para evitar errores
            except Exception:
                pass
        # Filtros seguros
        for f in spec["filters"]:
            field = f.get("field")
            op = f.get("op")
            val = f.get("value")
            if not field or not op:
                continue
            lookup = field
            if op in ("eq", "gt", "lt", "contains", "in"):
                if op == "gt": lookup = f"{field}__gt"
                elif op == "lt": lookup = f"{field}__lt"
                elif op == "contains": lookup = f"{field}__icontains"
                elif op == "in": lookup = f"{field}__in"
                qs = qs.filter(**{lookup: val})
        # Group & Aggregations
        annotate_kwargs = {}
        # Agrupación temporal: crea una etiqueta 'label' si time.group está definido
        tgroup = (time.get("group") or "").lower()
        if tgroup:
            if "mes" in model_fields and tgroup in ("month", "quarter", "semester"):
                if tgroup == "month":
                    qs = qs.annotate(label=F("mes"))
                elif tgroup == "quarter":
                    # (mes+2)//3
                    qs = qs.annotate(label=((F("mes") + 2) // 3))
                elif tgroup == "semester":
                    # (mes+5)//6
                    qs = qs.annotate(label=((F("mes") + 5) // 6))
            elif date_field_name:
                df = F(date_field_name)
                try:
                    if tgroup == "month":
                        qs = qs.annotate(label=ExtractMonth(df))
                    elif tgroup == "day":
                        qs = qs.annotate(label=ExtractDay(df))
                    elif tgroup == "week" and ExtractWeek:
                        qs = qs.annotate(label=ExtractWeek(df))
                    elif tgroup == "quarter" and ExtractQuarter:
                        qs = qs.annotate(label=ExtractQuarter(df))
                    elif tgroup == "semester":
                        # Derivar de mes
                        qs = qs.annotate(_m=ExtractMonth(df)).annotate(label=((F("_m") + 5) // 6))
                except Exception:
                    pass
        for a in spec["aggs"]:
            func = ALLOWED_FUNCS[a["func"]]
            fld = a.get("field")
            alias = a.get("alias") or f"{a['func']}_{fld}"
            if fld:
                annotate_kwargs[alias] = func(fld)
            else:
                annotate_kwargs[alias] = func("*")
        if annotate_kwargs:
            if tgroup and "label" in qs.query.annotations:
                qs = qs.values("label", *spec["group_by"]).annotate(**annotate_kwargs)
            else:
                qs = qs.values(*spec["group_by"]).annotate(**annotate_kwargs)
        else:
            if spec["group_by"]:
                if tgroup and "label" in qs.query.annotations:
                    qs = qs.values("label", *spec["group_by"])
                else:
                    qs = qs.values(*spec["group_by"])
        # Orden
        for o in spec["order_by"]:
            dir_ = o.get("dir", "asc")
            fld = o.get("field")
            if not fld:
                continue
            qs = qs.order_by(f"{'-' if dir_=='desc' else ''}{fld}")
        # Limit
        qs = qs[:spec["limit"]]
        # Serializar
        return list(qs)

    @staticmethod
    def _enforce_hints(dsl: Dict[str, Any], hints: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rec_sources = hints.get("recommended_sources") or []
            if dsl.get("source") not in rec_sources and rec_sources:
                dsl["source"] = rec_sources[0]
            rec_fields = set(hints.get("recommended_fields") or [])
            gb = dsl.get("group_by") or []
            if rec_fields:
                gb = [f for f in gb if f in rec_fields]
            dsl["group_by"] = gb
            aggs = dsl.get("aggregations") or []
            if rec_fields:
                aggs = [a for a in aggs if (a.get("field") in rec_fields) or (not a.get("field"))]
            dsl["aggregations"] = aggs
            ob = dsl.get("order_by") or []
            if rec_fields:
                filtered_ob = []
                for o in ob:
                    fld = o.get("field")
                    if not fld or fld in rec_fields:
                        filtered_ob.append(o)
                dsl["order_by"] = filtered_ob
        except Exception:
            pass
        return dsl

    @staticmethod
    def persist_result(empresa: int, ejercicio: int, query_text: str, dsl: Dict[str, Any], result: List[Dict[str, Any]]) -> Dict[str, Any]:
        rid = uuid.uuid4().hex[:8]
        try:
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        except Exception:
            ctx_dir = settings.BASE_DIR
        if not os.path.exists(ctx_dir):
            os.makedirs(ctx_dir, exist_ok=True)
        path = os.path.join(ctx_dir, f"datia_ai_query_{empresa}_{ejercicio}_{rid}.json")
        payload = {
            "empresa": empresa,
            "ejercicio": ejercicio,
            "query_text": query_text,
            "dsl": dsl,
            "result": result
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        try:
            from datia.models import MetricsSavedQuery
            MetricsSavedQuery.objects.create(
                empresa=empresa,
                ejercicio=ejercicio,
                query=f"AI_QUERY:{rid}",
                last_answer={"type": "ai_query", "path": path, "dsl": dsl, "count": len(result)}
            )
        except Exception:
            pass
        return {"id": rid, "path": path, "count": len(result)}
