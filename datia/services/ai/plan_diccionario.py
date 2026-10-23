"""Plan cerrado. Lee el diccionario, rellena los huecos y lee la cifra en Postgres."""
import logging
import re
import unicodedata

from django.db import connections

from datia.services.ai.diccionario import operaciones
from datia.services.ai.presentacion import barras, origen, variacion

logger = logging.getLogger('datia')

NEGATIVA = 'El dato no está cargado.'

_TABLAS = {ficha['frase']: ficha['tabla'] for ficha in operaciones()}
_PERMITIDAS = {
    'metrics_totales_empresa_ejercicio_mes',
    'metrics_totales_empresa_ejercicio_compra_mes',
    'datia_financial_cartera',
    'datia_financial_acumulados',
}
_NO_CABE_EN_TRIMESTRE = (
    'cliente', 'clientes', 'articulo', 'articulos', 'producto', 'productos',
    'proveedor', 'proveedores', 'familia', 'familias', 'agente', 'agentes',
    'almacen', 'almacenes', 'cuenta', 'cuentas', 'efecto', 'efectos', 'factura', 'facturas', 'grupo',
)
_NO_CABE_EN_GRUPO = (
    'cliente', 'clientes', 'articulo', 'articulos', 'producto', 'productos',
    'proveedor', 'proveedores', 'efecto', 'efectos', 'factura', 'facturas',
)


def _fold(text):
    raw = unicodedata.normalize('NFD', text or '')
    raw = ''.join(ch for ch in raw if unicodedata.category(ch) != 'Mn')
    raw = raw.lower().replace('ñ', 'n')
    raw = re.sub(r'[^a-z0-9]+', ' ', raw)
    return re.sub(r'\s+', ' ', raw).strip()


def _ejercicio(question, ejercicio):
    years = re.findall(r'\b(20\d{2})\b', question or '')
    try:
        return int(years[0]) if years else int(ejercicio)
    except (TypeError, ValueError):
        return None


def _tope(texto, limit):
    pedido = re.search(r'\b(?:los|las|top|primeros|primeras)\s+(\d{1,3})\b', texto or '')
    if not pedido:
        pedido = re.search(r'\b(\d{1,3})\s+efectos\b', texto or '')
    try:
        n = int(pedido.group(1) if pedido else limit)
    except (TypeError, ValueError):
        n = 10
    if n < 1 or n > 100:
        return 10
    return n


def _tabla(frase):
    tabla = _TABLAS.get(frase)
    if tabla in _PERMITIDAS:
        return tabla
    return None


def _alias():
    return 'analytics' if 'analytics' in connections.databases else 'default'


def _euros(valor):
    return f"{float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'


_FALTAS = {
    'factura': (
        'datia_financial_cartera',
        'No hay columna de factura. La cartera guarda el efecto: titular, importe, importe cobrado y estado.',
    ),
    'sentido': (
        'datia_financial_cartera',
        'Falta decir si el efecto es de cobro o de pago.',
    ),
    'cifra': (
        'metrics_totales_empresa_ejercicio_mes',
        'Falta decir si la cifra es de ventas o de compras.',
    ),
    'entidad': (
        '',
        'Ese corte no está cargado para un cliente, un artículo o un proveedor.',
    ),
    'grupo': (
        'datia_financial_acumulados',
        'Falta el número del grupo de cuentas.',
    ),
}


def _negativa(motivo=''):
    tabla, falta = _FALTAS.get(motivo, ('', 'El dato pedido no está en las columnas cargadas.'))
    return {
        'reply': {
            'type': 'text',
            'text': NEGATIVA,
            'answer': NEGATIVA,
            'source': 'plan',
            'dato_no_cargado': True,
            'origen': origen(tabla, '', [], falta=falta),
        }
    }


def _elige_empresa():
    texto = 'Elige la empresa y el ejercicio antes de preguntar.'
    return {'reply': {'type': 'text', 'text': texto, 'answer': texto, 'source': 'plan'}}


