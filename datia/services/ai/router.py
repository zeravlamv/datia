
import re
from typing import Dict, Any, Tuple
from django.utils import translation
from datia.models import UserPreference
from datia.services.query_builder import QueryBuilder
# from django.utils.translation import LANGUAGE_SESSION_KEY # Not available in this version

LANGUAGE_SESSION_KEY = '_language'
from .handlers.report_handler import ReportHandler
from .handlers.list_handler import ListHandler
from .handlers.dynamic_handler import DynamicHandler
from .handlers.generative_handler import GenerativeHandler
from .handlers.training_handler import TrainingHandler
from .handlers.compute_handler import PythonComputeHandler
from .handlers.catalog_report_handler import CatalogReportHandler
from .conversation_manager import ConversationManager
from .title_generator import TitleGenerator
from .ambiguity_analyzer import AmbiguityAnalyzer
from datia.models.master import GlobalConfig
from .nlq_catalog import match_intent, cubre_la_pregunta

class IntentRouter:
    MONTHS = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    def __init__(self, embedding_service):
        self.embedding_service = embedding_service

    def resolve(self, question: str, context: dict = {}) -> Tuple[Any, Dict]:
        """
        Main routing logic. Strict "Tabula Rasa" Flow.
        Returns: (HandlerClass, intent_data_dict)
        """
        cat_backup = None
        try:
            from django.conf import settings
            import os
            if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                print(f"DEBUG: Router.resolve context: {context}")
        except:
            pass
        
        # Conversational Memory: enriquecer pregunta y contexto
        empresa = context.get('empresa', 'DEMO')
        ejercicio = context.get('ejercicio', 2025)
        limit = context.get('limit', 10)
        training_enabled = context.get('training_enabled', False)

        context['limit'] = limit 
        # Inicializar/Enriquecer sesión
        try:
            cm = ConversationManager()
            cm.ensure_schema()
            user_id = None
            req = context.get('request')
            if req and getattr(req, 'user', None) and getattr(req.user, 'id', None):
                user_id = req.user.id
            else:
                user_id = context.get('user_id')
            enriched_q, enriched_ctx, delta, conv_id = cm.enrich(question, context, user_id)
            context = enriched_ctx
            question = enriched_q
        except Exception:
            conv_id = None
            delta = {}
        q_lower = question.lower().strip()

        if q_lower.startswith('informe detallado y '):
            q_lower = q_lower.replace('informe detallado y ', '').strip()
            context['detailed'] = True

        cat = match_intent(q_lower)
        cat_backup = None
        if cat and cubre_la_pregunta(q_lower, cat.get('intent_id')):
            try:
                cat['query'] = question
            except Exception:
                pass
            return CatalogReportHandler, cat
        if cat:
            try:
                cat['query'] = question
            except Exception:
                pass
            cat_backup = cat

        # --- 0. Language Change Intent ---
        # Regex to detect: "cambiar a ingles", "speak in english", "ponlo en frances"
        lang_pattern = r'(?:cambiar|poner|traducir|speak|switch).*(?:idioma|a|in|to)?\s+(ingl[ée]s|english|franc[ée]s|french|alem[áa]n|german|catal[áa]n|catala|portugu[ée]s|portuguese|italiano|italian|vasco|euskera|gallego|galician|español|spanish|castellano)'
        lang_match = re.search(lang_pattern, q_lower)
        
        if lang_match:
            target_raw = lang_match.group(1).lower()
            lang_map = {
                'ingles': 'en', 'inglés': 'en', 'english': 'en',
                'frances': 'fr', 'francés': 'fr', 'french': 'fr',
                'aleman': 'de', 'alemán': 'de', 'german': 'de',
                'catalan': 'ca', 'catalán': 'ca', 'catala': 'ca',
                'portugues': 'pt', 'portugués': 'pt', 'portuguese': 'pt',
                'italiano': 'it', 'italian': 'it',
                'vasco': 'eu', 'euskera': 'eu',
                'gallego': 'gl', 'galician': 'gl',
                'español': 'es', 'spanish': 'es', 'castellano': 'es'
            }
            target_code = lang_map.get(target_raw, 'es')
            
            # Check Persistence
            is_permanent = any(x in q_lower for x in ['permanente', 'para siempre', 'guardar', 'fijo', 'forever', 'default'])
            
            request = context.get('request')
            if request:
                # 1. Session Update (Immediate)
                request.session[LANGUAGE_SESSION_KEY] = target_code
                translation.activate(target_code)
                
                # 2. Persistence Update (if requested or if logic dictates)
                # User asked for "permanente" OR maybe we want to always save it? The requirement says "indicando permanente".
                if is_permanent and request.user.is_authenticated:
                    try:
                        # Ensure UserPreference exists
                        pref, _ = UserPreference.objects.get_or_create(user=request.user)
                        pref.language = target_code
                        pref.save()
                        persistence_msg = " (Preferencia guardada permanentemente)"
                    except Exception as e:
                        try:
                            from django.conf import settings
                            import os
                            if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                                print(f"Error saving preference: {e}")
                        except:
                            pass
                        persistence_msg = " (Error guardando preferencia)"
                else:
                    persistence_msg = ""
                
                # 3. Return Action for Frontend Reload
                lang_names = {'en': 'English', 'es': 'Español', 'fr': 'Français', 'de': 'Deutsch', 'it': 'Italiano', 'pt': 'Português', 'ca': 'Català', 'gl': 'Galego', 'eu': 'Euskara'}
                lang_label = lang_names.get(target_code, target_code)
                
                return None, {
                    'text': f"Cambiando idioma a <b>{lang_label}</b>...{persistence_msg}<br>La página se recargará en unos instantes.",
                    'action': 'RELOAD', # Special Flag
                    'lang': target_code
                }


        analyzer = AmbiguityAnalyzer()
        try:
            gc = GlobalConfig.load()
            settings_map = gc.implanter_settings or {}
            context['ambiguity_threshold'] = float(settings_map.get('ai_ambiguity_threshold', 0.85))
        except Exception:
            context['ambiguity_threshold'] = 0.85
        amb = analyzer.analyze(question, context)
        if amb.get('ambiguous'):
             return None, {
                'type': 'ambiguity_alert',
                'text': amb.get('text'),
                'answer': amb.get('text'),
                'details': {'categories': amb.get('categories'), 'reasons': amb.get('reasons')},
                'suggestions': amb.get('suggestions'),
                'clarity': amb.get('clarity')
             }
        # 1. Broad Status/Report Keywords
        # [FIX] Be more strict. 'pedidos de enero' should NOT match 'report'.
        # Only trigger report if the INTENT is clearly a summary.
        report_keywords = ['informe anual', 'informe general', 'situacion global', 'resumen anual', 'balance anual']
        
        # Check for 'como va' but ensure it's not 'como va el pedido X'
        if q_lower in ['como va', 'como vamos', 'situacion', 'resumen', 'balance', 'report', 'status']:
             data = {'key': 'annual_report', 'type': 'report', 'display_mode': 'annual'}
             return ReportHandler, data
             
        if any(x in q_lower for x in report_keywords):
             data = {'key': 'annual_report', 'type': 'report', 'display_mode': 'annual'}
             return ReportHandler, data

        # 2. Ranking / Top Lists (Regex High Confidence)
        ranking_keywords = ['top', 'ranking', 'mejores', 'mejor', 'mayor', 'best', 'mas vend', 'peores']
        if any(x in q_lower for x in ranking_keywords):
            # Derivar directamente a QueryBuilder para ranking determinista por entidad
            # Detectar entidad objetivo por keywords
            target_entity = None
            if ('cliente' in q_lower) or ('clientes' in q_lower):
                target_entity = 'cliente'
            elif ('articulo' in q_lower) or ('artículos' in q_lower) or ('producto' in q_lower) or ('productos' in q_lower):
                target_entity = 'articulo'
            elif ('agente' in q_lower) or ('vendedor' in q_lower) or ('comercial' in q_lower):
                target_entity = 'agente'
            elif ('zona' in q_lower) or ('region' in q_lower) or ('provincia' in q_lower):
                target_entity = 'zona'
            elif ('familia' in q_lower) or ('familias' in q_lower):
                target_entity = 'familia'
            if target_entity:
                result = QueryBuilder._handle_ranking(q_lower, empresa, ejercicio, target_entity)
                if result:
                    tg = TitleGenerator()
                    title = tg.generate(question, result.get('intent_meta') or {}, context.get('conversation_state') or {}, conv_id)
                    result['label'] = title
                    im = result.get('intent_meta') or {}
                    im['title'] = title
                    result['intent_meta'] = im
                    try:
                        if conv_id:
                            cm.save_turn(conv_id, question, delta, result.get('sql'), intent=result.get('intent_meta'))
                    except Exception:
                        pass
                    return DynamicHandler, result
            # Si no se detecta entidad explícita, continuar al QueryBuilder general
        # 2.1 Compute Intent
        compute_keywords = ['media mov', 'moving average', 'ratio', 'normaliz', 'pronostic', 'tendenc', 'correl']
        if any(x in q_lower for x in compute_keywords):
            return PythonComputeHandler, {'query': question}

        # 3. Dynamic Query Builder (The Core Brain)
        try:
            # We pass 'training_enabled' to QueryBuilder so it knows whether to attempt Generation or just Recall.
            dynamic_match = QueryBuilder.build_from_nl(q_lower, context)
            if not dynamic_match or dynamic_match.get('error'):
                from datia.services.ai.open_question import OpenQuestion
                abierta = OpenQuestion.responder(question, empresa, ejercicio, limit)
                if abierta and not abierta.get('error'):
                    dynamic_match = abierta
            
            if dynamic_match:
                if dynamic_match.get('reply'):
                    return None, dynamic_match['reply']
                if dynamic_match.get('error'):
                    # Handle strict errors from QueryBuilder
                    error_type = dynamic_match.get('error')
                    details = dynamic_match.get('details', '')
                    
                    if error_type == 'PASSIVE_MODE':
                         # Fallthrough to existing passive logic
                         pass 
                    
                    elif error_type == 'NO_TABLES':
                         # Keep the original suggestion but be specific
                         msg = "He intentado generar una consulta segura (DatiaDB_), pero no he encontrado las tablas necesarias.<br>Verifica que el esquema DatiaDB_ est&aacute; sincronizado."
                         return None, {'text': msg}
                    
                    elif error_type == 'VALIDATION_FAILED':
                         msg = "He generado una consulta, pero no cumple los protocolos de seguridad (No ataca tablas DatiaDB_)."
                         return None, {'text': msg}

                    elif error_type == 'VALIDATION_FAILED_SECURITY':
                         msg = f"<b>ALERTA DE SEGURIDAD</b>: {details}"
                         return None, {'text': msg}
                    
                    elif error_type == 'VALIDATION_FAILED_SYNTAX':
                         msg = "La IA no pudo generar una consulta SQL válida (Error de Sintaxis)."
                         return None, {'text': msg}

                    elif error_type == 'AMBIGUOUS':
                         return None, {
                            'type': 'training_ask',
                            'question': question,
                            'text': "¿Quieres ver por Pedido o por Albarán?",
                            'details': details or 'pedido_or_albaran'
                         }

                    elif error_type == 'GENERATION_ERROR' or error_type == 'TIMEOUT':
                         # Fallback to Manual Training (Pattern 2.3)
                         return None, {
                            'type': 'training_ask',
                            'question': question,
                            'text': f"He tenido problemas generando la respuesta ({details}). ¿Quieres enseñarme cómo hacerlo?"
                        }

                    elif error_type == 'TIMEOUT_SAT':
                        # STRICT TIMEOUT HANDLER (>15s)
                        # [FIX] Provide more actionable error message
                        msg = f"❌ <b>Tiempo de espera agotado.</b><br>{details}<br><br>Sugerencia: Intenta ser más específico o verifica si la tabla está entrenada."
                        return None, {'text': msg}
                    
                else:
                    if dynamic_match.get('keep_label') and dynamic_match.get('label'):
                        title = dynamic_match['label']
                    else:
                        tg = TitleGenerator()
                        title = tg.generate(question, dynamic_match.get('intent_meta') or {}, context.get('conversation_state') or {}, conv_id)
                        dynamic_match['label'] = title
                    im = dynamic_match.get('intent_meta') or {}
                    im['title'] = title
                    dynamic_match['intent_meta'] = im
                    # Success: persistir turno en memoria conversacional
                    try:
                        if conv_id:
                            cm.save_turn(conv_id, question, delta, dynamic_match.get('sql'), intent=dynamic_match.get('intent_meta'))
                    except Exception:
                        pass
                    return DynamicHandler, dynamic_match

            
        except Exception as e:
            print(f"Router: QueryBuilder Error: {e}")

        if cat_backup:
            return CatalogReportHandler, cat_backup

        if not training_enabled:
            return None, {
                'type': 'text',
                'question': question,
                'text': (
                    "No he podido preparar una consulta segura para esta pregunta. "
                    "Nombra el dato: ventas, compras, clientes, artículos, margen o coste."
                ),
                'suggestions': [
                    {'label': 'Mejores clientes', 'query': 'mejores clientes'},
                    {'label': 'Ventas y compras', 'query': 'ventas y compras'},
                    {'label': 'Margen por cliente', 'query': 'margen por cliente'},
                ],
            }

        try:
            trained = TrainingHandler(None).handle({'query': question}, context)
            if trained.get('learned_count', 0) > 0:
                retry = QueryBuilder.build_from_nl(q_lower, context)
                if retry and not retry.get('error'):
                    return DynamicHandler, retry
        except Exception as exc:
            print(f"Router: entrenamiento de sinónimos no disponible: {exc}")
        if cat_backup:
            return CatalogReportHandler, cat_backup
        return None, {
            'type': 'text',
            'text': (
                "No he podido dejar esta pregunta en una consulta sobre las métricas de la empresa. "
                "Prueba con clientes, artículos, ventas, compras, margen o coste."
            ),
        }


