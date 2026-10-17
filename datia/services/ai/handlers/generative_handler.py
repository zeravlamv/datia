from datia.services.ai.handlers.base import BaseHandler
from datia.factories import ServiceFactory, RepositoryFactory
from datia.services.ollama_service import OllamaService
from datia.services.ai.language import LanguageService
from django.db import connections
from datia.services.security.sql_guard import SQLGuard

class GenerativeHandler(BaseHandler):
    """
    Handles queries by dynamically generating SQL using LLM + RAG (Schema).
    Fallback when no hardcoded template matches.
    """
    
    def handle(self, intent_data, context):
        question = intent_data.get('query') or "Query"
        empresa = context.get('empresa')
        ejercicio = context.get('ejercicio')
        limit = context.get('limit', 20)
        
        emb_svc = ServiceFactory.get_embedding_service()
        
        # --- LEVEL 1: MEMORY (Cache) ---
        # Check if we already know this query
        cached_template = emb_svc.search_template(question, threshold=0.5)
        
        if cached_template:
            raw_sql = cached_template['sql']
            # Hydate the template
            try:
                # Safe formatting using specific keys to avoid KeyError if template has extra braces
                # We use .format() but we need to be careful about JSON in SQL or similar.
                # Assuming simple templates for now.
                sql = raw_sql.replace('{empresa}', str(empresa)).replace('{ejercicio}', str(ejercicio)).replace('{limit}', str(limit))
                
                # Execute immediately
                SQLGuard.ensure_allowed(sql)
                with connections['analytics'].cursor() as cursor:
                    cursor.execute(sql)
                    if cursor.description:
                        columns = [col[0] for col in cursor.description]
                        rows = cursor.fetchall()
                        formatted_data = [dict(zip(columns, row)) for row in rows]
                    else:
                        formatted_data = []

                display_type = cached_template.get('type', 'table')
                if len(formatted_data) == 1 and len(columns) <= 3: display_type = 'card'

                return {
                    "type": display_type,
                    "sql": sql,
                    "data": formatted_data,
                    "text": LanguageService.get_text('generative_success', context.get('lang','es'), question=question),
                    "source": "ai_learned", # Flag for UI
                    "label": cached_template.get('label')
                }
            except Exception as e:
                # If cache fails (e.g. schema changed), fall through to LLM
                try:
                    from django.conf import settings
                    import os
                    if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                        print(f"Cache Hit failed execution: {e}")
                except:
                    pass

        # --- LEVEL 2: GENERATION (LLM) ---
        
        # 1. Retrieve Schema Context
        relevant_tables = emb_svc.search_schema(question, limit=3)
        
        if not relevant_tables:
            return {
                "text": "No he encontrado información relevante en tu base de datos para responder a eso. (Intenta configurar el Mapeo de Datos)",
                "sql": None
            }
            
        # 2. Build Schema Context String
        schema_text = "\n\n".join([t['text'] for t in relevant_tables])

        # 2.5 Retrieve Similar Examples (Few-Shot RAG) [NEW]
        similar_examples = emb_svc.find_similar_examples(question, k=3)
        examples_text = ""
        if similar_examples:
            examples_text = "\n\n--- SIMILAR SQL PATTERNS (GOLDEN EXAMPLES) ---\nUse these verified examples to understand table joins and naming conventions:\n"
            for i, ex in enumerate(similar_examples, 1):
                examples_text += f"Example {i}:\nQuestion: {ex['text']}\nSQL: {ex['sql']}\n\n"
        
        # 3. Generate SQL using Chain-of-Thought (JSON)
        req_model = context.get('model')
        ollama = OllamaService(model=req_model) if req_model else OllamaService()
        
        # New Prompt Strategy: Force JSON output with reasoning
        prompt_prefix = (
            "You are a Business Intelligence SQL Expert. You MUST reply with a VALID JSON Object.\n"
            "GOAL: Generate a PostgreSQL query to answer the question using the provided Schema Context and Similar Examples.\n\n"
            "CRITICAL RULES:\n"
            "1. TABLE NAMES: You MUST use the 'SQL Table' name provided in the context (e.g., 'DatiaDB_Cabecera...'). NEVER use raw names like 'Cabecera'.\n"
            "2. QUOTING: Wrap table names in double quotes (e.g., FROM \"DatiaDB_Table\").\n"
            f"3. FILTERING: Filter by Company Code = '{empresa}' and Year = {ejercicio}. IMPORTANT: You must find the column representing the COMPANY ID (e.g., 'CodigoEmpresa', 'Empresa', 'IdEmpresa') and the YEAR (usually called 'Ejercicio'). NEVER use 'Year' unless it explicitly exists in the schema. NEVER use 'RazonSocial', 'Nombre', or text fields for the Company ID '{empresa}'.\n"
            "4. SEMANTICS: Distinguish between 'Aggregation' (e.g., 'orders by client' -> GROUP BY) and 'Search' (e.g., 'orders of client Pepito' -> WHERE ... ILIKE).\n"
            "5. NO HALLUCINATIONS: Do NOT add WHERE filters for generic words like 'client', 'product', 'zone' unless the user specified a proper name.\n\n"
            "RESPONSE FORMAT (You must return ONLY this JSON):\n"
            "{\n"
            "  \"analysis\": \"Explain your understanding of the user request (is it grouping or filtering?) and which columns/tables you chose.\",\n"
            "  \"sql\": \"SELECT ...\"\n"
            "}"
        )
        
        # Use separated arguments if possible, or concatenated if the service expects one prompt
        augmented_q = f"{prompt_prefix}\n\nSchema Context:\n{schema_text}{examples_text}\n\nQuestion: {question}"
        
        # We assume generate_sql_query handles standard context injection or we pass it all in prompt
        raw_response = ollama.generate_sql_query(augmented_q, "") # Schema text is already in augmented_q? No, wait. 
        # In previous successful version (step 85 check): generate_sql_query(prompt_prefix + ..., schema_text)
        # In my manual overwrite (Step 85 write_to_file): `raw_response = ollama.generate_sql_query(prompt_prefix + f"\n\nQuestion: {question}", schema_text)`
        # I should stick to that pattern to be safe, although passing schema_text as 2nd arg is standard for the RAG service.
        
        raw_response = ollama.generate_sql_query(prompt_prefix + f"\n\nQuestion: {question}", schema_text)
        
        if raw_response == "-- OLLAMA_OFFLINE":
             return {
                "text": "⚠️ El sistema de IA Generativa (Ollama) está desconectado.",
                "sql": None,
                "source": "system"
             }

        # 4. Parse JSON Response
        import json
        import re
        
        sql = ""
        analysis = ""
        
        try:
            # Clean up potential markdown code blocks
            clean_json = re.sub(r'```json\s*', '', raw_response)
            clean_json = re.sub(r'```\s*$', '', clean_json)
            clean_json = clean_json.strip()
            
            data = json.loads(clean_json)
            sql = data.get("sql", "")
            analysis = data.get("analysis", "")
            
        except Exception:
            # Fallback for non-JSON responses
            # Find SELECT ... ;
            match = re.search(r'SELECT.*?;', raw_response, re.DOTALL | re.IGNORECASE)
            if match:
                sql = match.group(0)
            else:
                if "SELECT" in raw_response.upper():
                    sql = raw_response
                else:
                    return {
                        "text": "No he podido generar una estructura válida. Intenta ser más específico.",
                        "sql": None,
                        "debug_raw": raw_response
                    }

        # --- HARD FIX: FORCE CORRECT TABLE NAME (Legacy Safety Net) ---
        if relevant_tables:
            target_table_info = relevant_tables[0]['metadata'].get('table', '')
            # Fix: Case-insensitive check for prefix to avoid double-prefixing
            if target_table_info.lower().startswith("datiadb_"):
                correct_name = target_table_info
                # Remove prefix case-insensitively
                suffix = re.sub(r'^datiadb_', '', correct_name, flags=re.IGNORECASE)
                
                if suffix and suffix.lower() in sql.lower() and "datiadb_" not in sql.lower():
                     pattern = re.compile(rf'["\[\]]?{re.escape(suffix)}["\[\]]?', re.IGNORECASE)
                     sql = pattern.sub(f'"{correct_name}"', sql)

        # 5. Execute SQL
        formatted_data = []
        error_msg = None
        
        if "DELETE" in sql.upper() or "DROP" in sql.upper() or "UPDATE" in sql.upper():
             lang = context.get('lang', 'es')
             return {"answer": LanguageService.get_text('destructive_error', lang), "sql": sql}

        try:
            SQLGuard.ensure_allowed(sql)
            with connections['analytics'].cursor() as cursor:
                cursor.execute(sql)
                if cursor.description is None:
                    columns = []
                    rows = []
                else:
                    columns = [col[0] for col in cursor.description]
                    rows = cursor.fetchall()
                
                formatted_data = [dict(zip(columns, row)) for row in rows]

                if not formatted_data:
                     return {
                        "answer": (f"✨ **Análisis**: {analysis}\n\n" if analysis else "") + f"No he encontrado datos para '{question}' en el ejercicio {ejercicio}.",
                        "sql": sql,
                        "source": "ai",
                        "type": "text",
                        "analysis": analysis 
                     }
                
                # --- LEVEL 3: TRAINING (Validation Phase) ---
                should_train = context.get('training_enabled', False)

        except Exception as e:
            error_msg = str(e)
            
        lang = context.get('lang', 'es')
        
        if error_msg:
            # Enhanced Error Message with Actions
            sugg_html = """
            <div style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button class="btn-secondary" onclick="openSqlEditor(this)" data-sql="{sql}">🛠️ Ajustar SQL</button>
                <button class="btn-primary" onclick="startTrainingFlow('{q}')">✨ Intentar de nuevo</button>
            </div>
            """.replace('{sql}', sql.replace('"', '&quot;')).replace('{q}', question.replace("'", "\\'"))
            
            return {
                "answer": f"He intentado generar una consulta, pero ha fallado: {error_msg}<br>{sugg_html}",
                "type": "error",
                "sql": sql,
                "debug_sql": sql
            }
            
        # --- SUCCESS: Delegate to Formatter ---
        # 1. Enrich with Top Breakdown if Sales Context
        # Heuristic: If query mentions 'ventas', 'facturacion', or we are comparing years
        extras = {}
        is_sales_context = any(k in question.lower() for k in ['venta', 'factur', 'revenue', 'compar', 'vs'])
        
        if is_sales_context:
            try:
                # Fetch Top Clients
                top_clients = self._fetch_top_breakdown('DatiaDB_CabeceraPedidoCliente', 'NombreCliente', 'ImporteNeto', context, limit=5)
                if top_clients: extras['top_clients'] = top_clients
                
                # Fetch Top Products
                top_products = self._fetch_top_breakdown('DatiaDB_LineasPedidoCliente', 'DescripcionArticulo', 'ImporteNeto', context, limit=5)
                if top_products: extras['top_products'] = top_products
            except Exception as e:
                print(f"Error fetching extras: {e}")
                pass

        # 2. Build Match Meta
        match_meta = {
            'sql': sql,
            'type': 'table', # Default to table, formatter will upgrade to chart if suitable
            'label': question, # Use question as label
            'source': 'ai_gen',
            'analysis': analysis,
            'extras': extras # Pass extras
        }
        
        # 3. Call Formatter
        # This ensures consistent "Senior Consultant" summary
        return self.formatter.format_response(match_meta, formatted_data, ejercicio, limit, lang=lang)