def encajar(question, ejercicio=None, limit=10):
    """Huecos de la pregunta. None si no es una operación del diccionario."""
    folded = _fold(question)
    if not folded:
        return None
    year = _ejercicio(question, ejercicio)

    if re.search(r'\bfacturas?\b', folded) and re.search(r'\b(pendient\w*|cobr\w*|pag\w*|impagad\w*)\b', folded):
        return {'negativa': True, 'motivo': 'factura'}

    if re.search(r'\befectos?\b', folded):
        pago = bool(re.search(r'\b(pago|pagos|pagar)\b', folded))
        cobro = bool(re.search(r'\b(cobro|cobros|cobrar)\b', folded))
        if pago == cobro:
            return {'negativa': True, 'motivo': 'sentido'}
        if re.search(r'\b(cuantos|cuantas|numero|cantidad)\b', folded):
            modo = 'conteo'
        elif re.search(r'\b(lista|listado|muestra|mostrar|ensenar)\b', folded):
            modo = 'lista'
        else:
            modo = 'importe'
        titular = ''
        hallado = re.search(r'\bde (?:pago|cobro) de (.+)$', folded)
        if hallado:
            titular = re.sub(r'\b(de\s+)?mayor importe\b', ' ', hallado.group(1))
            titular = re.sub(r'\b(por importe|ordenados?|ordenadas?)\b', ' ', titular)
            titular = re.sub(r'\s+', ' ', titular).strip()
        return {
            'operacion': 'efectos pendientes de cobro o de pago',
            'sentido': 'P' if pago else 'C',
            'modo': modo,
            'titular': titular,
            'limite': _tope(folded, limit),
            'ejercicio': year,
        }

    if re.search(r'\bsaldos?\b', folded) and re.search(r'\bgrupo\b', folded):
        if any(re.search(rf'\b{nombre}\b', folded) for nombre in _NO_CABE_EN_GRUPO):
            return {'negativa': True, 'motivo': 'entidad'}
        hallado = re.search(r'\bgrupo\s+([0-9]{1,2})\b', folded)
        if not hallado:
            return {'negativa': True, 'motivo': 'grupo'}
        desde, hasta, corte = _corte_grupo(folded)
        return {
            'operacion': 'saldo de un grupo de cuentas',
            'grupo': hallado.group(1),
            'desde': desde,
            'hasta': hasta,
            'corte': corte,
            'ejercicio': year,
        }

    if re.search(r'\btrimestres?\b|\btrimestrales?\b|\btrimestral\b', folded):
        venta = bool(re.search(r'\b(ventas?|facturacion)\b', folded))
        compra = bool(re.search(r'\bcompras?\b', folded))
        if venta == compra:
            return {'negativa': True, 'motivo': 'cifra'}
        if any(re.search(rf'\b{nombre}\b', folded) for nombre in _NO_CABE_EN_TRIMESTRE):
            return {'negativa': True, 'motivo': 'entidad'}
        frase = 'ventas por trimestre' if venta else 'compras por trimestre'
        return {'operacion': frase, 'corte': 'trimestre', 'ejercicio': year}
    return None


def _corte_grupo(folded):
    """Meses del grupo. El último trimestre son octubre, noviembre y diciembre."""
    if re.search(r'\bultim[oa]s?\s+trimestres?\b', folded):
        return 10, 12, 'último trimestre'
    ordinales = {
        'primer': 1, 'primero': 1, 'segundo': 2, 'tercer': 3, 'tercero': 3, 'cuarto': 4,
    }
    hallado = re.search(r'\b(primer|primero|segundo|tercer|tercero|cuarto)\s+trimestre\b', folded)
    numero = ordinales.get(hallado.group(1)) if hallado else None
    if numero is None:
        suelto = re.search(r'\btrimestre\s+([1-4])\b', folded)
        numero = int(suelto.group(1)) if suelto else None
    if numero:
        desde = (numero - 1) * 3 + 1
        return desde, desde + 2, f'trimestre {numero}'
    return 1, 12, 'enero a diciembre'


