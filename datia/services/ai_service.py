from datia.factories import ServiceFactory
from datia.services.ai.router import IntentRouter
from datia.services.ai.formatter import ResponseFormatter
from datia.services.ai.language import LanguageService
# from datia.services.ai.context_builders.ventas_context import VentasContextBuilder
# from datia.services.ai.context_builders.financial_context import FinancialContextBuilder
from datia.services.ollama_service import OllamaService
import requests
import re
import logging
import time as _time
import uuid

logger = logging.getLogger('datia')
AI_PROGRESS = {}

_TIPOS_CON_RESPUESTA = {
    'text', 'report', 'table', 'chart', 'card', 'cantidad',
    'ambiguity_alert', 'training_ask', 'no_data_option',
}


def _respuesta_tiene_valor(resultado) -> bool:
    """La consulta dejó algo que mostrar. Un importe a cero también cuenta."""
    if not isinstance(resultado, dict):
        return False
    if resultado.get('type') == 'error':
        return False
    texto = f"{resultado.get('text') or ''} {resultado.get('answer') or ''}"
    if 'no he podido' in texto.casefold() or 'error al procesar' in texto.casefold():
        return False
    if resultado.get('kpis') or resultado.get('data'):
        return True
    tabla = resultado.get('table') or {}
    if tabla.get('rows'):
        return True
    if resultado.get('source') in ('cartera', 'metricas_compra'):
        return True
    tipo = resultado.get('type')
    if not tipo and texto.strip():
        tipo = 'text'
    if tipo in _TIPOS_CON_RESPUESTA and texto.strip():
        return True
    if resultado.get('sql') and tipo in _TIPOS_CON_RESPUESTA:
        return True
    return False

def _progress(req_id: str, step: str, message: str = "", percent: int = None):
    try:
        ev = {"ts": _time.time(), "step": step, "message": message}
        if percent is not None:
            ev["percent"] = percent
        AI_PROGRESS.setdefault(req_id, []).append(ev)
        logger.info(f"[AI_PROGRESS {req_id}] {step} — {message}" + (f" ({percent}%)" if percent is not None else ""))
    except Exception:
        pass

