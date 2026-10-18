from datia.services.ai.handlers.base import BaseHandler
from datia.models.semantic import DataSource, DataField
from datia.services.ollama_service import OllamaService
import json
import re

class TrainingHandler(BaseHandler):
    """
    Handles the 'Training Mode' flow.
    Instead of executing SQL, it asks the AI to map the user's terminology
    to the existing Schema (Synonyms/Keywords) and saves it to the DB.
    """
    
    def handle(self, intent_data, context):
        question = intent_data.get('query') or ""
        
        # 1. Fetch Schema Context (Simplified for Context Window)
        # BUG FIX: Must filter by empresa to avoid cross-tenant pollution
        empresa = context.get('empresa', 0)
        try:
            empresa = int(str(empresa).strip())
        except:
            empresa = 0
        
        sources = DataSource.objects.filter(
            is_active=True,
            empresa_id=empresa
        ).prefetch_related('fields')
        
        schema_summary = []
        for ds in sources:
            fields_str = ", ".join([f"{f.business_name} (ID: {f.field_name})" for f in ds.fields.filter(is_active=True)])
            schema_summary.append(f"Table: {ds.name} (ID: {ds.id}, Keywords: {ds.keywords})\nFields: {fields_str}")
        
        schema_text = "\n\n".join(schema_summary)
        
        # 1.5 Fetch Business Context
        from datia.models.semantic import BusinessContext
        empresa = context.get('empresa', 0)
        try:
            empresa = int(str(empresa).strip())
        except:
            empresa = 0
        cx_obj = BusinessContext.objects.filter(empresa_id=empresa, key='descripcion_negocio').first()
        business_bio = cx_obj.content if cx_obj else "Standard business data analysis."
        
        ollama = OllamaService()
        model = context.get('model') or None
        if not model:
            try:
                from datia.models.master import GlobalConfig
                model = (GlobalConfig.load().llm_sql_training or GlobalConfig.load().llm_chat or '').strip() or None
            except Exception:
                model = None
        
        prompt = (
            "You are a Semantic Data Mapper. Your goal is to map the USER'S terminology to the DATABASE Schema.\n"
            f"BUSINESS CONTEXT: {business_bio}\n\n"
            "The User asked a question but the strict Query Builder failed to understand specific terms.\n\n"
            "SCHEMA:\n"
            f"{schema_text}\n\n"
            "USER QUESTION:\n"
            f"\"{question}\"\n\n"
            "TASK:\n"
            "Identify words in the User Question that are synonyms for Tables or Fields in the Schema.\n"
            "Return a JSON object with a list of 'mappings'.\n"
            "Each mapping must have:\n"
            "- 'type': 'field' or 'table'\n"
            "- 'target_id': The ID of the field (field_name) or table (id) from the Schema provided.\n"
            "- 'synonym': The exact word/phrase from the User Question that should be mapped.\n\n"
            "EXAMPLE:\n"
            "Question: 'Show me the profit'\n"
            "Schema: Field 'Margin' (ID: MarginPct)\n"
            "Output: {\"mappings\": [{\"type\": \"field\", \"target_id\": \"MarginPct\", \"synonym\": \"profit\"}]}\n\n"
            "IMPORTANT: Only map terms that are CLEARLY intended to be synonyms. Do not map generic words like 'show', 'me', 'the'.\n"
            "Return ONLY JSON."
        )
        
        response = ollama.generate_text(prompt, timeout=60, model=model)
        
        # 3. Parse and Persist
        try:
            # Clean JSON
            json_str = re.sub(r'```json\s*', '', response)
            json_str = re.sub(r'```\s*$', '', json_str).strip()
            
            data = json.loads(json_str)
            mappings = data.get('mappings', [])
            
            learned_count = 0
            
            for m in mappings:
                term = m.get('synonym', '').lower().strip()
                target_id = m.get('target_id')
                type_ = m.get('type')
                
                if not term or len(term) < 2: continue
                
                if type_ == 'field':
                    fields = DataField.objects.filter(field_name=target_id)
                    for f in fields:
                        current = list(f.synonyms or [])
                        if term not in [str(s).lower() for s in current] and term != (f.business_name or '').lower():
                            current.append(term)
                            f.synonyms = current
                            f.save()
                            learned_count += 1
                            
                elif type_ == 'table':
                    try:
                        ds = DataSource.objects.get(id=target_id)
                        current = list(ds.keywords or [])
                        if term not in [str(k).lower() for k in current] and term != (ds.name or '').lower():
                            current.append(term)
                            ds.keywords = current
                            ds.save()
                            learned_count += 1
                    except (DataSource.DoesNotExist, ValueError, TypeError):
                        pass
            
            return {
                "type": "training_completed",
                "text": f"✅ He aprendido {learned_count} nuevos conceptos. Re-procesando consulta...",
                "learned_count": learned_count,
                "should_retry": True
            }

        except Exception as e:
            return {
                "type": "error",
                "text": f"Error durante el entrenamiento: {str(e)}"
            }
