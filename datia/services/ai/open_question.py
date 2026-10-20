"""Traduce preguntas de negocio que el catálogo no cubre a un SELECT seguro sobre métricas."""
import logging
import re
import unicodedata

from django.db import connections, transaction

logger = logging.getLogger('query_builder')

_TABLAS_LINEA = (
    'datiadb_lineasalbarancliente',
    'datiadb_cabeceraalbarancliente',
    'datia_articulos',
    'datia_cliente',
)

_TABLAS = (
    'metrics_totales_empresa_ejercicio',
    'metrics_totales_empresa_ejercicio_mes',
    'metrics_totales_empresa_ejercicio_cliente',
    'metrics_totales_empresa_ejercicio_cliente_mes',
    'metrics_totales_empresa_ejercicio_articulo',
    'metrics_totales_empresa_ejercicio_compra',
    'metrics_totales_empresa_ejercicio_compra_mes',
    'metrics_totales_empresa_ejercicio_proveedor',
)

_FUNCIONES = {
    'sum', 'count', 'avg', 'min', 'max', 'coalesce', 'nullif', 'btrim',
    'extract', 'round', 'abs', 'cast', 'ltrim', 'rtrim', 'concat',
}

_SUGERENCIAS = [
    {'label': 'Mejores clientes', 'query': 'mejores clientes'},
    {'label': 'Ventas y compras', 'query': 'ventas y compras'},
    {'label': 'Margen por cliente', 'query': 'margen por cliente'},
    {'label': 'Clientes con margen negativo', 'query': 'clientes con margen negativo'},
]


def _fold(text: str) -> str:
    raw = unicodedata.normalize('NFD', text or '')
    return ''.join(ch for ch in raw if unicodedata.category(ch) != 'Mn').lower()


def _tope(limit) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 10
    if n < 1:
        return 10
    if n > 100:
        return 100
    return n


def _coords(question, empresa, ejercicio):
    years = re.findall(r'\b(20\d{2})\b', question or '')
    try:
        year = int(years[0]) if years else int(ejercicio)
        emp = int(empresa)
    except (TypeError, ValueError):
        return None
    return emp, year


def _sql_listado(tabla, etiqueta, empresa, year, limit, where_extra='', orden='importe_neto_total DESC'):
    filtro = f'empresa = {empresa} AND ejercicio = {year}'
    if where_extra:
        filtro = f'{filtro} AND {where_extra}'
    return (
        f"SELECT {etiqueta} AS label, importe_neto_total AS val, importe_coste_total AS coste, "
        f"albaranes_count AS ops FROM {tabla} WHERE {filtro} "
        f"ORDER BY {orden} LIMIT {limit}"
    )


