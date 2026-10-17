from datia.services.ai.context_builders.ventas_context import VentasContextBuilder
from datia.services.ai.context_builders.financial_context import FinancialContextBuilder
from datia.services.ollama_service import OllamaService
import logging
import time as _time
import uuid
import threading
import json
import os
from django.conf import settings
from django.db import close_old_connections
from datia.services.cache_service import compute_mssql_fingerprint
from datia.factories import ServiceFactory

logger = logging.getLogger('datia')
AI_PROGRESS = {}
REPORT_CACHE = {}
REPORT_CACHE_TTL = int(os.environ.get('DATIA_REPORT_TTL', '600'))
REPORT_CACHE_LOCK = threading.Lock()
REPORT_CACHE_MAX = int(os.environ.get('DATIA_REPORT_CACHE_MAX', '50'))
REPORT_FP = None

# Import Generators
from datia.services.ai.reports.financial import FinancialReportGenerator

def _progress(req_id: str, step: str, message: str = "", percent: int = None):
    """
    Helper para registrar eventos de progreso en memoria.
    """
    try:
        ev = {"ts": _time.time(), "step": step, "message": message}
        if percent is not None:
            ev["percent"] = percent
        # Use simple global dict for progress (consider redis for production)
        AI_PROGRESS.setdefault(req_id, []).append(ev)
        logger.info(f"[AI_PROGRESS {req_id}] {step} -- {message}" + (f" ({percent}%)" if percent is not None else ""))
    except Exception as e:
        logger.error(f"[AI_PROGRESS_ERROR {req_id}] {e}")

