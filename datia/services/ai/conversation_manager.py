import re
import json
import datetime
from typing import Dict, Tuple, Any, Optional
from django.db import connections
from django.utils.crypto import get_random_string


class ConversationManager:
    """
    Gestor de memoria conversacional multi‑turno para IA.
    - Persiste sesiones y turnos en Postgres (analytics).
    - Enriquece el contexto con estado previo (empresa, ejercicio, entidad, métrica, periodo, límites).
    - Resuelve elipsis y referencias (“y en octubre?”, “los peores?”, “top 10”).
    """

    def __init__(self, db_alias: str = None):
        self.db = db_alias or ('analytics' if 'analytics' in connections.databases else 'default')

    # --- Esquema mínimo: auto‑creación segura si no existen tablas ---
    def ensure_schema(self) -> None:
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS datiadb_ai_conversations(
              id SERIAL PRIMARY KEY,
              user_id INTEGER,
              empresa INTEGER,
              ejercicio INTEGER,
              topic TEXT,
              state JSONB DEFAULT '{}'::jsonb,
              created_at TIMESTAMP DEFAULT NOW(),
              updated_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS datiadb_ai_turns(
              id SERIAL PRIMARY KEY,
              conversation_id INTEGER REFERENCES datiadb_ai_conversations(id) ON DELETE CASCADE,
              turn_index INTEGER,
              input_text TEXT,
              intent JSONB,
              state_delta JSONB,
              sql TEXT,
              result_hash TEXT,
              created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS datiadb_ai_entities(
              id SERIAL PRIMARY KEY,
              conversation_id INTEGER REFERENCES datiadb_ai_conversations(id) ON DELETE CASCADE,
              entity_type TEXT,
              canonical_name TEXT,
              data JSONB,
              created_at TIMESTAMP DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS datiadb_ai_metrics(
              id SERIAL PRIMARY KEY,
              conversation_id INTEGER REFERENCES datiadb_ai_conversations(id) ON DELETE CASCADE,
              turn_id INTEGER REFERENCES datiadb_ai_turns(id) ON DELETE CASCADE,
              quality_score NUMERIC,
              coherence_score NUMERIC,
              satisfaction INTEGER,
              notes TEXT,
              created_at TIMESTAMP DEFAULT NOW()
            )
            """
        ]
        try:
            with connections[self.db].cursor() as cur:
                for stmt in ddl:
                    cur.execute(stmt)
        except Exception:
            # Si el usuario no concede permisos de DDL, el sistema funcionará en modo "solo lectura" de estado.
            pass

    # --- Gestión de sesión y estado ---
    def _default_state(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        return {
            "empresa": empresa,
            "ejercicio": ejercicio,
            "intent": None,
            "entity": None,
            "metric": None,
            "month_range": None,
            "quarter": None,
            "semester": None,
            "limit": 20,
            "order": "DESC"
        }

    def get_or_start_session(self, user_id: Optional[int], empresa: int, ejercicio: int) -> Tuple[int, Dict[str, Any]]:
        with connections[self.db].cursor() as cur:
            cur.execute("""
                SELECT id, state FROM datiadb_ai_conversations 
                WHERE user_id = %s AND empresa = %s AND ejercicio = %s 
                ORDER BY updated_at DESC LIMIT 1
            """, [user_id or 0, empresa, ejercicio])
            row = cur.fetchone()
            if row:
                conv_id, state = row[0], row[1] or {}
                if isinstance(state, str):
                    try:
                        state = json.loads(state)
                    except Exception:
                        state = {}
                return conv_id, state
            # Crear nueva conversación
            state = self._default_state(empresa, ejercicio)
            cur.execute("""
                INSERT INTO datiadb_ai_conversations(user_id, empresa, ejercicio, topic, state)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, [user_id or 0, empresa, ejercicio, "general", json.dumps(state)])
            conv_id = cur.fetchone()[0]
            return conv_id, state

    # --- Resolución de elipsis y coreferencias ligeras ---
    def _parse_delta(self, text: str) -> Dict[str, Any]:
        t = text.lower().strip()

        meses = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12
        }
        delta: Dict[str, Any] = {}

        # Mes único o rango "entre X y Y"
        m_one = re.search(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b', t)
        if m_one:
            mv = meses.get(m_one.group(1))
            if mv:
                delta['month_range'] = (mv, mv)
        else:
            m_between = re.search(r'\b(entre|desde|de)\s+([a-záéíóú]+|\d{1,2})\s+(?:y|a|hasta)\s+([a-záéíóú]+|\d{1,2})\b', t)
            if m_between:
                def to_m(tok: str) -> Optional[int]:
                    tok = tok.lower()
                    if tok.isdigit():
                        v = int(tok)
                        return v if 1 <= v <= 12 else None
                    return meses.get(tok)
                s = to_m(m_between.group(2))
                e = to_m(m_between.group(3))
                if s and e:
                    delta['month_range'] = (s, e)

        # Top N y orden
        m_top = re.search(r'\btop\s+(\d{1,3})\b', t)
        if m_top:
            delta['limit'] = int(m_top.group(1))
            delta['intent'] = 'ranking'
        if re.search(r'\bpeores|peor|menor|worst\b', t):
            delta['order'] = 'ASC'
            delta['intent'] = 'ranking'
        if re.search(r'\bmejores|mejor|mayor|best\b', t):
            delta['order'] = 'DESC'
            delta['intent'] = 'ranking'

        # Entidad foco
        if re.search(r'\bproductos|articulos?\b', t):
            delta['entity'] = 'articulo'
        elif re.search(r'\bclientes?\b', t):
            delta['entity'] = 'cliente'
        elif re.search(r'\bfamilias?\b', t):
            delta['entity'] = 'familia'
        elif re.search(r'\bagentes?|vendedores?|comerciales?\b', t):
            delta['entity'] = 'agente'

        # Métrica foco
        if re.search(r'\brentab|benefic|margen\b', t):
            delta['metric'] = 'margin'
        elif re.search(r'\bventas|neto|importe\b', t):
            delta['metric'] = 'sales'
        elif re.search(r'\bcoste|gasto\b', t):
            delta['metric'] = 'cost'

        # Año explícito
        years = re.findall(r'\b(20\d{2})\b', t)
        if years:
            delta['ejercicio'] = int(years[0])

        return delta

    def enrich(self, question: str, base_context: Dict[str, Any], user_id: Optional[int]) -> Tuple[str, Dict[str, Any], Dict[str, Any], int]:
        empresa = int(base_context.get('empresa'))
        ejercicio = int(base_context.get('ejercicio'))

        conv_id, state = self.get_or_start_session(user_id, empresa, ejercicio)
        delta = self._parse_delta(question)

        # Merge: lo nuevo sobre lo previo
        new_state = dict(state)
        for k, v in delta.items():
            new_state[k] = v

        # Enriquecer contexto para Router/QueryBuilder
        ctx = dict(base_context)
        ctx['empresa'] = new_state.get('empresa', empresa)
        ctx['ejercicio'] = new_state.get('ejercicio', ejercicio)
        ctx['conversation_id'] = conv_id
        ctx['conversation_state'] = new_state

        # Si pregunta es elíptica (“y en octubre?”), conservar la base pero incluir pistas en el texto
        q = question
        q_lower = question.lower()
        theme_pattern = r'\b(ventas|compras|rentab|margen|coste|articulos?|artículos?|clientes?|familias?|agentes?|ranking|top|tesorer[ií]a|cartera|presupuesto|balances?|saldos?|anatom[ií]a|informe|resumen)\b'
        ellipsis_pattern = r'^\s*(y|y en|y para|tambien|también|otra vez|lo mismo)\b'
        if not re.search(theme_pattern, q_lower) and re.search(ellipsis_pattern, q_lower):
            # Inyectar entidad/métrica si existen en estado previo para guiar al Router
            hints = []
            if new_state.get('entity'):
                hints.append(new_state['entity'])
            if new_state.get('metric'):
                hints.append(new_state['metric'])
            if new_state.get('intent') == 'ranking':
                hints.append('ranking')
                # Añadir top N si hay límite en estado
                lim = new_state.get('limit')
                if lim:
                    hints.append(f'top {lim}')
            # Añadir mes/rango si existe en estado y no hay mención en la pregunta original
            mr = new_state.get('month_range')
            if mr and not re.search(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\b', question.lower()):
                meses_nom = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}
                s, e = mr
                if s == e:
                    hints.append(meses_nom.get(s, str(s)))
                else:
                    hints.append(f'entre {meses_nom.get(s, s)} y {meses_nom.get(e, e)}')
            if hints:
                q = f"{question.strip()} ({' '.join(hints)})"

        # Persistir estado actualizado en conversación
        try:
            with connections[self.db].cursor() as cur:
                cur.execute("""
                    UPDATE datiadb_ai_conversations SET state = %s, updated_at = NOW() WHERE id = %s
                """, [json.dumps(new_state), conv_id])
        except Exception:
            pass

        return q, ctx, delta, conv_id

    def save_turn(self, conv_id: int, turn_text: str, delta: Dict[str, Any], sql: Optional[str], intent: Optional[Dict[str, Any]] = None) -> None:
        try:
            with connections[self.db].cursor() as cur:
                result_hash = None
                if sql:
                    result_hash = get_random_string(12)
                # obtener índice
                cur.execute("SELECT COALESCE(MAX(turn_index), -1) + 1 FROM datiadb_ai_turns WHERE conversation_id = %s", [conv_id])
                idx = cur.fetchone()[0]
                cur.execute("""
                    INSERT INTO datiadb_ai_turns(conversation_id, turn_index, input_text, intent, state_delta, sql, result_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [conv_id, idx, turn_text, json.dumps(intent or {}), json.dumps(delta or {}), sql, result_hash])
        except Exception:
            pass
