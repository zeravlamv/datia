"""Lee la frase entera. Una respuesta solo vale si cubre todos los significados."""
import re

from datia.services.ai.compilador_mapeo import _plegar

_MESES = (
    'enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
    'septiembre|octubre|noviembre|diciembre'
)
_SERIE_TRIMESTRE = re.compile(r'\b(trimestres|trimestrales|trimestral|por trimestre)\b')
_FILTRO_TRIMESTRE = re.compile(
    r'\b(ultimo|ultima|primer|primero|segundo|tercer|tercero|cuarto)\s+trimestre\b'
    r'|\btrimestre\s*[1-4]\b'
)
_TRIMESTRE = re.compile(r'\btrimestre\b')
_SEMESTRE = re.compile(r'\b(semestres|semestre|semestral|semestrales)\b')
_SERIE_SQL = re.compile(r'\(\s*mes\s*-\s*1\s*\)\s*/\s*3', re.I)
_SEMESTRE_SQL = re.compile(r'\(\s*mes\s*-\s*1\s*\)\s*/\s*6', re.I)
_FILTRO_SQL = re.compile(r'\bbetween\s+(1|4|7|10)\s+and\s+(3|6|9|12)\b', re.I)
_MES_SQL = re.compile(r'extract\s*\(\s*month|datepart\s*\(\s*month|\bmes\s+as\s+(label|mes)\b|\bas\s+mes\b', re.I)
_DIA_TEXTO = re.compile(r'\b\d{1,2}\s+de\s+(?:' + _MESES + r')\s+de\s+20\d{2}\b')
_DIA_SQL = re.compile(r'\b20\d{2}-\d{2}-\d{2}\b')
_T = re.compile(r'\bT[1-4]\b')


def _activa():
    from datia.services.ai.reglas_negocio import cargar
    return any(regla.get('motor') == 'cobertura' for regla in cargar())


def _anio(pregunta, lectura, ejercicio):
    from datia.services.ai.interprete_mapeo import _anio_del_hilo
    return _anio_del_hilo(lectura) or ejercicio


def grano_pedido(pregunta):
    """Corte temporal que la frase nombra. Vacío si basta el ejercicio."""
    folded = _plegar(pregunta)
    if not folded:
        return ''
    if _SERIE_TRIMESTRE.search(folded):
        return 'trimestre-serie'
    if _TRIMESTRE.search(folded):
        if _FILTRO_TRIMESTRE.search(folded):
            return 'trimestre-filtro'
        return 'trimestre-serie'
    if _SEMESTRE.search(folded):
        return 'semestre'
    from datia.services.ai.interprete_mapeo import _pide_mes
    if _pide_mes(pregunta):
        return 'mes'
    from datia.services.query_builder import QueryBuilder
    if QueryBuilder._pide_ultimo_dia(pregunta) or QueryBuilder._dia_natural(pregunta):
        return 'dia'
    return ''


def exigidos(pregunta, lectura=None, ejercicio=None):
    """Significados que la respuesta tiene que cubrir. Vacío si la cobertura no está activa."""
    if not _activa():
        return frozenset()
    pedido = set()
    grano = grano_pedido(pregunta)
    if grano:
        pedido.add('grano:' + grano)
    from datia.services.ai.plan_diccionario import encajar
    from datia.services.ai.reglas_negocio import decidir
    from datia.services.query_builder import QueryBuilder
    anio = _anio(pregunta, lectura, ejercicio)
    ficha = encajar(pregunta, anio)
    if ficha and ficha.get('operacion'):
        pedido.add('operacion:' + ficha['operacion'])
    decision = decidir(pregunta, lectura, anio)
    if decision and decision.get('motor') == 'kilos':
        pedido.add('kilos')
    medida = QueryBuilder._medida_pedida(pregunta)
    if medida:
        pedido.add('medida:' + medida)
    return frozenset(pedido)


