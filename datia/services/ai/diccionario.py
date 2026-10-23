"""Fichas que el plan puede usar. Salen del mapeo y de las cifras ya resumidas."""
from datia.models.semantic import DataField

_PAPELES = {
    'metric': 'cifra',
    'dimension': 'agrupador',
    'date': 'fecha',
}

_NOMBRES = (
    'cliente', 'articulo', 'producto', 'proveedor', 'cuenta', 'familia', 'agente', 'almacen',
)


def papel_de(usage_type, field_name='', business_name=''):
    """Traduce el rol del mapeo al papel del plan. None si la columna no se pregunta."""
    uso = (usage_type or '').strip().lower()
    if uso not in _PAPELES:
        return None
    papel = _PAPELES[uso]
    if papel != 'agrupador':
        return papel
    texto = f'{field_name} {business_name}'.casefold()
    if any(nombre in texto for nombre in _NOMBRES):
        return 'nombre'
    return 'agrupador'


def _frase(field):
    nombre = (field.business_name or '').strip()
    if nombre:
        return nombre
    return (field.field_name or '').strip()


def desde_mapeo():
    """Una ficha por columna activa marcada como cifra, nombre, agrupador o fecha."""
    fichas = []
    campos = (
        DataField.objects.filter(is_active=True, source__is_active=True)
        .exclude(usage_type__in=('none', 'data'))
        .select_related('source')
    )
    for field in campos:
        papel = papel_de(field.usage_type, field.field_name, field.business_name)
        if not papel:
            continue
        fuente = field.source
        tabla = fuente.get_local_table_name()
        if not tabla:
            continue
        fichas.append({
            'papel': papel,
            'frase': _frase(field),
            'columna': field.field_name,
            'tabla': tabla,
            'tabla_origen': fuente.source_table,
            'origen': 'mapeo',
        })
    return fichas


def operaciones():
    """Cifras que ya están en Postgres y el mapeo de SQL Server no declara solas."""
    return [
        {
            'papel': 'operacion',
            'frase': 'ventas por trimestre',
            'tabla': 'metrics_totales_empresa_ejercicio_mes',
            'corte': 'trimestre',
            'origen': 'resumen',
        },
        {
            'papel': 'operacion',
            'frase': 'compras por trimestre',
            'tabla': 'metrics_totales_empresa_ejercicio_compra_mes',
            'corte': 'trimestre',
            'origen': 'resumen',
        },
        {
            'papel': 'operacion',
            'frase': 'efectos pendientes de cobro o de pago',
            'tabla': 'datia_financial_cartera',
            'corte': 'efecto',
            'origen': 'detalle',
        },
        {
            'papel': 'operacion',
            'frase': 'saldo de un grupo de cuentas',
            'tabla': 'datia_financial_acumulados',
            'corte': 'grupo',
            'origen': 'detalle',
        },
    ]


def fichas():
    return desde_mapeo() + operaciones()


def resumen():
    cuentas = {}
    for ficha in fichas():
        cuentas[ficha['papel']] = cuentas.get(ficha['papel'], 0) + 1
    return cuentas