class OpenQuestion:
    @staticmethod
    def plantilla(question, empresa, ejercicio, limit=10):
        folded = _fold(question)
        coords = _coords(question, empresa, ejercicio)
        if not folded or not coords:
            return None
        if re.search(r'\b(stock|existencia|inventario|kilo|kilos|litros|unidades)\b', folded) and 'margen' not in folded:
            return None
        emp, year = coords
        n = _tope(limit)
        sentido = OpenQuestion.clasificar_deuda(folded)
        if sentido:
            return OpenQuestion._respuesta_deuda(emp, year, sentido, n)
        orden_proveedor = OpenQuestion.clasificar_ranking_proveedor(folded)
        if orden_proveedor:
            return OpenQuestion._respuesta_ranking_proveedor(emp, year, orden_proveedor, n, folded)
        # Un mes o un trimestre ya lo resuelve el constructor de consultas, con su filtro de fechas.
        if re.search(
            r'\b(mensual|por mes|mes a mes|trimestre|trimestral|semestre|semestral|semana|semanal|'
            r'enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b',
            folded,
        ):
            return None
        peor = bool(re.search(r'\b(peor|peores|menor|menores)\b', folded))
        direccion = 'ASC' if peor else 'DESC'

        pide_clientes = bool(re.search(r'\bclientes?\b', folded))
        pide_articulos = bool(re.search(r'\b(articulos?|productos?)\b', folded))
        pide_proveedores = bool(re.search(r'\bproveedores?\b', folded))
        ranking = bool(re.search(r'\b(top|ranking|mejores|mejor|peores|peor|mayores|principales)\b', folded))

        if pide_clientes and pide_articulos and (ranking or 'margen' in folded or 'venta' in folded):
            clientes = _sql_listado(
                'metrics_totales_empresa_ejercicio_cliente',
                "'Cliente: ' || COALESCE(nombre, cliente)",
                emp, year, n,
            )
            articulos = _sql_listado(
                'metrics_totales_empresa_ejercicio_articulo',
                "'Articulo: ' || COALESCE(descripcion, articulo)",
                emp, year, n,
            )
            sql = f'({clientes}) UNION ALL ({articulos})'
            return OpenQuestion._match(sql, 'Clientes y artículos', 'table', year)

        negativo = bool(re.search(
            r'\b(margen negativo|margenes negativos|por debajo del coste|pierden dinero|en perdidas|coste supera)\b',
            folded,
        ))
        if negativo:
            extra = 'importe_neto_total > 0 AND importe_coste_total > importe_neto_total'
            orden = '(importe_coste_total - importe_neto_total) DESC'
            if pide_articulos and not pide_clientes:
                sql = _sql_listado(
                    'metrics_totales_empresa_ejercicio_articulo',
                    'COALESCE(descripcion, articulo)',
                    emp, year, n, extra, orden,
                )
                titulo = 'Artículos con margen negativo'
            elif pide_proveedores and not pide_clientes:
                sql = _sql_listado(
                    'metrics_totales_empresa_ejercicio_proveedor',
                    'COALESCE(nombre, proveedor)',
                    emp, year, n, extra, orden,
                )
                titulo = 'Proveedores con coste por encima de la compra'
            else:
                sql = _sql_listado(
                    'metrics_totales_empresa_ejercicio_cliente',
                    'COALESCE(nombre, cliente)',
                    emp, year, n, extra, orden,
                )
                titulo = 'Clientes con margen negativo'
            return OpenQuestion._match(sql, titulo, 'table', year, nota=OpenQuestion._nota_coste())

        if 'margen' in folded and not re.search(r'\b(mensual|por mes|mes a mes)\b', folded):
            orden = f'(importe_neto_total - importe_coste_total) {direccion}'
            if pide_clientes:
                sql = _sql_listado(
                    'metrics_totales_empresa_ejercicio_cliente',
                    'COALESCE(nombre, cliente)',
                    emp, year, n, 'importe_neto_total <> 0', orden,
                )
                return OpenQuestion._match(sql, f'Margen por cliente {year}', 'table', year, nota=OpenQuestion._nota_coste())
            if pide_articulos:
                sql = _sql_listado(
                    'metrics_totales_empresa_ejercicio_articulo',
                    'COALESCE(descripcion, articulo)',
                    emp, year, n, 'importe_neto_total <> 0', orden,
                )
                return OpenQuestion._match(sql, f'Margen por artículo {year}', 'table', year, nota=OpenQuestion._nota_coste())

        conteo = re.search(
            r'\b(cuantos|cuantas|numero de|cantidad de)\s+(clientes|articulos|productos|proveedores|albaranes)\b',
            folded,
        )
        if conteo:
            cosa = conteo.group(2)
            if cosa in ('articulos', 'productos'):
                tabla = 'metrics_totales_empresa_ejercicio_articulo'
                titulo = f'Artículos con movimiento en {year}'
            elif cosa == 'proveedores':
                tabla = 'metrics_totales_empresa_ejercicio_proveedor'
                titulo = f'Proveedores con compras en {year}'
            elif cosa == 'albaranes':
                sql = (
                    f"SELECT 'Albaranes' AS label, albaranes_count AS registros "
                    f"FROM metrics_totales_empresa_ejercicio WHERE empresa = {emp} AND ejercicio = {year}"
                )
                return OpenQuestion._match(sql, f'Albaranes de venta en {year}', 'conteo', year)
            else:
                tabla = 'metrics_totales_empresa_ejercicio_cliente'
                titulo = f'Clientes con ventas en {year}'
            sql = (
                f"SELECT 'Total' AS label, COUNT(*) AS registros FROM {tabla} "
                f"WHERE empresa = {emp} AND ejercicio = {year} AND importe_neto_total <> 0"
            )
            return OpenQuestion._match(sql, titulo, 'conteo', year)

        if re.search(r'\bventas?\b', folded) and re.search(r'\bcompras?\b', folded):
            sql = (
                f"SELECT 'Ventas' AS label, importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops "
                f"FROM metrics_totales_empresa_ejercicio WHERE empresa = {emp} AND ejercicio = {year} "
                f"UNION ALL "
                f"SELECT 'Compras' AS label, importe_neto_total AS val, importe_coste_total AS coste, albaranes_count AS ops "
                f"FROM metrics_totales_empresa_ejercicio_compra WHERE empresa = {emp} AND ejercicio = {year}"
            )
            return OpenQuestion._match(sql, f'Ventas y compras {year}', 'table', year)

        if re.search(r'\b(margen|coste|costo)\b', folded) and not re.search(
            r'\b(cliente|clientes|articulo|articulos|producto|productos|proveedor|proveedores|mensual|mes)\b',
            folded,
        ):
            sql = (
                f"SELECT 'Ejercicio {year}' AS label, importe_neto_total AS val, importe_coste_total AS coste, "
                f"albaranes_count AS ops FROM metrics_totales_empresa_ejercicio "
                f"WHERE empresa = {emp} AND ejercicio = {year}"
            )
            return OpenQuestion._match(sql, f'Margen y coste {year}', 'card', year, nota=OpenQuestion._nota_coste())
        return None

    @staticmethod
    def responder(question, empresa, ejercicio, limit=10, forzar_modelo=False):
        if not forzar_modelo:
            hit = OpenQuestion.plantilla(question, empresa, ejercicio, limit)
            if hit:
                return hit
        folded = _fold(question)
        if not OpenQuestion._es_de_negocio(folded):
            return OpenQuestion._reply(
                'Puedo responder sobre ventas, compras, clientes, artículos, proveedores, margen, coste y stock de la empresa. '
                'Formula la pregunta con uno de esos datos.'
            )
        coords = _coords(question, empresa, ejercicio)
        if not coords:
            return OpenQuestion._reply('Elige la empresa y el ejercicio antes de preguntar.')
        emp, year = coords
        from datia.services.ai.semantic_plan import SemanticPlan
        tope = _tope(limit)
        plan = None if forzar_modelo else SemanticPlan.desde_frase(question, tope)
        if not plan:
            plan = SemanticPlan.desde_modelo(question, tope)
        sql = SemanticPlan.compilar(plan, emp, year, SemanticPlan.dialecto_actual()) if plan else None
        if not sql:
            return OpenQuestion._reply(
                'No he podido traducir esta pregunta a una consulta sobre las métricas de la empresa. '
                'Prueba nombrando el dato y el corte: clientes, artículos, ventas, compras, margen o coste.'
            )
        filas = OpenQuestion._ejecutar(sql)
        if filas is None:
            return OpenQuestion._reply(
                'He preparado una consulta y la base de métricas la ha rechazado. '
                'Reformula la pregunta con ventas, compras, clientes o artículos del ejercicio.'
            )
        if not filas:
            return OpenQuestion._reply(
                f'No hay datos en {year} para esta pregunta.'
            )
        OpenQuestion._guardar(question, sql, emp, year, plan)
        salida = OpenQuestion._match(sql, 'Consulta sobre métricas', 'table', year, source='open_question')
        salida['plan'] = plan
        return salida

    @staticmethod
    def clasificar_deuda(question: str):
        """C si nos deben (cobro). P si debemos (pago). None si la frase no habla de deuda."""
        folded = _fold(question)
        if not re.search(
            r'\b(deuda|deudas|deben|debe|debemos|impagad\w*|cobrar|pagar)\b|pendiente de cobro|pendiente de pago',
            folded or '',
        ):
            return None
        if re.search(r'\bdebemos\b|pendiente de pago', folded):
            return 'P'
        pago = bool(re.search(r'\b(proveedor|proveedores|acreedor|acreedores|pagar)\b', folded))
        cobro = bool(re.search(r'\b(deben|debe|cliente|clientes|cobrar)\b|pendiente de cobro', folded))
        if pago and not cobro:
            return 'P'
        if cobro or re.search(r'\b(deuda|deudas|impagad\w*)\b', folded):
            return 'C'
        return None

    @staticmethod
    def clasificar_ranking_proveedor(question: str):
        """DESC si pide el proveedor al que más se compra. ASC si pide el que menos. None si no es ese ranking."""
        folded = _fold(question)
        if not folded:
            return None
        if not re.search(r'\b(mas|mayor|mayores|mejor|mejores|top|ranking|peor|peores|menos)\b', folded):
            return None
        proveedor = bool(re.search(r'\bproveedores?\b', folded))
        compra = bool(re.search(r'\bcompr\w*\b|\bgastos?\b', folded))
        quien = bool(re.search(r'\b(a quien|al que|el que|la que)\b', folded))
        if re.search(r'\b(cliente|clientes|venta|ventas)\b', folded) and not (proveedor or compra):
            return None
        if not (proveedor or (compra and quien)):
            return None
        if re.search(r'\b(peor|peores|menos)\b', folded) and not re.search(
            r'\b(mas|mayor|mayores|mejor|mejores|top|ranking)\b', folded,
        ):
            return 'ASC'
        return 'DESC'

    @staticmethod
    def _tope_proveedores(folded, limit):
        pedido = re.search(r'\b(?:top|primeros|primeras|mejores|peores)\s+(\d{1,3})\b', folded or '')
        if pedido:
            return _tope(pedido.group(1))
        if re.search(r'\bproveedores\b', folded or '') and not re.search(r'\b(el|la|al|un)\s+proveedor\b', folded or ''):
            return _tope(limit)
        return 1

    @staticmethod
    def _respuesta_deuda(empresa, year, sentido, limit):
        tipo = 'P' if sentido == 'P' else 'C'
        titulo = 'Pendiente de pago' if tipo == 'P' else 'Pendiente de cobro'
        sujeto = 'proveedores' if tipo == 'P' else 'clientes'
        try:
            filas = OpenQuestion._leer_deuda(empresa, year, tipo)
        except Exception:
            logger.exception('OpenQuestion: no se pudo leer la cartera')
            return OpenQuestion._reply(f'No he podido leer la cartera de {year}.')
        if not filas:
            texto = f'En {year} no hay efectos pendientes de {"pago" if tipo == "P" else "cobro"}.'
            return {
                'reply': {
                    'type': 'text',
                    'text': texto,
                    'answer': texto,
                    'source': 'cartera',
                }
            }
        total = sum(fila['pendiente'] for fila in filas)
        efectos = sum(fila['efectos'] for fila in filas)
        visibles = filas[:limit]
        texto = (
            f"En {year} los {sujeto} tienen un {titulo.lower()} de {OpenQuestion._eur(total)} "
            f"en {efectos} efectos y {len(filas)} cuentas. "
            f"El importe es lo facturado menos lo ya cobrado o pagado, sin efectos liquidados."
        )
        return {
            'reply': {
                'type': 'report',
                'key': 'deuda_proveedores' if tipo == 'P' else 'deuda_clientes',
                'text': texto,
                'answer': texto,
                'source': 'cartera',
                'kpis': [{
                    'label': titulo,
                    'value': round(total, 2),
                    'suffix': '€',
                    'color': '#fbbf24',
                }],
                'table': {
                    'title': f'{titulo} por cuenta',
                    'columns': ['Cuenta', f'{titulo} (€)', 'Efectos'],
                    'rows': [
                        [fila['nombre'], round(fila['pendiente'], 2), fila['efectos']]
                        for fila in visibles
                    ],
                },
            }
        }

    @staticmethod
    def _leer_deuda(empresa, year, tipo):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        sql = """
            SELECT COALESCE(NULLIF(BTRIM(p.descripcion), ''), c.codigo_titular) AS nombre,
                   SUM(c.importe - c.importe_cobrado) AS pendiente,
                   COUNT(*) AS efectos
            FROM datia_financial_cartera c
            LEFT JOIN datia_financial_plan p
              ON p.empresa = c.empresa
             AND p.ejercicio = c.ejercicio
             AND p.codigo = c.codigo_titular
            WHERE c.empresa = %s
              AND c.ejercicio = %s
              AND c.tipo_efecto = %s
              AND COALESCE(c.estado, '') NOT IN ('COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO')
              AND (c.importe - c.importe_cobrado) > 0.01
            GROUP BY c.codigo_titular, p.descripcion
            ORDER BY pendiente DESC
        """
        with connections[alias].cursor() as cur:
            cur.execute(sql, [int(empresa), int(year), tipo])
            rows = cur.fetchall()
        salida = []
        for nombre, pendiente, efectos in rows:
            salida.append({
                'nombre': str(nombre or 'Sin nombre'),
                'pendiente': float(pendiente or 0),
                'efectos': int(efectos or 0),
            })
        return salida

    @staticmethod
    def _respuesta_ranking_proveedor(empresa, year, orden, limit, folded):
        cuantos = OpenQuestion._tope_proveedores(folded, limit)
        try:
            filas = OpenQuestion._leer_ranking_proveedor(empresa, year, orden, cuantos)
        except Exception:
            logger.exception('OpenQuestion: no se pudo leer el ranking de proveedores')
            return OpenQuestion._reply(f'No he podido leer las compras por proveedor de {year}.')
        if not filas:
            texto = f'En {year} no hay compras por proveedor en las métricas.'
            return {'reply': {'type': 'text', 'text': texto, 'answer': texto, 'source': 'metricas_compra'}}
        primero = filas[0]
        sentido = 'menos' if orden == 'ASC' else 'más'
        if cuantos == 1:
            texto = (
                f"En {year} el proveedor al que {sentido} se le compra es {primero['nombre']}, "
                f"con {OpenQuestion._eur(primero['importe'])} en {primero['albaranes']} albaranes."
            )
        else:
            texto = (
                f"En {year} el proveedor al que {sentido} se le compra es {primero['nombre']}, "
                f"con {OpenQuestion._eur(primero['importe'])} en {primero['albaranes']} albaranes. "
                f"El listado muestra {len(filas)} proveedores."
            )
        return {
            'reply': {
                'type': 'report',
                'key': 'ranking_proveedores',
                'text': texto,
                'answer': texto,
                'source': 'metricas_compra',
                'kpis': [{
                    'label': 'Compra',
                    'value': round(primero['importe'], 2),
                    'suffix': '€',
                    'color': '#34d399',
                }],
                'table': {
                    'title': 'Compras por proveedor',
                    'columns': ['Proveedor', 'Compra (€)', 'Albaranes'],
                    'rows': [
                        [fila['nombre'], round(fila['importe'], 2), fila['albaranes']]
                        for fila in filas
                    ],
                },
            }
        }

    @staticmethod
    def _leer_ranking_proveedor(empresa, year, orden, limit):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        sentido = 'ASC' if orden == 'ASC' else 'DESC'
        sql = f"""
            SELECT COALESCE(NULLIF(BTRIM(nombre), ''), proveedor) AS nombre,
                   importe_neto_total,
                   albaranes_count
            FROM metrics_totales_empresa_ejercicio_proveedor
            WHERE empresa = %s
              AND ejercicio = %s
              AND (importe_neto_total <> 0 OR albaranes_count <> 0)
            ORDER BY importe_neto_total {sentido}
            LIMIT %s
        """
        with connections[alias].cursor() as cur:
            cur.execute(sql, [int(empresa), int(year), int(limit)])
            rows = cur.fetchall()
        return [
            {
                'nombre': str(nombre or 'Sin nombre').strip(),
                'importe': float(importe or 0),
                'albaranes': int(albaranes or 0),
            }
            for nombre, importe, albaranes in rows
        ]

    @staticmethod
    def _eur(valor):
        return f"{float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'

    @staticmethod
    def _match(sql, titulo, tipo, year, nota='', source='open_question'):
        clave = 'conteo' if tipo == 'conteo' else 'open_question'
        out = {
            'key': clave,
            'sql': ' '.join(sql.split()),
            'type': 'table' if tipo == 'conteo' else tipo,
            'chart_type': 'bar',
            'label': titulo,
            'keep_label': True,
            'source': source,
            'intent_meta': {'metric': 'sales', 'ejercicio': year, 'title': titulo},
        }
        if nota:
            out['nota'] = nota
        return out

    @staticmethod
    def _nota_coste():
        return (
            'El margen es la venta neta menos el coste agregado. '
            'Si el coste supera la venta, revisa ImporteCoste de las líneas antes de dar la pérdida por buena.'
        )

    @staticmethod
    def _reply(text):
        return {
            'reply': {
                'type': 'text',
                'text': text,
                'answer': text,
                'suggestions': list(_SUGERENCIAS),
            }
        }

    @staticmethod
    def _es_de_negocio(folded: str) -> bool:
        return bool(re.search(
            r'\b(venta|ventas|compra|compras|cliente|clientes|producto|productos|articulo|articulos|'
            r'margen|coste|costo|albaran|albaranes|pedido|pedidos|factura|facturas|stock|proveedor|'
            r'proveedores|tesoreria|presupuesto|saldo|familia|agente|ejercicio|ranking|importe|ticket|'
            r'deuda|cobro|cobros|pago|pagos|facturacion|beneficio|rentabilidad|gasto|gastos|'
            r'vendido|vendidos)\b',
            folded or '',
        ))

    @staticmethod
    def _aceptar(sql, empresa, year):
        text = (sql or '').strip().strip('`')
        text = re.sub(r'^sql\s*', '', text, flags=re.I)
        text = text.split(';')[0].strip()
        if not re.match(r'(?is)^select\b', text):
            return None
        if ';' in text or '--' in text or '/*' in text:
            return None
        if re.search(r'(?i)\b(insert|update|delete|drop|alter|truncate|grant|copy|execute|pg_)\b', text):
            return None
        funciones = re.findall(r'(?i)\b([a-z_][a-z0-9_]*)\s*\(', text)
        if any(nombre.lower() not in _FUNCIONES for nombre in funciones):
            return None
        tablas = [nombre.lower() for nombre in re.findall(r'(?i)\b(?:from|join)\s+([a-z_][a-z0-9_]*)', text)]
        if not tablas:
            return None
        de_lineas = any(nombre in _TABLAS_LINEA for nombre in tablas)
        if de_lineas:
            if any(nombre not in _TABLAS_LINEA for nombre in tablas):
                return None
            if re.search(r'(?i)\b(importeneto|precio)\b', text) is None:
                return None
            if not re.search(rf'(?i)\bcodigoempresa\s*=\s*{int(empresa)}\b', text):
                return None
            if not re.search(rf'(?i)\bejercicioalbaran\s*=\s*{int(year)}\b', text):
                return None
        else:
            if re.search(r'(?i)\b(importeneto|datiadb_)\b', text):
                return None
            if any(nombre not in _TABLAS for nombre in tablas):
                return None
            if not re.search(rf'(?i)\bempresa\s*=\s*{int(empresa)}\b', text):
                return None
            if not re.search(rf'(?i)\bejercicio\s*=\s*{int(year)}\b', text):
                return None
        if not re.search(r'(?i)\bas\s+label\b', text) or not re.search(r'(?i)\bas\s+(val|registros)\b', text):
            return None
        if not re.search(r'(?i)\blimit\s+\d+\b', text):
            text = f'{text} LIMIT 100'
        else:
            def _bajar(match):
                n = int(match.group(1))
                return f'LIMIT {min(n, 100)}'
            text = re.sub(r'(?i)\blimit\s+(\d+)\b', _bajar, text)
        return ' '.join(text.split())

    @staticmethod
    def _ejecutar(sql):
        from datia.services.security.sql_guard import SQLGuard
        try:
            SQLGuard.ensure_allowed(sql)
        except PermissionError:
            logger.info('OpenQuestion: SQL fuera de las tablas permitidas')
            return None
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        try:
            with transaction.atomic(using=alias):
                with connections[alias].cursor() as cur:
                    if connections[alias].vendor == 'postgresql':
                        cur.execute("SET LOCAL statement_timeout = 8000")
                    cur.execute(sql)
                    if not cur.description:
                        return []
                    cols = [c[0] for c in cur.description]
                    return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception:
            logger.exception('OpenQuestion: la consulta no se pudo ejecutar')
            return None

    @staticmethod
    def _guardar(question, sql, empresa, year, plan=None):
        try:
            from datia.factories import ServiceFactory
            ServiceFactory.get_embedding_service().learn_template(
                text=question,
                sql=sql,
                type='table',
                label='Consulta abierta',
                empresa=empresa,
                ejercicio=year,
                scope='learned',
                plan=plan,
            )
        except Exception:
            logger.exception('OpenQuestion: no se pudo guardar la consulta')