class IAService:
    """
    Local AI Service Facade.
    Delegates logic to Router, Handlers, and Formatter.
    """
    def __init__(self):
        self.embedding_service = ServiceFactory.get_embedding_service()
        self.router = IntentRouter(self.embedding_service)
        self.formatter = ResponseFormatter()

    def generate_answer(self, question: str, empresa: int, ejercicio: int, threshold: float = 0.60, training_enabled: bool = False, model: str = None, request = None, profundizar: bool = False) -> dict:
        q_lower = question.lower()
        
        # --- 1. Parameter Extraction ---
        found_year = re.search(r'\b(20\d{2})\b', q_lower)
        if found_year:
            ejercicio = int(found_year.group(1))

        limit = 10
        top_match = re.search(r'(?:top|primeros|primeras|ultimos|últimos|mejores|peores)\s+(\d{1,3})\b', q_lower)
        if not top_match:
            top_match = re.search(r'\b(\d{1,3})\s+(?:mejores|peores|primeros|primeras|ultimos|últimos)\b', q_lower)
        if top_match:
            limit = int(top_match.group(1))
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 10

        # Call the AI Service
        
        # [NEW] Check Explicit Switch
        explicit_lang, is_supported = LanguageService.check_explicit_switch(question)
        
        # Heuristic detection (always needed for fallback or standard detection)
        detected_lang = LanguageService.detect(question)
        
        if explicit_lang:
            if is_supported:
                # User requested a supported language explicitly
                lang = explicit_lang
                # Return immediately to trigger reload in frontend
                msg = LanguageService.get_text('changing_language', lang, name=explicit_lang.upper())
                return {
                    "text": msg,
                    "sql": None,
                    "data": {},
                    "action": "RELOAD",
                    "lang": lang
                }
            else:
                # User requested an unsupported language
                # Requirement: Show error in "current active" language (or heuristics)
                # IMPROVEMENT: Try to show error in the REQUESTED language if we have a translation for it
                # get_text will fallback to ES if 'explicit_lang' translation is missing.
                error_msg = LanguageService.get_text('unavailable_error', explicit_lang)
                return {
                    "text": error_msg,
                    "sql": None,
                    "data": {},
                    "action": "NONE"
                }
        else:
            # Normal flow
            lang = detected_lang
            force_reload = False

        context = {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'limit': limit,
            'threshold': threshold,
            'lang': lang,
            'training_enabled': training_enabled,
            'model': model,
            'request': request
        }

        if profundizar:
            from datia.services.ai.profundizar import Profundizar
            detalle = Profundizar.responder(question, empresa, ejercicio)
            if isinstance(detalle, dict):
                detalle['query'] = question
                detalle['lang'] = lang
                return self._con_origen(detalle, empresa, ejercicio, question)

        # --- 2. Route Intent ---
        result = self._responder(question, context, lang, force_reload)
        if (result or {}).get('dato_no_cargado') or context.get('_ya_reintento') or _respuesta_tiene_valor(result):
            return self._con_origen(result, empresa, ejercicio, question)

        logger.info("IAService: la primera vía no dejó un resultado; el modelo escribe la consulta")
        context['training_enabled'] = True
        context['_ya_reintento'] = True
        context['_sql_descartada'] = (result or {}).get('sql')
        segundo = self._consulta_del_modelo(question, context, lang)
        if _respuesta_tiene_valor(segundo):
            segundo['reentrenado'] = True
            return self._con_origen(segundo, empresa, ejercicio, question)
        aviso = (
            "No he podido obtener un resultado para esta pregunta. "
            "Prueba nombrando el dato: ventas, compras, clientes, artículos, margen o coste."
        )
        return self._con_origen({
            "type": "text",
            "text": aviso,
            "answer": aviso,
            "sql": None,
            "query": question,
            "lang": lang,
            "reentrenado": True,
        }, empresa, ejercicio, question)

    def _con_origen(self, result, empresa, ejercicio, question):
        from datia.services.ai.presentacion import asegurar_origen
        if isinstance(result, dict) and not result.get('query'):
            result['query'] = question
        return asegurar_origen(result, empresa, ejercicio)

    def _responder(self, question, context, lang, force_reload):
        handler_class, intent_data = self.router.resolve(question, context)
        if not handler_class:
            custom_text = intent_data.get('text')
            default_text = LanguageService.get_text('unknown_intent', lang) if hasattr(LanguageService, 'get_text') else "No he entendido tu pregunta."
            respuesta = {
                "text": custom_text if custom_text else default_text,
                "sql": None,
                **intent_data,
            }
            respuesta['query'] = question
            respuesta['lang'] = lang
            return respuesta
        handler = handler_class(self.formatter)
        try:
            result = handler.handle(intent_data, context)
        except Exception as e:
            logger.error(f"Inference Error: {e}", exc_info=True)
            return {"text": f"Error al procesar tu solicitud: {str(e)}", "sql": "ERROR", "query": question, "lang": lang}
        if isinstance(result, dict):
            result['query'] = question
            result['lang'] = context['lang']
            if force_reload:
                result['action'] = 'RELOAD'
            return result
        return {"text": "No he podido preparar la respuesta.", "answer": "No he podido preparar la respuesta.", "sql": None, "query": question, "lang": lang}

    def _consulta_del_modelo(self, question, context, lang):
        """La primera vía no dejó datos. El modelo local escribe un SELECT y se acepta si hay filas o un texto."""
        from datia.services.ai.handlers.dynamic_handler import DynamicHandler
        from datia.services.ai.open_question import OpenQuestion
        abierto = OpenQuestion.responder(
            question,
            context.get('empresa'),
            context.get('ejercicio'),
            context.get('limit') or 10,
            forzar_modelo=True,
        )
        if not isinstance(abierto, dict):
            return None
        if abierto.get('reply'):
            reply = dict(abierto['reply'])
            reply['query'] = question
            reply['lang'] = lang
            return reply
        if abierto.get('error') or not abierto.get('sql'):
            return None
        try:
            result = DynamicHandler(self.formatter).handle(abierto, context)
        except Exception:
            logger.exception("IAService: la consulta del modelo no se pudo ejecutar")
            return None
        if isinstance(result, dict):
            result['query'] = question
            result['lang'] = lang
            return result
        return None

    def generate_strategic_report(self, empresa: int, ejercicio: int, kind: str = 'ventas', model: str = None, role: str = None) -> dict:
        import os
        import json
        from django.conf import settings
        req_id = f"{kind}-{empresa}-{ejercicio}"
        try:
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        except Exception:
            ctx_dir = settings.BASE_DIR
        report_path = os.path.join(str(ctx_dir), f'datia_ai_report_{kind}_{empresa}_{ejercicio}.html')
        data_context = None
        try:
            context_file = os.path.join(ctx_dir, f'datia_ai_context_{kind}_{empresa}_{ejercicio}.json')
            legacy_context_file = os.path.join(ctx_dir, f'datia_ai_context_{kind}.json')
            context_source = None

            # --- 0. ULTIMATE SPEED HACK: Return Pre-Generated Report if exists and recent (< 5 min) ---
            # DISABLED: This prevents JS-Only mode from working if a heavy report was cached before
            # if os.path.exists(report_path):
            #     try:
            #         mtime = os.path.getmtime(report_path)
            #         if time.time() - mtime < 600: # 10 minutes cache logic for report HTML
            #             logger.info(f"[AI] INSTANT LOAD: Returning pre-generated report from {report_path}")
            #             _progress(req_id, "CACHE_HTML", f"Usando HTML en disco {report_path}", 10)
            #             with open(report_path, 'r', encoding='utf-8') as f:
            #                 html_content = f.read()
            #             return {
            #                 "status": "success", 
            #                 "html": html_content, 
            #                 "type": "strategic_report",
            #                 "model_used": "cached_disk",
            #                 "context_source": "n/a",
            #                 "request_id": req_id
            #             }
            #     except Exception as e:
            #         logger.warning(f"[AI] Report Disk Read Failed: {e}")

            # --- 1. JSON PRIORITY: LOAD PRE-GENERATED CONTEXT IF EXISTS (no TTL) ---
            if os.path.exists(context_file):
                try:
                    with open(context_file, 'r', encoding='utf-8') as f:
                        data_context = json.load(f)
                    context_source = "disk"
                    _progress(req_id, "LECTURA_DISCO", f"{context_file}", 15)
                except Exception as e:
                    logger.warning(f"[AI] Context Read Failed ({context_file}): {e}")
            elif os.path.exists(legacy_context_file):
                # Backwards compatibility (legacy filename sin empresa/ejercicio)
                try:
                    with open(legacy_context_file, 'r', encoding='utf-8') as f:
                        data_context = json.load(f)
                    context_source = "disk-legacy"
                    _progress(req_id, "LECTURA_DISCO", f"{legacy_context_file}", 15)
                except Exception as e:
                    logger.warning(f"[AI] Context Read Failed (legacy {legacy_context_file}): {e}")
            if not data_context:
                _progress(req_id, "GENERANDO_CONTEXTO", "Datos no cacheados. Generando en tiempo real...", 18)
                try:
                    builder = None
                    if kind == 'financiera':
                         builder = FinancialContextBuilder()
                    
                    if builder:
                        # Force Fast Mode if Fallback requested (User wants speed)
                        use_fast = (bool(model) and str(model).lower() == 'fallback')
                        logger.info(f"[AI] Generating Context ON-THE-FLY (FastMode={use_fast})...")
                        
                        if kind == 'financiera':
                             data_context = builder.build_context(empresa, ejercicio, fast_mode=use_fast)
                        else:
                             data_context = builder.build_context(empresa, ejercicio)
                        
                        context_source = "generated_fly"
                    else:
                        # Fallback for other kinds or if builder fails
                         _progress(req_id, "NO_CONTEXT", f"{context_file}", 20)
                         return {
                            "status": "no_context",
                            "message": f"Falta contexto JSON en disco para '{kind}' y no hay generador automático.",
                            "context_source": "missing"
                        }
                except Exception as e:
                    logger.error(f"[AI] Auto-Gen Failed: {e}")
                    return {"status": "error", "message": f"Error generando contexto: {e}"}

            if kind not in ['ventas', 'financiera']:
                 # Tolerate unknown kinds if we have data (generic mode)
                 pass
                
            logger.info(f"[AI] Starting LLM Generation... {time.ctime()}")
            _progress(req_id, "LLM_INICIO", "Preparando prompt", 50)
                
            # 2. Select Prompt Template based on kind
            if kind == 'financiera':
                json_str = json.dumps(data_context, ensure_ascii=False, indent=2)
                base_prompt = f"""
                Eres un Director Financiero (CFO) con 20 años de experiencia.
                Tu objetivo es analizar datos crudos en formato JSON y extraer 'insights' estratégicos.
                Al elaborar tus informes:
                1. Prioriza la rentabilidad, el flujo de caja y los indicadores clave (KPIs).
                2. No te limites a describir los números; explica el PORQUÉ de las variaciones.
                3. Identifica riesgos financieros potenciales.
                4. Usa un tono ejecutivo, directo y profesional.
                5. Estructura el informe en: Resumen Ejecutivo, Análisis de Variaciones y Recomendaciones Estratégicas.
                
                DATOS (JSON):
                {json_str}
                
                REGLAS:
                - Usa solo HTML (div, h3, p, ul, li, b). Sin Markdown.
                - Devuelve exactamente las tres secciones indicadas con etiquetas HTML y cifras clave.
                """
            else:
                # Default Sales Prompt
                json_str = json.dumps(data_context, ensure_ascii=False, indent=2)
                base_prompt = f"""
                Actúa como Director Comercial. Analiza las ventas del ejercicio {ejercicio}.
                DATOS: {json_str}
                Structure: 1. Resumen, 2. Hallazgos, 3. Recomendaciones. HTML format.
                """
            
            # Lazy init to prevent blocking if fallback requested
            ollama = None
            force_fallback = bool(model) and str(model).lower() == 'fallback'
            
            available_models = []
            if not force_fallback:
                try:
                    ollama = OllamaService()
                    available_models = ollama.list_models()
                    _progress(req_id, "MODELOS_OLLAMA", f"Disponibles={len(available_models)}", 55)
                except Exception as e:
                    logger.warning(f"Ollama list_models failed: {e}")
            
            selected_model = None
            
            selected_model = None
            
            selected_model = None
            
            if model and not force_fallback:
                 target = None
                 for m in available_models:
                     if m.lower() == model.lower(): target = m; break
                 if not target:
                     for m in available_models:
                         if model.lower() in m.lower(): target = m; break
                 selected_model = target
                 _progress(req_id, "SELECCION_MODELO", f"Solicitado='{model}' → '{selected_model or 'no-match'}'", 60)
            
            if not force_fallback and not selected_model:
                # Centralized selector in OllamaService
                selected_model = OllamaService.select_preferred_model(kind, available_models)
                _progress(req_id, "SELECCION_MODELO", f"Prioridad → '{selected_model or 'fallback'}'", 65)
            
            prompt = f"{base_prompt}\n\nCrea el informe usando el modelo: {selected_model}"
            
            logger.info(f"Using Model: {selected_model or 'fallback'} for report kind '{kind}'")
            try:
                ollama = OllamaService()
                res = ollama.generate_text_with_policy(prompt, kind, requested_model=model, force_fallback=force_fallback, deadline=120)
                if res.get("status") == "ok":
                    report_html = res.get("text", "")
                    used_model = res.get("model") or "unknown"
                    _progress(req_id, "OLLAMA_DONE", f"Modelo='{used_model}'", 85)
                else:
                    fallback_html = (self._build_fallback_financial_report_html if kind == 'financiera' else self._build_fallback_sales_report_html)(data_context, ejercicio)
                    report_html = fallback_html
                    used_model = "fallback"
                    _progress(req_id, "FALLBACK_ACTIVADO", "Sin modelo disponible o error", 75)
                    
                # [LOG RESULT] Save generated report to disk
                try:
                    with open(report_path, 'w', encoding='utf-8') as f:
                        f.write(report_html)
                    logger.info(f"[AI] Saved report result to {report_path}")
                    _progress(req_id, "GUARDADO_HTML", report_path, 95)
                except: pass
                    
            except requests.exceptions.Timeout:
                logger.error("Ollama Timeout generating report")
                fallback_html = (self._build_fallback_financial_report_html if kind == 'financiera' else self._build_fallback_sales_report_html)(data_context, ejercicio)
                report_html = fallback_html
                used_model = "fallback"
                _progress(req_id, "OLLAMA_TIMEOUT", "requests.Timeout", 75)
            
            # [FIX] Prepare Common Response Structure (KPIs + Charts)
            kpis_data = data_context.get("kpis_globales") or data_context.get("kpis", {})
            frontend_kpis = []
            
            if kind == 'financiera':
                frontend_kpis = [
                    {'label': 'Ventas', 'value': f"{kpis_data.get('ventas', 0):,.0f}€", 'color': 'blue'},
                    {'label': 'EBITDA', 'value': f"{kpis_data.get('ebitda', 0):,.0f}€", 'color': 'green'},
                    {'label': 'Margen %', 'value': f"{kpis_data.get('margen_op_pct', 0):.1f}%", 'color': 'orange'},
                ]
            else:
                frontend_kpis = [
                    {'label': 'Ventas Totales', 'value': f"{kpis_data.get('ventas_totales', 0):,.0f}€", 'color': 'blue'},
                    {'label': 'Margen %', 'value': f"{kpis_data.get('margen_beneficio_pct', 0):.1f}%", 'color': 'green'},
                    {'label': 'Operaciones', 'value': str(kpis_data.get('total_operaciones', 0)), 'color': 'purple'},
                ]

            _progress(req_id, "COMPLETADO", "Informe listo", 100)
            return {
                "status": "success", 
                "type": "report", 
                "answer": report_html, 
                "html": report_html,
                "raw_data": data_context,
                "kpis": frontend_kpis, 
                "model_used": used_model,
                "context_source": context_source or "unknown",
                "request_id": req_id
            }
            
        except Exception as e:
            try:
                fallback_html = (self._build_fallback_financial_report_html if kind == 'financiera' else self._build_fallback_sales_report_html)(data_context, ejercicio)
                # Fallback KPIs
                kb = data_context.get("kpis_globales") or data_context.get("kpis", {})
                fb_kpis = [
                     {'label': 'Ventas/Ingresos', 'value': f"{kb.get('ventas', kb.get('ventas_totales', 0)):,.0f}€", 'color': 'gray'}
                ]
                _progress("unknown", "ERROR", str(e))
                return {
                    "status": "success",
                    "type": "report", 
                    "answer": fallback_html, 
                    "html": fallback_html,
                    "raw_data": data_context,
                    "kpis": fb_kpis, 
                    "model_used": "fallback",
                    "context_source": "unknown",
                    "request_id": None
                }
            except Exception as ex:
                logger.error(f"Report Generation Error: {e}", exc_info=True)
                return {"status": "error", "message": str(ex)}

    def _build_fallback_financial_report_html(self, data_context: dict, ejercicio: int) -> str:
        """
        Generates a Rule-Based Report matching the STRICT Controller Persona requested by User.
        """
        kpis = data_context.get("kpis_globales") or data_context.get("kpis", {})
        
        # Extract Variables
        ventas = kpis.get("ventas") or kpis.get("ventas_totales") or 0
        gastos = kpis.get("gastos") or 0
        ebitda = kpis.get("ebitda") or kpis.get("resultado") or (ventas - gastos)
        margen = kpis.get("margen_op_pct") or kpis.get("margen_beneficio_pct") or 0
        
        balance_ratios = data_context.get("balance_situacion", {}).get("ratios", {})
        liquidez = balance_ratios.get("liquidez", 0)
        solvencia = balance_ratios.get("solvencia", 0)
        endeuda = balance_ratios.get("endeudamiento_pct", 0)
        
        fmt = lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # 1. Executive Summary Logic
        if margen < 0:
            status_title = "El Desafío de la Rentabilidad"
            status_desc = "A nivel global, la empresa presenta una <b>situación operativa deficitaria</b>. La estructura de costes absorbe la totalidad de los ingresos."
            diag = "Existe un <b>desajuste estructural</b>. Se destruye valor con cada operación."
        elif margen < 5:
            status_title = "Rentabilidad Ajustada"
            status_desc = "La empresa es solvente pero opera con márgenes muy estrechos, lo que aumenta el riesgo ante imprevistos."
            diag = "Es necesario revisar la eficiencia operativa para mejorar el margen de seguridad."
        else:
            status_title = "Solidez Operativa"
            status_desc = "La empresa muestra una cuenta de resultados saneada con un margen operativo saludable."
            diag = "La gestión es eficiente y genera valor sostenible."

        resumen_html = f"""
        <div class="ai-report-section">
            <h3>1. Resumen Ejecutivo: {status_title}</h3>
            <p>{status_desc}</p>
            <p>
               Ingresos: <b>{fmt(ventas)} €</b><br>
               EBITDA: <b>{fmt(ebitda)} €</b> (Margen: {margen:.2f}%)
            </p>
            <p><b>Diagnóstico:</b> {diag}</p>
        </div>
        """
        
        # 2. Monthly/Quarterly Analysis (Dynamic)
        analysis_html = ""
        try:
             quarterly = data_context.get("quarterly", {})
             q_curr = quarterly.get("curr", [])
             
             if q_curr and any(q_curr):
                 best_q = q_curr.index(max(q_curr)) + 1
                 worst_q = q_curr.index(min(q_curr)) + 1
                 q1_val = q_curr[0]
                 q4_val = q_curr[3] if len(q_curr) > 3 else 0
                 
                 trend_txt = "una tendencia decreciente" if q4_val < q1_val else "una recuperación progresiva"
                 
                 analysis_html = f"""
                <div class="ai-report-section">
                    <h3>2. Análisis Mensual: Volatilidad y Estacionalidad</h3>
                    <p>El comportamiento anual muestra <b>{trend_txt}</b> hacia el cierre del ejercicio.</p>
                    <ul>
                        <li><b>Pico de Actividad:</b> El <b>Q{best_q}</b> concentra el mayor volumen de negocio.</li>
                        <li><b>Periodo Crítico:</b> El Q{worst_q} registra los menores ingresos, sugiriendo estacionalidad inversa o caída de demanda.</li>
                    </ul>
                </div>
                """
             else:
                 # Fallback if no quarterly data
                 analysis_html = f"""
                <div class="ai-report-section">
                    <h3>2. Análisis Mensual: Volatilidad y Estacionalidad</h3>
                    <p>No se detectan patrones estacionales significativos en los datos agregados. Se recomienda revisar el detalle mensual en el cuadro de mandos.</p>
                </div>
                """
        except:
             analysis_html = f"""
            <div class="ai-report-section">
                <h3>2. Análisis Mensual: Volatilidad y Estacionalidad</h3>
                <p>Datos no disponibles para análisis de estacionalidad.</p>
            </div>
            """
        
        # 3. Ratios Logic
        liq_interp = "Excesiva (Dinero ocioso)" if liquidez > 2 else ("Adecuada" if liquidez > 1 else "Tensión de Liquidez")
        solv_interp = "Muy Alta (Gran Solidez)" if solvencia > 2 else "Equilibrada"
        
        ratios_html = f"""
        <div class="ai-report-section">
            <h3>3. Ratios Clave y Salud Financiera</h3>
            <ul>
                <li><b>Liquidez ({liquidez:.2f}):</b> {liq_interp}. Capacidad inmediata de pago.</li>
                <li><b>Solvencia ({solvencia:.2f}):</b> {solv_interp}. Garantía frente a acreedores.</li>
                <li><b>Endeudamiento ({endeuda:.2f}%):</b> Estructura de capital actual.</li>
            </ul>
        </div>
        """
        
        # 4. Recommendations (Dynamic)
        rec_list = ""
        if margen < 0:
            rec_list += "<li><b>Plan de Choque (Cost Cutting):</b> Reducción inmediata de gastos operativos (15%) para alcanzar break-even.</li>"
        if liquidez > 2:
            rec_list += "<li><b>Optimización de Tesorería:</b> Reinvertir el excedente de caja (Ratio > 2) en activos productivos.</li>"
        if endeuda < 30:
            rec_list += "<li><b>Apalancamiento Operativo:</b> Capacidad para financiar expansión mediante deuda barata.</li>"
        
        if not rec_list:
             rec_list = "<li><b>Consolidación:</b> Mantener la estrategia actual vigilando de cerca el margen bruto.</li>"

        rec_html = f"""
        <div class="ai-report-section">
            <h3>4. Conclusiones y Recomendaciones</h3>
            <p>Acciones Propuestas:</p>
            <ul>
                {rec_list}
            </ul>
        </div>
        """
        
        return resumen_html + analysis_html + ratios_html + rec_html


    def _build_fallback_sales_report_html(self, data_context: dict, ejercicio: int) -> str:
        kpis = data_context.get("kpis", {})
        resumen_total = kpis.get("ventas_totales", 0)
        margen_pct = kpis.get("margen_beneficio_pct", 0)
        crecimiento = kpis.get("crecimiento_anual_pct", 0)
        operaciones = kpis.get("total_operaciones", 0)
        top_clientes = data_context.get("top_clientes", [])[:3]
        top_productos = data_context.get("top_productos", [])[:3]
        evolucion = data_context.get("evolucion_mensual", [])[-6:]
        ticket = data_context.get("ticket_mensual", [])[-6:]
        clientes_mes = data_context.get("clientes_mes", [])[:3]
        geografia = data_context.get("geografia", [])[:5]
        pareto = data_context.get("pareto", {})
        estacionalidad = data_context.get("estacionalidad", [])[-6:]
        alertas = data_context.get("alertas", [])
        resumen_texto = "Ventas estables" if abs(crecimiento) < 1 else ("Expansión" if crecimiento > 0 else "Contracción")
        clientes_html = "".join([f"<li>{c.get('nombre','Cliente')} — {float(c.get('volumen_compras',0)):.2f} €</li>" for c in top_clientes])
        productos_html = "".join([f"<li>{p.get('nombre','Producto')} — {float(p.get('ingresos_generados',0)):.2f} €</li>" for p in top_productos])
        evo_html = "".join([f"<li>Mes {e.get('mes')} — Ventas {float(e.get('ventas',0)):.2f} €</li>" for e in evolucion])
        ticket_html = "".join([f"<li>Mes {t.get('mes')} — Ticket {float(t.get('ticket',0)):.2f} €</li>" for t in ticket])
        clientes_mes_html_items = []
        for cm in clientes_mes:
            series = cm.get("series", [])[-6:]
            series_html = "".join([f"<li>Mes {s.get('mes')} — {float(s.get('ventas',0)):.2f} €</li>" for s in series])
            clientes_mes_html_items.append(f"<li>{cm.get('nombre','Cliente')}</li><ul>{series_html}</ul>")
        clientes_mes_html = "".join(clientes_mes_html_items)
        geo_html = "".join([f"<li>CP {g.get('cod_postal','')} — {float(g.get('ventas',0)):.2f} €</li>" for g in geografia])
        pareto_html = f"<li>Concentración Top {pareto.get('top_n',0)}: {float(pareto.get('top_share_pct',0)):.2f}% del total</li>" if pareto else ""
        est_html = "".join([f"<li>Mes {e.get('mes')} — Participación {float(e.get('share_pct',0)):.2f}% — YoY {float(e.get('yoy_pct',0)):.2f}%</li>" for e in estacionalidad])
        alertas_html = "".join([f"<li>{a}</li>" for a in alertas])
        return (
            f"<div class=\"ai-report-section\">"
            f"<h3>📊 Resumen Ejecutivo</h3>"
            f"<p>Ejercicio {ejercicio}. {resumen_texto}. Ventas totales {resumen_total:.2f} €, margen {margen_pct:.2f}%, crecimiento {crecimiento:.2f}%, operaciones {operaciones}.</p>"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>🔍 Hallazgos Clave</h3>"
            f"<ul>{clientes_html}{productos_html}{evo_html}{pareto_html}</ul>"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>🧾 Ticket Medio</h3>"
            f"<ul>{ticket_html}</ul>"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>👥 Clientes Clave (últimos meses)</h3>"
            f"{clientes_mes_html}"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>🗺️ Geografía</h3>"
            f"<ul>{geo_html}</ul>"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>📅 Estacionalidad</h3>"
            f"<ul>{est_html}</ul>"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>🚨 Alertas Relevantes</h3>"
            f"<ul>{alertas_html}</ul>"
            f"</div>"
            f"<div class=\"ai-report-section\">"
            f"<h3>🚀 Recomendaciones Estratégicas</h3>"
            f"<p>Consolidar cartera en clientes de mayor contribución y revisar costes para elevar el margen. Intensificar acciones en meses de menor rendimiento.</p>"
            f"</div>"
        )

    def generate_context(self, empresa: int, ejercicio: int, kind: str = 'ventas') -> dict:
        import os
        import json
        from django.conf import settings
        try:
            ctx_dir = getattr(settings, 'DATIA_AI_CONTEXT_DIR', settings.BASE_DIR)
        except Exception:
            ctx_dir = settings.BASE_DIR
        # Use per-empresa/ejercicio filename to evitar lecturas equivocadas
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