def responder(question, empresa, ejercicio, limit=10):
    """Cifra real, o la negativa única. None si la pregunta sigue por las otras reglas."""
    ficha = encajar(question, ejercicio, limit)
    if not ficha:
        return None
    if ficha.get('negativa') or ficha.get('ejercicio') is None:
        if ficha.get('ejercicio') is None and not ficha.get('negativa'):
            return _elige_empresa()
        if ficha.get('negativa'):
            return _negativa(ficha.get('motivo') or '')
    try:
        empresa_id = int(empresa)
    except (TypeError, ValueError):
        return _elige_empresa()
    tabla = _tabla(ficha['operacion'])
    if not tabla:
        return _negativa()
    try:
        if ficha['operacion'] in ('ventas por trimestre', 'compras por trimestre'):
            return _trimestre(tabla, empresa_id, ficha)
        if ficha['operacion'] == 'efectos pendientes de cobro o de pago':
            return _efectos(tabla, empresa_id, ficha)
        if ficha['operacion'] == 'saldo de un grupo de cuentas':
            return _grupo(tabla, empresa_id, ficha)
    except Exception:
        logger.exception('Plan: no se pudo leer %s', ficha.get('operacion'))
        return _negativa()
    return _negativa()


def _leer_trimestre(tabla, empresa, year):
    with connections[_alias()].cursor() as cur:
        cur.execute(
            f'''
            SELECT ((mes - 1) / 3) + 1 AS trimestre, SUM(importe_neto_total) AS neto
            FROM {tabla}
            WHERE empresa = %s AND ejercicio = %s
            GROUP BY 1
            ORDER BY 1
            ''',
            [empresa, year],
        )
        return [(int(trimestre), float(neto or 0)) for trimestre, neto in cur.fetchall()]


def _consulta_trimestre(tabla, empresa, year):
    return (
        f'SELECT ((mes - 1) / 3) + 1 AS trimestre, SUM(importe_neto_total) AS neto '
        f'FROM {tabla} WHERE empresa = {int(empresa)} AND ejercicio = {int(year)} '
        f'GROUP BY 1 ORDER BY 1'
    )


def _trimestre(tabla, empresa, ficha):
    year = ficha['ejercicio']
    titulo = 'Ventas' if 'ventas' in ficha['operacion'] else 'Compras'
    filas = _leer_trimestre(tabla, empresa, year)
    anteriores = _leer_trimestre(tabla, empresa, year - 1)
    consulta = _consulta_trimestre(tabla, empresa, year)
    if anteriores:
        consulta = consulta + ' ; ' + _consulta_trimestre(tabla, empresa, year - 1)
    formula = (
        'Suma del importe neto de los meses de cada trimestre. '
        'El trimestre 1 reúne enero, febrero y marzo.'
    )
    filtros = [f'Empresa {empresa}', f'Ejercicio {year}']
    if not filas:
        texto = f'En {year} no hay {titulo.lower()} por trimestre cargadas.'
        return {
            'reply': {
                'type': 'text',
                'text': texto,
                'answer': texto,
                'source': 'plan',
                'origen': origen(tabla, formula, filtros, consulta),
            }
        }
    total = sum(neto for _trimestre, neto in filas)
    total_anterior = sum(neto for _trimestre, neto in anteriores)
    mejor = max(filas, key=lambda fila: fila[1])
    detalle = ', '.join(f'T{trimestre} {_euros(neto)}' for trimestre, neto in filas)
    texto = f'{titulo} por trimestre de {year}. {detalle}. Total {_euros(total)}.'
    serie_actual = {
        'label': str(year),
        'data': [round(dict(filas).get(n, 0), 2) for n in (1, 2, 3, 4)],
        'color': '#60a5fa',
    }
    series = [serie_actual]
    if anteriores:
        filtros.append(f'Comparado con {year - 1}')
        series.append({
            'label': str(year - 1),
            'data': [round(dict(anteriores).get(n, 0), 2) for n in (1, 2, 3, 4)],
            'color': '#94a3b8',
        })
    tarjeta_total = {
        'label': f'{titulo} {year}',
        'value': round(total, 2),
        'suffix': '€',
        'color': '#60a5fa',
    }
    cambio = variacion(total, total_anterior, year - 1) if anteriores else ''
    if cambio:
        tarjeta_total['change'] = cambio
    return {
        'reply': {
            'type': 'report',
            'text': texto,
            'answer': texto,
            'source': 'plan',
            'kpis': [
                tarjeta_total,
                {
                    'label': 'Trimestre más alto',
                    'value': round(mejor[1], 2),
                    'suffix': '€',
                    'color': '#34d399',
                    'change': f'T{mejor[0]}',
                },
            ],
            'chart_config': barras([f'T{n}' for n in (1, 2, 3, 4)], series),
            'table': {
                'title': f'{titulo} por trimestre {year}',
                'columns': ['Trimestre', 'Importe neto (€)'],
                'rows': [[f'T{trimestre}', round(neto, 2)] for trimestre, neto in filas],
            },
            'origen': origen(tabla, formula, filtros, consulta),
        }
    }


