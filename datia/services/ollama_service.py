import requests
import json
import logging
import os

logger = logging.getLogger('datia')

from datia.services.system_monitor import SystemMonitorService

class OllamaService:
    """
    Service to interact with local Ollama instance (default port 11434).
    Enhanced with System Monitoring integration.
    """
    
    def __init__(self, base_url=None, model="qwen2.5:3b-instruct-q4_k_m"):
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model
        
    # Warm-up registry for heavy models
    WARMED_MODELS = {}
    
    @staticmethod
    def _is_warmed(model: str) -> bool:
        try:
            import time as _t
            last = OllamaService.WARMED_MODELS.get(model)
            return bool(last) and (_t.time() - last < 14 * 60)
        except Exception:
            return False
    
    @staticmethod
    def _mark_warmed(model: str):
        try:
            import time as _t
            OllamaService.WARMED_MODELS[model] = _t.time()
        except Exception:
            pass
        
    def _get_adaptive_timeout(self) -> int:
        """
        Gets dynamic timeout based on system health.
        """
        try:
            metrics = SystemMonitorService.get_system_metrics()
            # Try to load preset from config file if possible, else default to auto
            # Since SystemMonitorService.get_adaptive_config is self-contained:
            # We need to read the preset file.
            # But let's keep it simple and assume 'auto' if we can't easily reach the file from here without circular imports or file I/O overhead.
            # Actually, `datia.api.system_endpoints` has `load_config`. We can duplicate logic or import if clean.
            # Let's just use SystemMonitorService logic directly.
            
            # Helper to read preset safely
            import os
            import json
            from django.conf import settings
            CONFIG_FILE = os.path.join(settings.BASE_DIR, 'datia', 'config', 'system_perf.json')
            preset = 'auto'
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    preset = json.load(f).get('preset', 'auto')
            
            config = SystemMonitorService.get_adaptive_config(metrics, preset)
            return config.get('timeout', 30)
        except Exception as e:
            logger.warning(f"Failed to get adaptive timeout: {e}")
            return 30 # Default safe fallback

    def check_connection(self) -> bool:
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return res.status_code == 200
        except:
            return False

    def generate_text(self, prompt: str, timeout: int = None, model: str = None, options: dict = None, req_id: str = None, stream: bool = True) -> str:
        """
        Generic text generation.
        """
        target_model = model or self.model
        import time as _t
        if req_id:
            try:
                from datia.services.dashboard_service import AI_PROGRESS
                AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "OLLAMA_START", "message": f"model={target_model}", "percent": 40})
            except Exception:
                pass
        if not self.check_connection():
            raise Exception("OLLAMA_OFFLINE")
        
        effective_timeout = timeout if timeout is not None else self._get_adaptive_timeout()
             
        try:
            logger.info(f"⚡ Ollama Generating Text model='{target_model}' (Timeout={effective_timeout}s)...")
            payload = {
                "model": target_model,
                "prompt": prompt,
                "stream": bool(stream),
                "keep_alive": "15m"
            }
            if options:
                payload["options"] = options
            
            res = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=(5, effective_timeout),
                stream=bool(stream)
            )
            
            if res.status_code == 200:
                start = _t.time()
                if bool(stream):
                    text = ""
                    chunks = 0
                    last_log = start
                    for line in res.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            piece = obj.get("response") or ""
                            if piece:
                                text += piece
                                chunks += 1
                            now = _t.time()
                            if now - last_log >= 2:
                                last_log = now
                                try:
                                    logger.info(f"⚙️ Ollama Stream model='{target_model}' chunks={chunks} chars={len(text)} elapsed={int(now - start)}s")
                                    if req_id:
                                        try:
                                            from datia.services.dashboard_service import AI_PROGRESS
                                            AI_PROGRESS.setdefault(req_id, []).append({"ts": now, "step": "OLLAMA_STREAM", "message": f"chunks={chunks} chars={len(text)} elapsed={int(now - start)}s"})
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                            if obj.get("done"):
                                break
                        except Exception:
                            continue
                    try:
                        logger.info(f"✅ Ollama Done model='{target_model}' chunks={chunks} chars={len(text)} elapsed={int(_t.time() - start)}s")
                        if req_id:
                            try:
                                from datia.services.dashboard_service import AI_PROGRESS
                                AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "OLLAMA_DONE", "message": f"model={target_model} chunks={chunks} chars={len(text)} elapsed={int(_t.time() - start)}s", "percent": 90})
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return text
                else:
                    try:
                        body = res.json()
                    except Exception:
                        body = {}
                    text = body.get("response") or ""
                    try:
                        logger.info(f"✅ Ollama Done (no-stream) model='{target_model}' chars={len(text)} elapsed={int(_t.time() - start)}s")
                        if req_id:
                            try:
                                from datia.services.dashboard_service import AI_PROGRESS
                                AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "OLLAMA_DONE", "message": f"model={target_model} chars={len(text)} elapsed={int(_t.time() - start)}s", "percent": 90})
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return text
            else:
                raise Exception(f"Ollama Error {res.status_code}: {res.text}")
                
        except Exception as e:
            logger.error(f"Ollama Generation Error: {e}")
            if req_id:
                try:
                    from datia.services.dashboard_service import AI_PROGRESS
                    AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "OLLAMA_ERROR", "message": str(e)})
                except Exception:
                    pass
            raise e

    def generate_text_with_policy(self, prompt: str, kind: str, requested_model: str = None, force_fallback: bool = False, deadline: int = 120, req_id: str = None, prefer_no_stream: bool = False, allow_degrade: bool = False) -> dict:
        """
        Unified generation with selection, timeouts and quick retry.
        Returns dict: {'status': 'ok', 'text': str, 'model': str} or {'status': 'fallback'} or {'status': 'err', 'error': str}
        """
        try:
            if force_fallback:
                return {"status": "fallback", "reason": "forced"}
            
            if not self.check_connection():
                return {"status": "fallback", "reason": "offline"}
            
            models = self.list_models()
            selected = OllamaService.select_preferred_model(kind, models, requested_model, force_fallback=False)
            if not selected and requested_model:
                return {"status": "fallback", "reason": "requested_model_unavailable"}
            if not selected:
                return {"status": "fallback", "reason": "no_model_selected"}
            user_forced = requested_model is not None
            
            import time as _t
            start = _t.time()
            timeout = 60
            if 'qwen3:72b' in selected:
                timeout = 1500
            elif 'qwen3:30b' in selected:
                timeout = 720
            elif 'qwen3' in selected:
                timeout = 600
            elif 'qwen2.5:14b' in selected:
                timeout = 300
            elif 'mistral' in selected:
                timeout = 90
            elif 'qwen2.5:7b' in selected or 'deepseek' in selected:
                timeout = 480
            elif 'qwen' in selected:
                timeout = 75
            elif 'llama3' in selected:
                timeout = 180
            
            allowed_total = min(max(deadline, 480), 1800)
            remaining = allowed_total - int(_t.time() - start)
            
            opt = None
            try:
                if 'qwen3' in selected or 'qwen2.5:14b' in selected:
                    opt = {"num_predict": 512, "temperature": 0.2, "top_p": 0.95, "num_ctx": 8192}
                elif 'qwen2.5:7b' in selected:
                    opt = {"num_predict": 256, "temperature": 0.2, "top_p": 0.95, "num_ctx": 4096}
                else:
                    opt = {"num_predict": 384, "temperature": 0.2, "top_p": 0.95, "num_ctx": 4096}
            except Exception:
                opt = None
            
            # Warm-up to avoid cold start (heavy or first-time models)
            try:
                if (('qwen3' in selected) or ('qwen2.5:7b' in selected)) and (not OllamaService._is_warmed(selected)) and (remaining > 20):
                    warm_budget = min(90, max(15, int(allowed_total * 0.10)))
                    if req_id:
                        try:
                            from datia.services.dashboard_service import AI_PROGRESS
                            AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "WARMUP_START", "message": f"model={selected} budget={warm_budget}s"})
                        except Exception:
                            pass
                    _ = self.generate_text(
                        prompt="OK",
                        timeout=warm_budget,
                        model=selected,
                        options={"num_predict": 8, "temperature": 0, "top_p": 0.9},
                        req_id=req_id
                    )
                    OllamaService._mark_warmed(selected)
                    if req_id:
                        try:
                            from datia.services.dashboard_service import AI_PROGRESS
                            AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "WARMUP_DONE", "message": f"model={selected}"})
                        except Exception:
                            pass
            except Exception:
                # Ignore warm-up failures and proceed
                pass
            
            remaining = allowed_total - int(_t.time() - start)
            eff_timeout = max(5, min(timeout, remaining - 5)) if remaining > 0 else 5
            if req_id:
                try:
                    from datia.services.dashboard_service import AI_PROGRESS
                    AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "OLLAMA_ATTEMPT", "message": f"model={selected} timeout={eff_timeout}s"})
                except Exception:
                    pass
            try:
                txt = self.generate_text(prompt, timeout=eff_timeout, model=selected, options=opt, req_id=req_id, stream=(not prefer_no_stream))
                if txt:
                    return {"status": "ok", "text": txt, "model": selected}
            except Exception as e:
                last_err = str(e)
                try:
                    remaining = allowed_total - int(_t.time() - start)
                    if remaining > 60:
                        retry_timeout = max(5, min(timeout, remaining - 5))
                        retry_opt = {"num_predict": 256, "temperature": 0.2, "top_p": 0.95}
                        if 'qwen3' in selected or 'qwen2.5:14b' in selected:
                            retry_opt["num_ctx"] = 8192
                        else:
                            retry_opt["num_ctx"] = 4096
                        txt_retry = self.generate_text(prompt, timeout=retry_timeout, model=selected, options=retry_opt, req_id=req_id, stream=(not prefer_no_stream))
                        if txt_retry:
                            return {"status": "ok", "text": txt_retry, "model": selected}
                except Exception as e_retry:
                    last_err = f"{last_err} | RETRY: {str(e_retry)}"
            
            # No alternates when el usuario ha seleccionado un modelo explícito
            if not user_forced or allow_degrade:
                alt = None
                candidates = ['qwen2.5:3b-instruct-q4_k_m', 'qwen2.5:3b', 'mistral:latest', 'mistral']
                for c in candidates:
                    for m in models:
                        if m == c and m != selected:
                            alt = m
                            break
                    if alt:
                        break
                if alt:
                    remaining = allowed_total - int(_t.time() - start)
                    alt_timeout = max(5, min(120, remaining - 5)) if remaining > 0 else 5
                    try:
                        opt_alt = {"num_predict": 256, "temperature": 0.2, "top_p": 0.95}
                        txt2 = self.generate_text(prompt, timeout=alt_timeout, model=alt, options=opt_alt, req_id=req_id, stream=(not prefer_no_stream))
                        if txt2:
                            return {"status": "ok", "text": txt2, "model": alt}
                    except Exception as e2:
                        return {"status": "fallback", "reason": "alt_generation_error"}
            reason = "generation_failed"
            try:
                if 'Read timed out' in (last_err or ''):
                    reason = "cold_start_timeout"
                if remaining <= 0:
                    reason = "polling_window_exceeded"
                if user_forced and reason == "generation_failed":
                    reason = "selected_model_failed"
            except Exception:
                reason = "generation_failed"
            if req_id:
                try:
                    from datia.services.dashboard_service import AI_PROGRESS
                    AI_PROGRESS.setdefault(req_id, []).append({"ts": _t.time(), "step": "FALLBACK", "message": reason})
                except Exception:
                    pass
            return {"status": "fallback", "reason": reason}
        except Exception as e:
            return {"status": "err", "error": str(e)}


    def list_models(self) -> list:
        """
        Returns a list of available model names.
        """
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if res.status_code == 200:
                data = res.json()
                # Extract 'name' from 'models' list
                # format: {"models": [{"name": "mistral:latest", ...}, ...]}
                return [m['name'] for m in data.get('models', [])]
            return []
        except Exception as e:
            try:
                # IA local es opcional; si Ollama no está disponible, no debe contaminar logs
                logger.warning(f"Ollama list_models unavailable: {e}")
            except Exception:
                pass
            return []

    @staticmethod
    def select_preferred_model(kind: str, available_models: list, requested_model: str = None, force_fallback: bool = False) -> str:
        """
        Centralized model selection logic.
        - kind: 'financiera' or 'ventas' (others default to speed-first)
        - available_models: list returned by list_models()
        - requested_model: optional user-specified model (exact or substring match)
        - force_fallback: if True, returns None to trigger fallback
        """
        try:
            if force_fallback:
                return None
            
            # 1) Honor requested model if present
            if requested_model:
                target = None
                for m in available_models:
                    if m.lower() == requested_model.lower():
                        target = m
                        break
                if not target:
                    for m in available_models:
                        if requested_model.lower() in m.lower():
                            target = m
                            break
                if target:
                    return target
            
            # 2) Priorities by kind
            priorities_map = {
                'financiera': ['qwen2.5:14b', 'qwen2.5:14b-instruct', 'qwen3:72b', 'qwen3:30b', 'qwen2.5:7b', 'deepseek', 'qwen2.5:3b', 'mistral', 'llama3'],
                'ventas': ['qwen2.5:3b', 'qwen3:30b', 'mistral', 'llama3', 'gemma', 'qwen'],
                '_default': ['qwen2.5:3b', 'qwen3:30b', 'mistral', 'llama3', 'gemma', 'qwen']
            }
            priorities = priorities_map.get(kind, priorities_map['_default'])
            
            for p in priorities:
                for m in available_models:
                    if p in m:
                        return m
            
            # 3) Fallback: first available
            return available_models[0] if available_models else None
        except Exception as e:
            logger.warning(f"Model selection error: {e}")
            return available_models[0] if available_models else None

    def generate_field_descriptions(self, table_name: str, fields: list, context: str = "", business_context: str = "", model: str = None) -> dict:
        """
        Generates business descriptions for a list of table fields.
        Returns a dict: {field_name: "description"}
        """
        target_model = model or self.model
        
        # optimized prompt for bulk generation to save round-trips
        # fields is now a list of dicts: {'id': '...', 'label': '...', 'type': '...'}
        
        items_str = json.dumps([{ 'id': f['id'], 'label': f['label'] } for f in fields], indent=None)
        
        context_str = f"Context about this table: {context}" if context else ""
        biz_context_str = f"Context about the COMPANY: {business_context}" if business_context else ""

        prompt = f"""
        Act as a Data Analyst expert in ERP systems.
        I have a database table named '{table_name}'.
        {biz_context_str}
        {context_str}
        
        Analyze the provided 'label' for each field and provide a short, business-friendly description in Spanish.
        
        Input Fields: {items_str}
        
        Output STRICTLY valid JSON format where the KEY is the 'id' of the field, and the VALUE is the specific description.
        
        Rules:
        1. Return ONLY the JSON object. No markdown, no code blocks, no intro text.
        2. The keys in the JSON must MATCH EXACTLY the 'id' from the input.
        3. Do NOT change the casing of the keys.
        
        Example Output:
        {{
            "FIELD_ID_1": "Description for field 1",
            "FIELD_ID_2": "Description for field 2"
        }}
        """
        
        try:
            import time
            start_time = time.time()
            
            logger.info(f"⚡ Ollama Generando Semántica para '{table_name}' usando modelo '{target_model}'...")
            logger.info(f"📊 Generando descripciones para {len(fields)} campos")
            
            payload = {
                "model": target_model,
                "prompt": prompt,
                "stream": False,
                "format": "json" # Force JSON mode if supported by model version
            }
            
            # Reduced timeout from 300s to 90s to prevent blocking
            res = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=90)
            
            elapsed = time.time() - start_time
            logger.info(f"⏱️ Respuesta recibida en {elapsed:.2f} segundos ({elapsed/len(fields):.2f}s por campo)")
            
            if res.status_code == 200:
                body = res.json()
                response_text = body.get('response', '{}')
                
                # Cleanup potential Markdown
                clean_json = response_text.replace("```json", "").replace("```", "").strip()
                
                try:
                    result = json.loads(clean_json)
                    logger.info(f"✅ Generación exitosa: {len(result)} descripciones")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Ollama JSON Error: {clean_json}")
                    # Return raw text for debugging
                    return {"_error": f"JSON Decode Error: {e}", "_raw": clean_json}
            else:
                logger.error(f"Ollama Error {res.status_code}: {res.text}")
                return {"_error": f"Ollama Status {res.status_code}", "_raw": res.text}
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout after 60s generating for {table_name}. Model may be too large. Try a smaller model like 'gemma2:2b'")
            return {"_error": "Timeout after 60s. Try a smaller/faster model", "_suggestion": "Use gemma2:2b or llama3:8b"}
        except Exception as e:
            logger.error(f"Ollama Connection Error: {e}")
            return {"_error": f"Exception: {e}"}

    def generate_sql_query(self, question: str, schema_context: str) -> str:
        """
        Generates a SQL query based on the question and schema.
        Handles offline mode gracefully.
        """
        if not self.check_connection():
            return "-- OLLAMA_OFFLINE"
            
        prompt = f"""
        Act as a Postgres SQL Expert.
        
        Question: {question}
        
        Database Schema:
        {schema_context}
        
        Rules:
        1. Return ONLY the raw SQL query. No markdown, no explanation.
        2. Use the provided tables and columns.
        3. Ensure the SQL is valid Postgres.
        
        SQL:
        """
        
        try:
            logger.info(f"⚡ Ollama Generando SQL para pregunta usando modelo '{self.model}'...")
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            res = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=45)
            
            if res.status_code == 200:
                body = res.json()
                response_text = body.get('response', '')
                clean_sql = response_text.replace("```sql", "").replace("```", "").strip()
                return clean_sql
            else:
                 return f"-- ERROR: Ollama returned {res.status_code}"
                 
        except Exception as e:
            logger.error(f"Ollama SQL Generation Error: {e}")
            return f"-- ERROR: {str(e)}"

    def generate_data_analysis(self, question: str, data_summary: list, context: dict) -> str:
        """
        Generates a business analysis report based on data rows.
        """
        if not self.check_connection():
            return "<i>(Análisis no disponible: IA desconectada)</i>"
            
        # Prepare data summary for LLM
        if isinstance(data_summary, list):
            max_rows = 15
            data_text = json.dumps(data_summary[:max_rows], default=str, indent=2)
            if len(data_summary) > max_rows:
                data_text += f"\n... ({len(data_summary) - max_rows} more rows)"
        else:
            # Assume Dict is already summarizing
            data_text = json.dumps(data_summary, default=str, indent=2)

        empresa = context.get('empresa', 'Unknown')
        ejercicio = context.get('ejercicio', 'Current')
        
        prompt = f"""
        Act as a Senior Business Intelligence Analyst for Company {empresa}.
        
        USER QUESTION: "{question}"
        CONTEXT: Financial Year {ejercicio}
        
        DATA RETRIEVED (JSON):
        {data_text}
        
        TASK:
        Write a concise Executive Summary (in Spanish) analyzing this data.
        
        STRUCTURE:
        1. **Resumen**: 1-2 sentences summarizing the main finding.
        2. **Tendencias**: Analyze growth, decline, or seasonality. Compare with previous year if data (val_prev/neto_prev) is available.
        3. **Conclusión**: 1 actionable recommendation or business insight.
        
        RULES:
        - Use HTML formatting: <b>bold</b> for key numbers, <br> for line breaks.
        - Be professional, direct, and analytical. 
        - Highlight "Ticket Medio" or "Margins" if they appear anomalous (e.g. 0 or negative).
        - Do not mention "JSON" or "SQL". Talk about Sales, Clients, Products.
        - If data suggests a negative trend, use a warning tone.
        
        OUTPUT (Markdown/HTML):
        """
        
        try:
            return self.generate_text(prompt, timeout=60)
        except Exception as e:
            logger.error(f"Analysis Generation Error: {e}")
            return "<i>(No se pudo generar el análisis detallado)</i>"