class DashboardService:
    """
    Servicio especializado en la generación de Cuadros de Mando (Dashboards) e Informes Estratégicos.
    Maneja la lectura y generación de JSONs de contexto y la creación de informes HTML.
    NO tiene dependencias de Chat ni SQL RAG.
    """
    
    def generate_strategic_report(self, empresa: int, ejercicio: int, kind: str = 'ventas', model: str = None, role: str = None) -> dict:
        """
        Inicia la generación del informe en SEGUNDO PLANO (Async).
        Retorna inmediatamente el ID de la solicitud para polling.
        """
        req_id = f"{kind}-{empresa}-{ejercicio}-{uuid.uuid4().hex[:8]}"
        try:
            AI_PROGRESS.setdefault(req_id, [])
            AI_PROGRESS[req_id].append({"ts": _time.time(), "step": "QUEUED", "message": "Solicitud recibida", "percent": 0})
        except Exception:
            pass
        
        def _worker():
            # Ensure DB connections are managed in thread
            close_old_connections()
            try:
                _progress(req_id, "ARRANQUE", f"Proceso Async Iniciado. Empresa={empresa}", 0)
                
                # --- 1. Context Acquisition ---
                data_context = {}
                try:
                    ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
                except Exception:
                    ctx_dir = settings.BASE_DIR
                
                context_file = os.path.join(ctx_dir, f'datia_ai_context_{kind}_{empresa}_{ejercicio}.json')
                legacy_context_file = os.path.join(ctx_dir, f'datia_ai_context_{kind}.json')
                context_source = None
                current_file = None

                # Check Disk Cache
                if os.path.exists(context_file):
                    with open(context_file, 'r', encoding='utf-8') as f: data_context = json.load(f)
                    context_source = "disk"
                    try:
                        context_mtime = os.path.getmtime(context_file)
                    except Exception:
                        context_mtime = None
                    current_file = context_file
                    _progress(req_id, "LECTURA_DISCO", f"Contexto encontrado: {os.path.basename(context_file)}", 10)
                elif os.path.exists(legacy_context_file):
                    with open(legacy_context_file, 'r', encoding='utf-8') as f: data_context = json.load(f)
                    context_source = "disk-legacy"
                    try:
                        context_mtime = os.path.getmtime(legacy_context_file)
                    except Exception:
                        context_mtime = None
                    current_file = legacy_context_file
                    _progress(req_id, "LECTURA_DISCO", f"Contexto legado: {os.path.basename(legacy_context_file)}", 10)

                # [STRICT MODE] Disk Only
                if not data_context:
                    msg = f"Falta archivo JSON de contexto en {context_file}. Ejecute Sincronización ETL primero."
                    _progress(req_id, "ERROR_DATOS", msg, 100)
                    AI_PROGRESS[req_id].append({"status": "error", "error": msg})
                    return
                _progress(req_id, "CONTEXT_SOURCE", f"{context_source or 'unknown'}", 12)
                _progress(req_id, "CONTEXT_FILE", os.path.basename(current_file) if current_file else "unknown", 12)
                if context_mtime is not None:
                    _progress(req_id, "CONTEXT_MTIME", str(context_mtime), 12)
                try:
                    if isinstance(data_context, dict):
                        _keys = list(data_context.keys())
                        _progress(req_id, "CONTEXT_KEYS_COUNT", str(len(_keys)), 12)
                        _sample = ", ".join([str(k) for k in _keys[:10]])
                        _progress(req_id, "CONTEXT_KEYS", _sample, 12)
                except Exception:
                    pass

                fp = compute_mssql_fingerprint()
                with REPORT_CACHE_LOCK:
                    global REPORT_FP
                    if REPORT_FP != fp:
                        REPORT_CACHE.clear()
                        REPORT_FP = fp
                cache_key = f"{fp}:{kind}:{empresa}:{ejercicio}"
                with REPORT_CACHE_LOCK:
                    entry = REPORT_CACHE.get(cache_key)
                    if entry and (_time.time() - entry.get("ts", 0) < REPORT_CACHE_TTL) and (entry.get("context_mtime") == context_mtime):
                        AI_PROGRESS[req_id].append({"status": "completed", "result": entry["result"]})
                        _progress(req_id, "CACHE_HTML", "Usando informe en caché", 100)
                        return
                    _progress(req_id, "CACHE_MISS", "Generación requerida", 15)

                # --- 2. Prompting ---
                _progress(req_id, "LLM_INICIO", "Preparando prompt para IA...", 20)
                
                if kind == 'financiera':
                    def _as_dict(x):
                        if isinstance(x, dict):
                            return x
                        if isinstance(x, list):
                            for it in x:
                                if isinstance(it, dict):
                                    return it
                            return {}
                        return {}
                    kpis = _as_dict(data_context.get('kpis_globales'))
                    pl = _as_dict(data_context.get('pl_analisis'))
                    tes = _as_dict(data_context.get('tesoreria'))
                    bal = _as_dict(data_context.get('balance_situacion'))
                    sen = data_context.get('tendencias_anomalias') or data_context.get('alertas_sistema') or {}
                    if not isinstance(sen, dict):
                        if isinstance(sen, list):
                            sen = {"items": sen[:5]}
                        else:
                            sen = {}
                    summary = {
                        "kpis": {
                            "ventas": kpis.get("ventas"),
                            "ebitda": kpis.get("ebitda"),
                            "margen_op_pct": kpis.get("margen_op_pct")
                        },
                        "pl": {
                            "ingresos": pl.get("ingresos"),
                            "costes": pl.get("costes"),
                            "resultado": pl.get("resultado")
                        },
                        "tesoreria": {
                            "liquidez": tes.get("liquidez") or tes.get("ratio_liquidez"),
                            "deuda_total": tes.get("deuda_total")
                        },
                        "balance": {
                            "solvencia": bal.get("solvencia") or bal.get("ratio_solvencia")
                        },
                        "señales": sen
                    }
                    json_str = json.dumps(summary, ensure_ascii=False)
                    _progress(req_id, "PROMPT_BYTES", str(len(json_str)), 20)
                    base_prompt = (
                        f"Eres un Senior Financial Controller y CFO. Analiza el resumen económico del ejercicio {ejercicio} y redacta un informe ejecutivo. "
                        f"Estructura en 4 secciones: Resumen Ejecutivo, Análisis de Rentabilidad, Salud del Balance y Recomendaciones Estratégicas. "
                        f"Usa solo la información disponible, evita conjeturas y devuelve exclusivamente HTML (div, h3, p, ul, li, b). "
                        f"Datos: {json_str[:6000]}..."
                    )
                else:
                    json_str = json.dumps(data_context, ensure_ascii=False, indent=2)
                    _progress(req_id, "PROMPT_BYTES", str(len(json_str)), 20)
                    sig = data_context.get('señales') or {}
                    prod_list = (data_context.get('productos_negativos') or [])[:3]
                    cli_list = (data_context.get('clientes_riesgo') or [])[:3]
                    prod_names = [ (p.get('nombre') or f"Art {p.get('articulo')}") for p in prod_list ]
                    cli_names = [ (c.get('nombre') or f"Cliente {c.get('cliente')}") for c in cli_list ]
                    evidencias = (
                        f"Margen {float(sig.get('margen_pct', 0)):.2f}% ; "
                        f"Productos negativos: {int(sig.get('productos_negativos_count', len(prod_list)))}"
                        + (f" (top: {', '.join(prod_names)})" if prod_names else "") + "; "
                        f"Clientes en riesgo: {int(sig.get('clientes_riesgo_count', len(cli_list)))}"
                        + (f" (top: {', '.join(cli_names)})" if cli_names else "") + "; "
                        f"Concentración de ventas: {float(sig.get('concentracion_pct', 0)):.2f}% ; "
                        f"Meses con caída YoY: {int(sig.get('meses_yoy_caida', 0))}."
                    )
                    base_prompt = (
                        f"Eres un Director Comercial senior. Analiza el JSON del ejercicio {ejercicio} y redacta un informe ejecutivo de alto impacto. "
                        f"Debes estructurar el análisis en 5 secciones: "
                        f"1) Resumen Ejecutivo, 2) Distribución de Margen, 3) Mix Comercial, 4) Estacionalidad y Anomalías, 5) Recomendaciones (30/60/90 días). "
                        f"Reglas: usa solo datos del JSON, prioriza margen sobre volumen, cita evidencias cuantitativas (porcentaje, euros), "
                        f"no menciones 'JSON' ni 'SQL', devuelve exclusivamente HTML (div, h3, p, ul, li, b), sin Markdown. "
                        f"Evidencias disponibles: {evidencias} "
                        f"Datos: {json_str[:15000]}..."
                    )

                # --- 3. Execution (Ollama) ---
                report_html = ""
                used_model = "unknown"
                run_fallback = False
                
                selected_model = None
                req_model = None

                # [NEW STRATEGY PATTERN] Delegate to specialized generators
                if kind == 'financiera':
                    try:
                        _progress(req_id, "GENERADOR_FINANCIERO", "Iniciando análisis profundo...", 30)
                        # Pre-warm para modelos grandes si el usuario ha forzado uno
                        try:
                            if model and ('qwen3' in str(model).lower()):
                                _progress(req_id, "WARMUP", f"Precalentando modelo {model}...", 28)
                                svc_warm = OllamaService()
                                # Warm-up corto y no bloqueante (si falla, se ignora)
                                try:
                                    svc_warm.generate_text(
                                        prompt="OK",
                                        timeout=60,
                                        model=model,
                                        options={"num_predict": 8, "temperature": 0, "top_p": 0.9}
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        gen = FinancialReportGenerator()
                        # Pass model if user forced one, else generator decides
                        res_gen = gen.generate(
                            context=data_context, 
                            ejercicio=ejercicio, 
                            model=model,
                            force_fallback=(str(model).lower() == 'fallback'),
                            role=role,
                            req_id=req_id
                        )
                        report_html = res_gen.get("html", "")
                        used_model = res_gen.get("model_used", "unknown")
                        reason = res_gen.get("reason")
                        try:
                            req_model = res_gen.get("selected_model", None) or model
                        except Exception:
                            req_model = model
                        if res_gen.get("status") == "fallback":
                            run_fallback = True
                        _progress(req_id, "GENERADOR_DONE", "Análisis completado", 90)
                    except Exception as e:
                        logger.error(f"Financial Generator Failed: {e}")
                        run_fallback = True
                
                else:
                    # Legacy Logic for Sales/Other (Keep as is for now or refactor later)
                    try:
                        available_models = []
                        force_fallback = bool(model) and str(model).lower() == 'fallback'
                        llm = ServiceFactory.get_report_llm_service(kind=kind)
                        provider_is_ollama = llm.__class__.__name__.lower().startswith("ollama")
                        
                        if not force_fallback:
                            try:
                                if provider_is_ollama and hasattr(llm, "list_models"):
                                    available_models = llm.list_models()
                            except Exception as e:
                                logger.warning(f"Ollama list_models failed: {e}")
                                available_models = []
                        
                        selected_model = None
                        if not force_fallback and available_models:
                            # Centralized selector in OllamaService
                            if hasattr(llm.__class__, "select_preferred_model"):
                                selected_model = llm.__class__.select_preferred_model(kind, available_models)
                            _progress(req_id, "MODEL_SELECT", f"Preferido: {selected_model}" if selected_model else "Sin preferencia", 25)

                        prompt = f"{base_prompt}"
                        req_model = model
                        
                        # Logic specific for 'ventas' model selection
                        if kind == 'ventas':
                            sig = data_context.get('señales') or {}
                            escalate = False
                            try:
                                if float(sig.get('margen_pct', 0)) < 10:
                                    escalate = True
                                if int(sig.get('meses_yoy_caida', 0)) >= 3:
                                    escalate = True
                                if int(sig.get('clientes_riesgo_count', 0)) >= 2:
                                    escalate = True
                                if float(sig.get('concentracion_pct', 0)) > 60:
                                    escalate = True
                                if int(sig.get('productos_negativos_count', 0)) >= 3:
                                    escalate = True
                            except Exception:
                                escalate = False
                            if escalate and not force_fallback and provider_is_ollama:
                                req_model = 'qwen2.5:7b'
                        
                        # Prefer selected model if available
                        if not force_fallback and not req_model and selected_model:
                            req_model = selected_model
                        
                        _progress(req_id, "MODEL_REQUEST", f"Solicitado: {req_model or 'default'}", 30)
                        model_name = (req_model or selected_model or "") or ""
                        dln = 240
                        try:
                            mn = str(model_name).lower()
                            if 'qwen3:72b' in mn:
                                dln = 1500
                            elif 'qwen3:30b' in mn:
                                dln = 1200
                            elif 'qwen3' in mn:
                                dln = 900
                            elif 'qwen2.5:14b' in mn:
                                dln = 300
                            elif 'qwen2.5:7b' in mn:
                                dln = 240
                        except Exception:
                            dln = 240
                        res = llm.generate_text_with_policy(prompt, kind, requested_model=req_model, force_fallback=force_fallback, deadline=dln, req_id=req_id)
                        
                        if res.get("status") == "ok":
                            report_html = res.get("text", "")
                            used_model = res.get("model") or "unknown"
                            req_model = req_model or selected_model
                            _progress(req_id, "LLM_DONE", "Generación completada", 90)
                        elif res.get("status") == "fallback":
                            run_fallback = True
                        else:
                            run_fallback = True
                    
                    except Exception as ollama_err:
                        logger.error(f"Ollama Critical Error: {ollama_err}")
                        run_fallback = True

                if run_fallback and kind != 'financiera':
                    # Only define markup_func for non-financial or if financial failed completely outside generator
                    markup_func = self._build_fallback_sales_report_html
                    fallback_html = markup_func(data_context, ejercicio)
                    
                    if not force_fallback:
                         fallback_html = '<div style="background:#fff3cd; color:#856404; padding:10px; border-radius:4px; margin-bottom:15px; border:1px solid #ffeeba;">⚠️ <b>Aviso:</b> Usando informe base (Fallback).</div>' + fallback_html
                    
                    report_html = fallback_html
                    used_model = "fallback"
                    _progress(req_id, "FALLBACK_ACTIVADO", "Fallback activo", 90)

                # --- 4. KPIs & Finish ---
                _progress(req_id, "FINALIZANDO", "Guardando resultados...", 95)
                
                # KPIs for Frontend
                kpis_data = data_context.get("kpis_globales") or data_context.get("kpis", {})
                frontend_kpis = []
                if kind == 'financiera':
                    frontend_kpis = [
                        {'label': 'Ventas', 'value': f"{kpis_data.get('ventas', 0):,.2f}€", 'color': 'blue'},
                        {'label': 'EBITDA', 'value': f"{kpis_data.get('ebitda', 0):,.2f}€", 'color': 'green'},
                        {'label': 'Margen %', 'value': f"{kpis_data.get('margen_op_pct', 0):.1f}%", 'color': 'orange'},
                    ]
                else:
                    frontend_kpis = [
                        {'label': 'Ventas Totales', 'value': f"{kpis_data.get('ventas_totales', 0):,.2f}€", 'color': 'blue'},
                        {'label': 'Margen %', 'value': f"{kpis_data.get('margen_beneficio_pct', 0):.1f}%", 'color': 'green'},
                        {'label': 'Operaciones', 'value': str(kpis_data.get('total_operaciones', 0)), 'color': 'purple'},
                    ]

                # RESULT PAYLOAD
                final_result = {
                    "status": "success",
                    "html": report_html,
                    "kpis": frontend_kpis,
                    "model_used": used_model,
                    "reason": locals().get("reason"),
                    "selected_model": selected_model,
                    "requested_model": req_model,
                    "raw_data": data_context,
                    "context_mtime": context_mtime,
                    "context_source": context_source or "unknown",
                    "type": "report"
                }
                with REPORT_CACHE_LOCK:
                    REPORT_CACHE[cache_key] = {"ts": _time.time(), "result": final_result, "context_mtime": context_mtime}
                    if len(REPORT_CACHE) > REPORT_CACHE_MAX:
                        # Evict oldest by ts
                        oldest_key = None
                        oldest_ts = None
                        for k, v in REPORT_CACHE.items():
                            tsv = v.get("ts", 0)
                            if oldest_ts is None or tsv < oldest_ts:
                                oldest_ts = tsv
                                oldest_key = k
                        if oldest_key:
                            REPORT_CACHE.pop(oldest_key, None)
                # Store Result in Memory for Polling
                AI_PROGRESS[req_id].append({"status": "completed", "result": final_result})
                _progress(req_id, "COMPLETADO", "Informe disponible", 100)
                
                # Auto-Save to DB
                try:
                    from datia.models import MetricsSavedQuery
                    last_answer = {
                        "type": "ai_report",
                        "html": report_html,
                        "origin": f"ia-{kind}",
                        "kind": kind,
                        "empresa": empresa,
                        "ejercicio": ejercicio,
                        "model_used": used_model,
                        "selected_model": selected_model,
                        "requested_model": req_model,
                        "context_source": context_source or "unknown",
                        "context_mtime": context_mtime,
                        "raw_data": data_context
                    }
                    MetricsSavedQuery.objects.create(
                        empresa=empresa,
                        ejercicio=ejercicio,
                        query=f"AI_REPORT:{kind}:auto",
                        last_answer=last_answer
                    )
                    logger.info(f"[AI] Auto-Saved Report {req_id}")
                except Exception as db_err:
                    logger.error(f"[AI] Auto-Save Error: {db_err}")
                
                close_old_connections()

            except Exception as e:
                logger.error(f"[AI] Worker Panic: {e}")
                _progress(req_id, "ERROR", f"Error crítico: {str(e)}", 100)
                AI_PROGRESS[req_id].append({"status": "error", "error": str(e)})
                close_old_connections()

        # Start Thread
        t = threading.Thread(target=_worker)
        t.daemon = True
        t.start()
        
        return {
            "status": "pending",
            "request_id": req_id,
            "message": "Generación iniciada en segundo plano"
        }

    def generate_context(self, empresa: int, ejercicio: int, kind: str = 'ventas') -> dict:
        """
        Public endpoint to get raw JSON context.
        """
        try:
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        except Exception:
            ctx_dir = settings.BASE_DIR
            
        context_file = os.path.join(ctx_dir, f'datia_ai_context_{kind}_{empresa}_{ejercicio}.json')
        legacy_context_file = os.path.join(ctx_dir, f'datia_ai_context_{kind}.json')
        data_context = {}
        
        try:
            if os.path.exists(context_file):
                with open(context_file, 'r', encoding='utf-8') as f:
                    data_context = json.load(f)
            elif os.path.exists(legacy_context_file):
                with open(legacy_context_file, 'r', encoding='utf-8') as f:
                    data_context = json.load(f)
        except Exception:
            data_context = {}
            
        if data_context:
            return {
                "status": "success",
                "kind": kind,
                "empresa": empresa,
                "ejercicio": ejercicio,
                "data": data_context,
                "context_source": "disk" if os.path.exists(context_file) else "disk-legacy"
            }
        else:
            return {
                "status": "no_context",
                "kind": kind,
                "empresa": empresa,
                "ejercicio": ejercicio,
                "data": {},
                "expected_path": context_file,
                "legacy_expected_path": legacy_context_file,
                "context_source": "missing"
            }

    def build_context(self, empresa: int, ejercicio: int, kind: str = 'ventas') -> dict:
        try:
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        except Exception:
            ctx_dir = settings.BASE_DIR
        if not os.path.exists(ctx_dir):
            try:
                os.makedirs(ctx_dir, exist_ok=True)
            except Exception as e:
                return {"status": "error", "message": str(e)}
        try:
            if kind == 'financiera':
                builder = FinancialContextBuilder()
            else:
                builder = VentasContextBuilder()
            context = builder.build_context(empresa, ejercicio)
            path = os.path.join(ctx_dir, f'datia_ai_context_{kind}_{empresa}_{ejercicio}.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(context, f, ensure_ascii=False, indent=2)
            try:
                if kind != 'financiera':
                    from datia.factories import ServiceFactory
                    emb = ServiceFactory.get_embedding_service()
                    emb.add_embedding(
                        text=json.dumps(context, ensure_ascii=False),
                        sql="",
                        metadata={"empresa": empresa, "ejercicio": ejercicio, "type": kind},
                        kind="context",
                        key=f"context_{kind}_{empresa}_{ejercicio}"
                    )
            except Exception:
                pass
            return {"status": "built", "kind": kind, "empresa": empresa, "ejercicio": ejercicio, "path": path, "context_source": "disk"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --- HTML Generator Helpers ---
    def _build_fallback_financial_report_html(self, data_context: dict, ejercicio: int) -> str:
        # DEPRECATED: Logic moved to FinancialReportGenerator
        # Keeping wrapper just in case any old call relies on it, or for quick debug
        from datia.services.ai.reports.financial import FinancialReportGenerator
        gen = FinancialReportGenerator()
        return gen._build_deterministic_report(data_context, ejercicio)

    def _build_fallback_sales_report_html(self, data_context: dict, ejercicio: int) -> str:
        try:
            kpis = data_context.get("kpis", {})
            resumen_total = kpis.get("ventas_totales", 0)
            return (
                f'<div class="ai-report-section">'
                f'<h3>📊 Resumen de Ventas {ejercicio}</h3>'
                f'<p>Ventas Totales: <b>{resumen_total:,.2f} €</b></p>'
                f'<p>Consulte el Dashboard interactivo para desglose por clientes y productos.</p>'
                f'</div>'
            )
        except Exception:
            return "<p>Error en fallback de ventas.</p>"
