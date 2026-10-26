import time
import os
import json
import re
from typing import Dict, Any
from django.conf import settings
from datia.services.ai.intent_detector import IntentDetector
from datia.services.query_builder import QueryBuilder

class AmbiguityAnalyzer:
    def analyze(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        q = (question or "").lower().strip()
        empresa = context.get('empresa')
        ejercicio = context.get('ejercicio')
        threshold = float(context.get('ambiguity_threshold', 0.85))
        detector = IntentDetector()
        intent = detector.detect(q, empresa)
        categories = []
        reasons = []
        suggestions = []
        ranking_kw = ['top', 'ranking', 'mejores', 'peores', 'peor', 'mejor']
        is_ranking = any(x in q for x in ranking_kw)
        has_cliente = ('cliente' in q) or ('clientes' in q)
        has_articulo = ('articulo' in q) or ('artículos' in q) or ('producto' in q) or ('productos' in q)
        has_proveedor = ('proveedor' in q) or ('proveedores' in q)
        has_pedido = ('pedido' in q) or ('pedidos' in q)
        has_albaran = ('albaran' in q) or ('albarán' in q) or ('albaranes' in q)
        has_ventas = 'venta' in q or 'ventas' in q or 'factur' in q
        has_compras = 'compra' in q or 'compras' in q or 'gasto' in q or 'gastos' in q
        temporal = intent.get('temporal') or {}
        has_year = bool(temporal.get('year')) or bool(ejercicio)
        direction = 'peores' if ('peor' in q or 'menor' in q) else 'mejores'
        amount = 10
        amount_match = re.search(r'\b(\d{1,3})\b', q)
        if amount_match and not re.fullmatch(r'20\d{2}', amount_match.group(1)):
            amount = int(amount_match.group(1))
        year_label = ejercicio if ejercicio else ''

        lectura = context.get('lectura') if isinstance(context.get('lectura'), dict) else {}
        if is_ranking and not (has_cliente or has_articulo or has_proveedor) and not lectura.get('conceptos'):
            categories.append('linguistica')
            reasons.append('ranking_sin_entidad')
            suggestions.extend([
                {'label': f'{amount} {direction} productos', 'query': f'los {amount} {direction} productos {year_label}'.strip()},
                {'label': f'{amount} {direction} clientes', 'query': f'los {amount} {direction} clientes {year_label}'.strip()},
                {'label': f'{amount} {direction} proveedores', 'query': f'los {amount} {direction} proveedores {year_label}'.strip()},
            ])
        if has_ventas and has_compras and not is_ranking:
            categories.append('linguistica')
            reasons.append('ventas_vs_compras')
            y = ejercicio if ejercicio else 0
            suggestions.append({'label': 'Ventas', 'query': f'ventas {y}'})
            suggestions.append({'label': 'Compras', 'query': f'compras {y}'})
        tech_flag = False
        table_check = None
        if has_cliente and is_ranking:
            if has_pedido:
                table_check = 'datiadb_lineaspedidocliente'
            elif has_albaran:
                table_check = 'datiadb_lineasalbarancliente'
            else:
                table_check = 'datiadb_lineaspedidocliente'
        elif has_articulo and is_ranking:
            if has_pedido:
                table_check = 'datiadb_lineaspedidocliente'
            elif has_albaran:
                table_check = 'datiadb_lineasalbarancliente'
            else:
                table_check = 'datiadb_lineaspedidocliente'
        if table_check:
            _, col_map = QueryBuilder._validate_table_columns(table_check, [])
            sales_cands = ['ImporteLiquido', 'ImporteNeto', 'ImporteBruto', 'BaseImponible', 'TotalNeto', 'Importe_bruto', 'Importe_neto', 'Importe_liquido']
            ok = any(c.lower() in col_map for c in [x.lower() for x in sales_cands])
            # Solo marcar técnica si hay columnas pero no se encuentran métricas
            if col_map and not ok:
                tech_flag = True
        if tech_flag:
            categories.append('tecnica')
            reasons.append('tabla_sin_metricas')
        clarity = 1.0
        if 'linguistica' in categories:
            clarity -= 0.4
        if 'contextual' in categories:
            clarity -= 0.3
        if 'tecnica' in categories:
            clarity -= 0.4
        if clarity < 0:
            clarity = 0.0
        ambiguous = clarity < threshold and len(categories) > 0
        t1 = time.perf_counter()
        time_ms = int((t1 - t0) * 1000)
        if 'ranking_sin_entidad' in reasons:
            message = 'Indica si buscas productos, clientes o proveedores.'
        else:
            message = 'Se ha detectado ambigüedad en la consulta.'
        payload = {
            'ambiguous': ambiguous,
            'clarity': clarity,
            'categories': categories,
            'reasons': reasons,
            'suggestions': suggestions,
            'time_ms': time_ms,
            'text': message
        }
        try:
            base_dir = settings.BASE_DIR
            path = os.path.join(base_dir, 'datia', 'runtime', 'ambiguity_incidents.json')
            data = []
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except:
                        data = []
            item = {
                'empresa': empresa,
                'ejercicio': ejercicio,
                'question': question,
                'clarity': clarity,
                'categories': categories,
                'reasons': reasons,
                'suggestions': suggestions,
                'time_ms': time_ms,
                'ts': int(time.time())
            }
            data.append(item)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except:
            pass
        return payload