def _capas(respuesta):
    capas = [respuesta]
    reply = respuesta.get('reply') if isinstance(respuesta, dict) else None
    if isinstance(reply, dict):
        capas.append(reply)
    return capas


def _textos(respuesta):
    trozos = []
    for capa in _capas(respuesta):
        for clave in ('text', 'answer', 'sql', 'label'):
            valor = capa.get(clave)
            if valor:
                trozos.append(str(valor))
        origen = capa.get('origen')
        if isinstance(origen, dict):
            for clave in ('consulta', 'formula', 'falta'):
                valor = origen.get(clave)
                if valor:
                    trozos.append(str(valor))
        tabla = capa.get('table')
        if isinstance(tabla, dict) and tabla.get('title'):
            trozos.append(str(tabla['title']))
        lectura = capa.get('lectura')
        plan = lectura.get('plan') if isinstance(lectura, dict) else None
        if isinstance(plan, dict) and plan.get('grano'):
            trozos.append('grano ' + str(plan['grano']))
    return '\n'.join(trozos)


def _grano_de(respuesta):
    bruto = _textos(respuesta)
    folded = _plegar(bruto)
    if _SERIE_SQL.search(bruto) or _T.search(bruto) or 'por trimestre' in folded:
        return 'trimestre-serie'
    if _SEMESTRE_SQL.search(bruto) or 'por semestre' in folded:
        return 'semestre'
    if _FILTRO_SQL.search(bruto) or _FILTRO_TRIMESTRE.search(folded):
        return 'trimestre-filtro'
    if _DIA_TEXTO.search(folded) or _DIA_SQL.search(bruto):
        return 'dia'
    if 'grano mes' in folded or _MES_SQL.search(bruto):
        return 'mes'
    return ''


def _medida_de(respuesta):
    for capa in _capas(respuesta):
        if capa.get('type') == 'cantidad' and capa.get('label'):
            return str(capa['label'])
        clave = str(capa.get('key') or '')
        if clave.startswith('cantidad_'):
            return clave.split('_', 1)[1]
    return ''


def _plan_positivo(respuesta):
    for capa in _capas(respuesta):
        if capa.get('dato_no_cargado'):
            return False
    return any(capa.get('source') == 'plan' for capa in _capas(respuesta))


def cubiertos(pregunta, respuesta, lectura=None, ejercicio=None):
    if not isinstance(respuesta, dict):
        return frozenset()
    dados = set()
    for capa in _capas(respuesta):
        for marca in capa.get('significados') or []:
            dados.add(str(marca))
    grano = _grano_de(respuesta)
    if grano:
        dados.add('grano:' + grano)
    if any(capa.get('vinculo') == 'cantidad' for capa in _capas(respuesta)):
        dados.add('kilos')
        dados.add('medida:kilos')
    medida = _medida_de(respuesta)
    if medida:
        dados.add('medida:' + medida)
    if _plan_positivo(respuesta):
        from datia.services.ai.plan_diccionario import encajar
        ficha = encajar(pregunta, _anio(pregunta, lectura, ejercicio))
        if ficha and ficha.get('operacion'):
            dados.add('operacion:' + ficha['operacion'])
            if 'trimestre' in ficha['operacion']:
                dados.add('grano:trimestre-serie')
    return frozenset(dados)


def cubre(pregunta, respuesta, lectura=None, ejercicio=None, pedido=None):
    if pedido is None:
        pedido = exigidos(pregunta, lectura, ejercicio)
    if not pedido:
        return True
    return pedido <= cubiertos(pregunta, respuesta, lectura, ejercicio)


def respuesta_incompleta():
    texto = 'Esa pregunta junta datos que no se pueden cruzar.'
    return {
        'reply': {
            'type': 'text',
            'text': texto,
            'answer': texto,
            'source': 'lectura',
            'vinculo': 'rechazo',
            'lectura': None,
        }
    }