def _filtro_efecto():
    return (
        "COALESCE(estado, '') NOT IN ('COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO') "
        "AND (importe - importe_cobrado) > 0.01"
    )


def _consulta_efectos(tabla, empresa, year, sentido):
    return (
        f'SELECT (importe - importe_cobrado) AS pendiente FROM {tabla} '
        f'WHERE empresa = {int(empresa)} AND ejercicio = {int(year)} '
        f"AND tipo_efecto = '{sentido}' AND {_filtro_efecto()}"
    )


def _suma_efectos(tabla, empresa, year, sentido):
    with connections[_alias()].cursor() as cur:
        cur.execute(
            f'''
            SELECT COUNT(*), COALESCE(SUM(importe - importe_cobrado), 0)
            FROM {tabla}
            WHERE empresa = %s
              AND ejercicio = %s
              AND tipo_efecto = %s
              AND COALESCE(estado, '') NOT IN ('COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO')
              AND (importe - importe_cobrado) > 0.01
            ''',
            [empresa, year, sentido],
        )
        cuenta, total = cur.fetchone()
    return int(cuenta or 0), float(total or 0)


def _efectos(tabla, empresa, ficha):
    year = ficha['ejercicio']
    sentido = ficha['sentido']
    lado = 'pago' if sentido == 'P' else 'cobro'
    with connections[_alias()].cursor() as cur:
        cur.execute(
            f'''
            SELECT COALESCE(NULLIF(BTRIM(p.descripcion), ''), c.codigo_titular) AS nombre,
                   (c.importe - c.importe_cobrado) AS pendiente,
                   c.fecha_vencimiento
            FROM {tabla} c
            LEFT JOIN datia_financial_plan p
              ON p.empresa = c.empresa
             AND p.ejercicio = c.ejercicio
             AND p.codigo = c.codigo_titular
            WHERE c.empresa = %s
              AND c.ejercicio = %s
              AND c.tipo_efecto = %s
              AND COALESCE(c.estado, '') NOT IN ('COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO')
              AND (c.importe - c.importe_cobrado) > 0.01
            ORDER BY pendiente DESC
            ''',
            [empresa, year, sentido],
        )
        filas = [
            {
                'nombre': str(nombre or 'Sin nombre').strip(),
                'pendiente': float(pendiente or 0),
                'vence': vence.isoformat() if hasattr(vence, 'isoformat') else '',
            }
            for nombre, pendiente, vence in cur.fetchall()
        ]
    titular = ficha.get('titular') or ''
    if titular:
        buscado = _fold(titular)
        filas = [fila for fila in filas if _fold(fila['nombre']) == buscado]
    cuenta_anterior, total_anterior = (0, 0.0)
    if not titular:
        cuenta_anterior, total_anterior = _suma_efectos(tabla, empresa, year - 1, sentido)
    formula = (
        'Pendiente = importe − importe cobrado. '
        'Quedan fuera los efectos cobrados, pagados, liquidados o anulados.'
    )
    filtros = [f'Empresa {empresa}', f'Ejercicio {year}', f'Tipo {sentido} ({lado})']
    if titular:
        filtros.append(f'Titular {titular}')
    consulta = _consulta_efectos(tabla, empresa, year, sentido)
    dato_origen = origen(tabla, formula, filtros, consulta)
    if not filas:
        texto = f'En {year} no hay efectos pendientes de {lado}.'
        if titular:
            texto = f'En {year} no hay efectos pendientes de {lado} de {titular}.'
        return {
            'reply': {
                'type': 'text',
                'text': texto,
                'answer': texto,
                'source': 'plan',
                'kpis': [{'label': 'Efectos', 'value': 0}],
                'origen': dato_origen,
            }
        }
    total = sum(fila['pendiente'] for fila in filas)
    if ficha['modo'] == 'conteo':
        texto = f'En {year} hay {len(filas)} efectos pendientes de {lado}.'
        tarjeta = {'label': 'Efectos', 'value': len(filas), 'color': '#60a5fa'}
        cambio = variacion(len(filas), cuenta_anterior, year - 1) if cuenta_anterior else ''
        if cambio:
            tarjeta['change'] = cambio
            filtros.append(f'Comparado con {year - 1}')
        grafico = None
        if cuenta_anterior:
            grafico = barras(
                [str(year - 1), str(year)],
                [{'label': 'Efectos', 'data': [cuenta_anterior, len(filas)], 'color': '#60a5fa'}],
                suffix='',
            )
        reply = {
            'type': 'report',
            'text': texto,
            'answer': texto,
            'source': 'plan',
            'kpis': [tarjeta],
            'origen': origen(tabla, formula, filtros, consulta),
        }
        if grafico:
            reply['chart_config'] = grafico
        return {'reply': reply}
    if ficha['modo'] == 'lista':
        visibles = filas[:ficha['limite']]
        texto = (
            f'En {year} estos son los {len(visibles)} efectos pendientes de {lado} de mayor importe.'
        )
        tarjeta = {
            'label': 'Pendiente',
            'value': round(total, 2),
            'suffix': '€',
            'color': '#fbbf24',
        }
        cambio = variacion(total, total_anterior, year - 1) if total_anterior else ''
        if cambio:
            tarjeta['change'] = cambio
            filtros.append(f'Comparado con {year - 1}')
            dato_origen = origen(tabla, formula, filtros, consulta)
        return {
            'reply': {
                'type': 'report',
                'text': texto,
                'answer': texto,
                'source': 'plan',
                'kpis': [tarjeta],
                'chart_config': barras(
                    [fila['nombre'] for fila in visibles],
                    [{
                        'label': f'Pendiente de {lado}',
                        'data': [fila['pendiente'] for fila in visibles],
                        'color': '#fbbf24',
                    }],
                    horizontal=True,
                ),
                'table': {
                    'title': f'Efectos pendientes de {lado}',
                    'columns': ['Titular', 'Pendiente (€)', 'Vencimiento'],
                    'rows': [
                        [fila['nombre'], round(fila['pendiente'], 2), fila['vence']]
                        for fila in visibles
                    ],
                },
                'origen': dato_origen,
            }
        }
    texto = f'En {year} el importe pendiente de {lado} es {_euros(total)} en {len(filas)} efectos.'
    tarjeta = {
        'label': f'Pendiente de {lado}',
        'value': round(total, 2),
        'suffix': '€',
        'color': '#fbbf24',
    }
    cambio = variacion(total, total_anterior, year - 1) if total_anterior else ''
    if cambio:
        tarjeta['change'] = cambio
        filtros.append(f'Comparado con {year - 1}')
    grafico = None
    if total_anterior:
        grafico = barras(
            [str(year - 1), str(year)],
            [{'label': f'Pendiente de {lado}', 'data': [total_anterior, total], 'color': '#fbbf24'}],
        )
    reply = {
        'type': 'report',
        'text': texto,
        'answer': texto,
        'source': 'plan',
        'kpis': [tarjeta],
        'origen': origen(tabla, formula, filtros, consulta),
    }
    if grafico:
        reply['chart_config'] = grafico
    return {'reply': reply}


