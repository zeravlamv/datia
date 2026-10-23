"""Gráfico, tarjetas y origen que el chat ya sabe pintar."""
import re


def variacion(actual, anterior, year_prev):
    """Texto «vs 2024: +3,2 %». Vacío si el año anterior no tiene cifra."""
    try:
        base = float(anterior)
        ahora = float(actual)
    except (TypeError, ValueError):
        return ''
    if base == 0:
        return ''
    pct = (ahora - base) / abs(base) * 100.0
    if abs(pct) > 300:
        return ''
    signo = '+' if pct > 0 else ''
    texto = f'{signo}{pct:.1f}'.replace('.', ',')
    return f'vs {year_prev}: {texto} %'


def barras(etiquetas, series, horizontal=False, suffix=' €'):
    """Serie de barras. Las etiquetas de trimestre van como T1 para no volverse meses."""
    return {
        'type': 'bar',
        'indexAxis': 'y' if horizontal else 'x',
        'suffix': suffix,
        'data': {
            'labels': [str(etiqueta) for etiqueta in etiquetas],
            'datasets': [
                {
                    'label': serie['label'],
                    'data': [round(float(valor), 2) for valor in serie['data']],
                    'backgroundColor': serie.get('color', '#60a5fa'),
                    'borderColor': serie.get('color', '#60a5fa'),
                }
                for serie in series
            ],
        },
    }


def origen(tabla, formula, filtros, consulta='', falta=''):
    dato = {
        'tabla': tabla or '',
        'formula': formula or '',
        'filtros': [str(filtro) for filtro in (filtros or []) if filtro],
        'consulta': ' '.join((consulta or '').split()),
    }
    if falta:
        dato['falta'] = falta
    return dato


_SIN_ORIGEN = {'ambiguity_alert', 'training_ask'}

# Informes del catálogo: no llevan SQL en la respuesta, pero la cifra sale de una tabla concreta.
_FICHAS = {
    'ventas_top_productos': (
        'metrics_totales_empresa_ejercicio_articulo',
        'Importe neto de cada artículo, de mayor a menor. Margen = venta neta − coste. '
        'Las barras de años son el total de ventas de la empresa, en metrics_totales_empresa_ejercicio.',
        'SELECT descripcion, articulo, importe_neto_total, importe_coste_total, albaranes_count '
        'FROM metrics_totales_empresa_ejercicio_articulo '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY importe_neto_total DESC',
    ),
    'ventas_top_clientes': (
        'metrics_totales_empresa_ejercicio_cliente',
        'Importe neto de cada cliente, de mayor a menor. Margen = venta neta − coste. '
        'Las barras de años son el total de ventas de la empresa.',
        'SELECT nombre, cliente, importe_neto_total, importe_coste_total, albaranes_count '
        'FROM metrics_totales_empresa_ejercicio_cliente '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY importe_neto_total DESC',
    ),
    'ventas_resumen': (
        'metrics_totales_empresa_ejercicio',
        'Importe neto de ventas del ejercicio. El gráfico mensual sale de metrics_totales_empresa_ejercicio_mes.',
        'SELECT importe_neto_total FROM metrics_totales_empresa_ejercicio '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio}',
    ),
    'ventas_mensual': (
        'metrics_totales_empresa_ejercicio_mes',
        'Importe neto de ventas de cada mes, comparado con el mismo mes del año anterior.',
        'SELECT mes, importe_neto_total FROM metrics_totales_empresa_ejercicio_mes '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY mes',
    ),
    'margen_mensual': (
        'metrics_totales_empresa_ejercicio_mes',
        'Margen del mes = (importe neto − coste) / importe neto.',
        'SELECT mes, importe_neto_total, importe_coste_total FROM metrics_totales_empresa_ejercicio_mes '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY mes',
    ),
    'ventas_rango_periodos': (
        'metrics_totales_empresa_ejercicio_mes',
        'Suma del importe neto de los meses pedidos, comparada con el año anterior.',
        'SELECT mes, importe_neto_total FROM metrics_totales_empresa_ejercicio_mes '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY mes',
    ),
    'compras_resumen': (
        'metrics_totales_empresa_ejercicio_compra',
        'Importe neto de compras del ejercicio. El gráfico mensual sale de metrics_totales_empresa_ejercicio_compra_mes.',
        'SELECT importe_neto_total FROM metrics_totales_empresa_ejercicio_compra '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio}',
    ),
    'compras_mensual': (
        'metrics_totales_empresa_ejercicio_compra_mes',
        'Importe neto de compras de cada mes, comparado con el año anterior.',
        'SELECT mes, importe_neto_total FROM metrics_totales_empresa_ejercicio_compra_mes '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY mes',
    ),
    'compras_top_proveedores': (
        'metrics_totales_empresa_ejercicio_proveedor',
        'Importe neto de compras de cada proveedor, de mayor a menor.',
        'SELECT nombre, proveedor, importe_neto_total, importe_coste_total, albaranes_count '
        'FROM metrics_totales_empresa_ejercicio_proveedor '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} ORDER BY importe_neto_total DESC',
    ),
    'finanzas_resumen': (
        'datia_financial_acumulados',
        'Suma del saldo (debe − haber) de los grupos 6 y 7, periodos 1 a 12.',
        'SELECT cuenta, periodo, debe, haber, saldo FROM datia_financial_acumulados '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} AND periodo BETWEEN 1 AND 12',
    ),
    'financiera_ratios': (
        'datia_financial_acumulados',
        'Ratios calculados con los saldos de los grupos contables del ejercicio.',
        'SELECT cuenta, periodo, saldo FROM datia_financial_acumulados '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} AND periodo BETWEEN 1 AND 12',
    ),
    'finanzas_per100': (
        'datia_financial_acumulados',
        'Cada magnitud partida por los ingresos y multiplicada por 100.',
        'SELECT cuenta, periodo, saldo FROM datia_financial_acumulados '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} AND periodo BETWEEN 1 AND 12',
    ),
    'tesoreria_resumen': (
        'datia_financial_acumulados, datia_financial_cartera',
        'Caja del grupo 57, saldos de clientes y proveedores, y efectos pendientes de la cartera.',
        'SELECT cuenta, saldo FROM datia_financial_acumulados '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio} AND periodo <= 12',
    ),
    'tesoreria_forecast': (
        'datia_financial_cartera',
        'Cobros y pagos previstos según el vencimiento de los efectos pendientes.',
        'SELECT fecha_vencimiento, importe, importe_cobrado, tipo_efecto FROM datia_financial_cartera '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio}',
    ),
    'tesoreria_caja_mensual': (
        'datia_financial_acumulados',
        'Movimiento de caja del grupo 57 por periodo.',
        "SELECT periodo, saldo FROM datia_financial_acumulados "
        "WHERE empresa = {empresa} AND ejercicio = {ejercicio} AND cuenta LIKE '57%'",
    ),
    'tesoreria_pool_bancario': (
        'datia_financial_acumulados',
        'Saldos bancarios del grupo 57.',
        "SELECT cuenta, saldo FROM datia_financial_acumulados "
        "WHERE empresa = {empresa} AND ejercicio = {ejercicio} AND cuenta LIKE '57%'",
    ),
    'presupuestos_comparativa': (
        'datia_financial_acumulados',
        'Real menos presupuesto, por cuenta. El real es el saldo y el presupuesto está en la misma tabla.',
        'SELECT cuenta, saldo, debe_presupuesto, haber_presupuesto FROM datia_financial_acumulados '
        'WHERE empresa = {empresa} AND ejercicio = {ejercicio}',
    ),
}


