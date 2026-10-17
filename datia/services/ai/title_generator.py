import re
from typing import Dict, Any, Optional
from django.db import connections


class TitleGenerator:
    MESES = {
        'enero': 1, 'ene': 1,
        'febrero': 2, 'feb': 2,
        'marzo': 3, 'mar': 3,
        'abril': 4, 'abr': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6,
        'julio': 7, 'jul': 7,
        'agosto': 8, 'ago': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9, 'setiembre': 9,
        'octubre': 10, 'oct': 10,
        'noviembre': 11, 'nov': 11,
        'diciembre': 12, 'dic': 12
    }
    MESES_LABEL = {1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'}

    def __init__(self):
        self.db = 'analytics' if 'analytics' in connections.databases else 'default'

    def _detect_entity(self, q: str, intent_meta: Dict[str, Any], state: Dict[str, Any]) -> str:
        if 'cliente' in q:
            return 'cliente'
        if 'producto' in q or 'articulo' in q or 'artículos' in q:
            return 'producto'
        if 'familia' in q:
            return 'familia'
        if 'agente' in q or 'vendedor' in q or 'comercial' in q:
            return 'agente'
        v = intent_meta.get('grouping')
        if v == 'client':
            return 'cliente'
        if v == 'product':
            return 'producto'
        if v == 'family':
            return 'familia'
        if v == 'agent':
            return 'agente'
        return state.get('entity') or 'cliente'

    def _detect_metric(self, q: str, intent_meta: Dict[str, Any], state: Dict[str, Any]) -> str:
        if re.search(r'\brentab|margen|beneficio\b', q):
            return 'margin'
        if re.search(r'\bcoste|gasto|costos?\b', q):
            return 'cost'
        if re.search(r'\bunidades|cantidad\b', q):
            return 'units'
        if re.search(r'\bprecio\b', q):
            return 'price'
        return intent_meta.get('metric') or state.get('metric') or 'sales'

    def _detect_top(self, q: str) -> Optional[int]:
        m = re.search(r'\btop\s+(\d{1,3})\b', q)
        if m:
            return int(m.group(1))
        m2 = re.search(r'\b(mejores|peores)\s+(\d{1,3})\b', q)
        if m2:
            return int(m2.group(2))
        return None

    def _detect_order(self, q: str) -> str:
        if re.search(r'\bpeores|menor|worst|menos\b', q):
            return 'ASC'
        return 'DESC'

    def _detect_period(self, q: str, state: Dict[str, Any]) -> Dict[str, Any]:
        ql = q.lower()
        y = re.search(r'\b(20\d{2})\b', ql)
        year = int(y.group(1)) if y else None
        m_between = re.search(r'\b(entre|desde|de)\s+([a-záéíóú]+|\d{1,2})\s+(?:y|a|hasta)\s+([a-záéíóú]+|\d{1,2})\b', ql)
        if m_between:
            def to_m(tok: str) -> Optional[int]:
                tok = tok.lower()
                if tok.isdigit():
                    vi = int(tok)
                    return vi if 1 <= vi <= 12 else None
                return self.MESES.get(tok)
            s = to_m(m_between.group(2))
            e = to_m(m_between.group(3))
            if s and e:
                return {'month': None, 'range': (s, e), 'year': year}
        for k, v in self.MESES.items():
            if re.search(r'\b' + k + r'\b', ql):
                return {'month': v, 'range': None, 'year': year}
        mr = state.get('month_range')
        if mr:
            return {'month': mr[0] if mr[0] == mr[1] else None, 'range': mr if mr[0] != mr[1] else None, 'year': state.get('ejercicio')}
        return {'month': None, 'range': None, 'year': year}

    def _metric_label(self, metric: str, q: str) -> str:
        if metric == 'margin':
            return 'margen bruto'
        if metric == 'cost':
            return 'importe de coste'
        if metric == 'sales':
            return 'ventas'
        if metric == 'units':
            if 'unidades' in q:
                return 'unidades vendidas'
            return 'cantidad de unidades vendidas'
        if metric == 'price':
            return 'precio'
        return 'importe neto vendido'

    def _entity_label(self, entity: str, q: str, top: Optional[int], singular_hint: bool) -> str:
        if entity == 'cliente':
            if singular_hint:
                return 'Cliente'
            return 'Clientes'
        if entity == 'producto':
            if singular_hint:
                return 'Producto'
            return 'Productos'
        if entity == 'familia':
            if singular_hint:
                return 'Familia'
            return 'Familias'
        if entity == 'agente':
            if singular_hint:
                return 'Agente'
            return 'Agentes'
        return 'Entidad'

    def _compose_period(self, p: Dict[str, Any]) -> str:
        if p.get('month'):
            return f"en {self.MESES_LABEL.get(p['month'], p['month'])}" + (f" de {p['year']}" if p.get('year') else "")
        if p.get('range'):
            s, e = p['range']
            sL = self.MESES_LABEL.get(s, s)
            eL = self.MESES_LABEL.get(e, e)
            return f"entre {sL} y {eL}" + (f" de {p['year']}" if p.get('year') else "")
        if p.get('year'):
            return f"en {p['year']}"
        return ""

    def _singular_hint(self, q: str) -> bool:
        return bool(re.search(r'\bque\s+cliente\b|\bqué\s+cliente\b|\bque\s+producto\b|\bqué\s+articulo\b|\bmejor\s+producto\b|\bpeor\s+producto\b|\bmejor\s+cliente\b|\bpeor\s+cliente\b', q))

    def _ensure_unique(self, title: str, conv_id: Optional[int]) -> str:
        if not conv_id:
            return title
        try:
            with connections[self.db].cursor() as cur:
                cur.execute("SELECT intent FROM datiadb_ai_turns WHERE conversation_id=%s ORDER BY id DESC LIMIT 10", [conv_id])
                rows = cur.fetchall()
                existed = False
                for r in rows:
                    if not r[0]:
                        continue
                    try:
                        import json
                        j = r[0]
                        t = j.get('title') if isinstance(j, dict) else json.loads(j).get('title')
                        if t == title:
                            existed = True
                            break
                    except Exception:
                        pass
                if existed:
                    return title + " · v2"
        except Exception:
            return title
        return title

    def generate(self, question: str, intent_meta: Dict[str, Any], state: Dict[str, Any], conv_id: Optional[int]) -> str:
        q = question.lower().strip()
        entity = self._detect_entity(q, intent_meta or {}, state or {})
        metric = self._detect_metric(q, intent_meta or {}, state or {})
        top = self._detect_top(q)
        order = self._detect_order(q)
        period = self._detect_period(q, state or {})
        singular_hint = self._singular_hint(q)
        ent_label = self._entity_label(entity, q, top, singular_hint)
        met_label = self._metric_label(metric, q)
        per_label = self._compose_period(period)
        prefix = ""
        if top and order == 'DESC':
            prefix = f"Top {top} {ent_label} por {met_label}"
        elif top and order == 'ASC':
            prefix = f"Peores {top} {ent_label} por {met_label}"
        elif singular_hint:
            prefix = f"{ent_label} con menor {met_label}" if order == 'ASC' else f"{ent_label} con mayor {met_label}"
        else:
            if metric in ['sales', 'cost', 'margin', 'units', 'price']:
                prefix = f"{met_label.capitalize()} por {((ent_label[:-1] if ent_label.endswith('s') else ent_label).lower() if (('producto' in q) or ('articulo' in q) or ('artículos' in q)) else (ent_label[:-1] if ent_label.endswith('s') else ent_label))}"
            else:
                prefix = f"{ent_label}"
        suffix = f" {per_label}" if per_label else ""
        title = prefix + suffix
        return self._ensure_unique(title, conv_id)