_MESES = (
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)


def _leer_grupo(tabla, empresa, year, grupo, desde, hasta):
    with connections[_alias()].cursor() as cur:
        cur.execute(
            f'''
            SELECT periodo, COALESCE(SUM(saldo), 0)
            FROM {tabla}
            WHERE empresa = %s
              AND ejercicio = %s
              AND periodo BETWEEN %s AND %s
              AND cuenta LIKE %s
            GROUP BY periodo
            ORDER BY periodo
            ''',
            [empresa, year, desde, hasta, f'{grupo}%'],
        )
        meses = {int(periodo): float(saldo or 0) for periodo, saldo in cur.fetchall()}
        cur.execute(
            f'''
            SELECT COUNT(DISTINCT cuenta)
            FROM {tabla}
            WHERE empresa = %s
              AND ejercicio = %s
              AND periodo BETWEEN %s AND %s
              AND cuenta LIKE %s
            ''',
            [empresa, year, desde, hasta, f'{grupo}%'],
        )
        cuentas = int(cur.fetchone()[0] or 0)
    return meses, cuentas


def _grupo(tabla, empresa, ficha):
    year = ficha['ejercicio']
    grupo = ficha['grupo']
    desde = int(ficha.get('desde') or 1)
    hasta = int(ficha.get('hasta') or 12)
    corte = ficha.get('corte') or 'enero a diciembre'
    meses, cuentas = _leer_grupo(tabla, empresa, year, grupo, desde, hasta)
    if not cuentas:
        return {
            'reply': {
                'type': 'text',
                'text': NEGATIVA,
                'answer': NEGATIVA,
                'source': 'plan',
                'dato_no_cargado': True,
                'origen': origen(
                    tabla,
                    '',
                    [f'Empresa {empresa}', f'Ejercicio {year}', f'Grupo {grupo}', corte],
                    falta=f'No hay saldo cargado del grupo {grupo} en {year}, {corte}.',
                ),
            }
        }
    anteriores, cuentas_anterior = _leer_grupo(tabla, empresa, year - 1, grupo, desde, hasta)
    saldo = sum(meses.values())
    saldo_anterior = sum(anteriores.values())
    tramo = _MESES[desde] if desde == hasta else f'{_MESES[desde]} a {_MESES[hasta]}'
    consulta = (
        f'SELECT periodo, SUM(saldo) FROM {tabla} WHERE empresa = {int(empresa)} '
        f'AND ejercicio = {int(year)} AND periodo BETWEEN {desde} AND {hasta} '
        f"AND cuenta LIKE '{grupo}%' GROUP BY periodo ORDER BY periodo"
    )
    formula = (
        'Suma del saldo, que es el debe menos el haber, de las cuentas cuyo código '
        f'empieza por {grupo}, de {tramo}.'
    )
    filtros = [f'Empresa {empresa}', f'Ejercicio {year}', f'Grupo {grupo}', corte]
    texto = (
        f'Saldo del grupo {grupo} en {year}, {corte}: {_euros(saldo)}. '
        f'Es la suma del debe menos el haber de {cuentas} cuentas, de {tramo}.'
    )
    tarjeta = {
        'label': f'Saldo grupo {grupo}',
        'value': round(saldo, 2),
        'suffix': '€',
        'color': '#60a5fa',
    }
    anio_entero = desde == 1 and hasta == 12
    if anio_entero and cuentas_anterior:
        etiquetas = [str(year - 1), str(year)]
        series = [{
            'label': f'Grupo {grupo}',
            'data': [round(saldo_anterior, 2), round(saldo, 2)],
            'color': '#60a5fa',
        }]
    else:
        periodos = list(range(desde, hasta + 1))
        etiquetas = periodos
        series = [{
            'label': str(year),
            'data': [round(meses.get(periodo, 0), 2) for periodo in periodos],
            'color': '#60a5fa',
        }]
        if cuentas_anterior:
            series.append({
                'label': str(year - 1),
                'data': [round(anteriores.get(periodo, 0), 2) for periodo in periodos],
                'color': '#94a3b8',
            })
    if cuentas_anterior:
        filtros.append(f'Comparado con {year - 1}')
        cambio = variacion(saldo, saldo_anterior, year - 1)
        if cambio:
            tarjeta['change'] = cambio
    return {
        'reply': {
            'type': 'report',
            'text': texto,
            'answer': texto,
            'source': 'plan',
            'kpis': [tarjeta],
            'chart_config': barras(etiquetas, series),
            'origen': origen(tabla, formula, filtros, consulta),
        }
    }