def _origen_util(dato):
    return isinstance(dato, dict) and bool(
        dato.get('tabla') or dato.get('formula') or dato.get('consulta') or dato.get('falta')
    )


def _tablas_de_la_consulta(sql):
    tablas = []
    for nombre in re.findall(r'(?i)\b(?:from|join)\s+([a-z_][a-z0-9_]*)', sql or ''):
        clave = nombre.lower()
        if clave not in tablas:
            tablas.append(clave)
    return tablas


def asegurar_origen(respuesta, empresa=None, ejercicio=None):
    """Toda respuesta con cifra lleva tabla, fórmula y consulta. No pisa un origen ya útil."""
    if not isinstance(respuesta, dict) or respuesta.get('error'):
        return respuesta
    if respuesta.get('action') in ('RELOAD', 'NONE'):
        return respuesta
    if respuesta.get('type') in _SIN_ORIGEN:
        return respuesta
    if _origen_util(respuesta.get('origen')):
        return respuesta
    ano = ejercicio
    hallado = re.search(r'\b(20\d{2})\b', str(respuesta.get('query') or ''))
    if hallado:
        ano = hallado.group(1)
    filtros = []
    if empresa not in (None, ''):
        filtros.append(f'Empresa {empresa}')
    if ano not in (None, ''):
        filtros.append(f'Ejercicio {ano}')
    ficha = _FICHAS.get(str(respuesta.get('key') or ''))
    if ficha:
        tabla, formula, consulta = ficha
        respuesta['origen'] = origen(
            tabla, formula, filtros,
            consulta.format(empresa=empresa if empresa not in (None, '') else '', ejercicio=ano if ano not in (None, '') else ''),
        )
        return respuesta
    sql = respuesta.get('sql') or ''
    if sql and sql != 'ERROR':
        respuesta['origen'] = origen(
            ', '.join(_tablas_de_la_consulta(sql)),
            'Cifra leída con la consulta de abajo.',
            filtros,
            sql,
        )
        return respuesta
    if respuesta.get('answer') or respuesta.get('text') or respuesta.get('kpis') or respuesta.get('table') or respuesta.get('chart_config'):
        respuesta['origen'] = origen(
            '',
            'Esta respuesta no indica la tabla de la que salió la cifra.',
            filtros,
            '',
            falta='No hay consulta asociada a esta respuesta.',
        )
    return respuesta
