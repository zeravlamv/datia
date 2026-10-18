"""Cuando ninguna regla conoce la pregunta, el modelo local escribe un SELECT, se comprueba y se guarda."""
import logging
import re
from decimal import Decimal

from django.db import connections

logger = logging.getLogger('query_builder')

_TABLAS = (
    'metrics_totales_empresa_ejercicio',
    'metrics_totales_empresa_ejercicio_mes',
    'metrics_totales_empresa_ejercicio_cliente',
    'metrics_totales_empresa_ejercicio_cliente_mes',
    'metrics_totales_empresa_ejercicio_articulo',
)

_CATALOGO = """
Tablas de Postgres. Los importes ya están calculados. No inventes columnas.
- metrics_totales_empresa_ejercicio(empresa, ejercicio, importe_neto_total, importe_coste_total, albaranes_count)
- metrics_totales_empresa_ejercicio_mes(empresa, ejercicio, mes, importe_neto_total, importe_coste_total, albaranes_count)
- metrics_totales_empresa_ejercicio_cliente(empresa, ejercicio, cliente, nombre, importe_neto_total, importe_coste_total, albaranes_count)
- metrics_totales_empresa_ejercicio_cliente_mes(empresa, ejercicio, cliente, mes, nombre, importe_neto_total, importe_coste_total, albaranes_count)
- metrics_totales_empresa_ejercicio_articulo(empresa, ejercicio, articulo, descripcion, importe_neto_total, importe_coste_total, albaranes_count)

importe_neto_total es la venta neta. El margen es importe_neto_total menos importe_coste_total.
El nombre del cliente está en nombre. La descripción del artículo está en descripcion. mes es 1..12.
Filtra empresa = {empresa} y ejercicio = {ejercicio}.
Una sola SELECT. Alias obligatorios: label, val, coste, ops.
val es importe_neto_total. coste es importe_coste_total. ops es albaranes_count.
Si piden uno solo (el mejor, el más, cuál), ORDER BY val DESC LIMIT 1.
No uses otras tablas. No uses importeneto. Devuelve solo el SQL.
"""


class AutoLearn:
    @staticmethod
    def aprender(question: str, empresa, ejercicio):
        try:
            empresa_id = int(empresa)
            target_year = int(ejercicio)
        except (TypeError, ValueError):
            return None
        texto = (question or '').strip()
        if len(texto) < 4:
            return None
        sql = AutoLearn._pedir_sql(texto, empresa_id, target_year)
        sql = AutoLearn._aceptar(sql, empresa_id, target_year)
        if not sql or not AutoLearn._tiene_cifra(sql):
            logger.info('AutoLearn: la consulta nueva no produjo un SQL usable')
            return None
        AutoLearn._guardar(texto, sql, empresa_id, target_year)
        logger.info('AutoLearn: consulta aprendida y guardada')
        return {
            'key': 'auto_learn',
            'sql': sql,
            'type': 'table',
            'chart_type': 'bar',
            'label': 'Consulta aprendida',
            'keep_label': True,
            'source': 'auto_learn',
            'intent_meta': {'metric': 'sales', 'ejercicio': target_year, 'title': 'Consulta aprendida'},
        }

    @staticmethod
    def _pedir_sql(question: str, empresa_id: int, target_year: int):
        try:
            from datia.services.ollama_service import OllamaService
            prompt = (
                'Eres un experto en Postgres. Responde solo con un SELECT.\n'
                + _CATALOGO.format(empresa=empresa_id, ejercicio=target_year)
                + f'\nPregunta: {question}\nSQL:'
            )
            texto = OllamaService().generate_text(
                prompt,
                timeout=45,
                model='qwen2.5:3b-instruct-q4_k_m',
                stream=False,
                options={'temperature': 0, 'num_predict': 160},
            )
        except Exception:
            logger.warning('AutoLearn: el modelo local no contestó a tiempo')
            return None
        found = re.search(r'(?is)\bselect\b.+', texto or '')
        if not found:
            return None
        return found.group(0).strip()

    @staticmethod
    def _aceptar(sql, empresa_id: int, target_year: int):
        text = (sql or '').strip()
        text = text.split(';')[0].strip()
        if not re.match(r'(?is)^select\b', text):
            return None
        if ';' in text or '--' in text or '/*' in text:
            return None
        if re.search(r'(?i)\b(insert|update|delete|drop|alter|truncate|grant|copy|execute|importeneto|datiadb_)\b', text):
            return None
        tablas = re.findall(r'(?i)\b(?:from|join)\s+([a-z_][a-z0-9_]*)', text)
        if not tablas or any(nombre.lower() not in _TABLAS for nombre in tablas):
            return None
        if not re.search(rf'(?i)\bempresa\s*=\s*{empresa_id}\b', text):
            return None
        if not re.search(rf'(?i)\bejercicio\s*=\s*{target_year}\b', text):
            return None
        if not re.search(r'(?i)\bimporte_neto_total\b', text):
            return None
        return ' '.join(text.split())

    @staticmethod
    def _tiene_cifra(sql: str) -> bool:
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        try:
            with connections[alias].cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
        except Exception:
            logger.exception('AutoLearn: el SQL aprendido no se pudo ejecutar')
            return False
        if not row:
            return False
        for value in row:
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float, Decimal)) and value is not None:
                return True
        return False

    @staticmethod
    def _guardar(question: str, sql: str, empresa_id: int, target_year: int):
        try:
            from datia.factories import ServiceFactory
            ServiceFactory.get_embedding_service().learn_template(
                text=question,
                sql=sql,
                type='table',
                label='Consulta aprendida',
                empresa=empresa_id,
                ejercicio=target_year,
                scope='learned',
            )
        except Exception:
            logger.exception('AutoLearn: no se pudo guardar la consulta aprendida')
