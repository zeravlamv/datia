"""Lee una pregunta contra el mapeo activo y compila un SELECT.

La lectura directa arma el plan cuando la frase nombra una cifra, un corte o un
filtro. Si esa lectura no basta, el modelo local elige campos del catálogo.
El modelo no escribe SQL. Si la frase pide un dato concreto y no hay plan,
la respuesta no se sustituye por un ranking.
"""
import json
import logging
import re
from collections import deque

from datia.services.ai.compilador_mapeo import (
    _anio,
    _columna_de,
    _etiqueta,
    _fisico_de_relacion,
    _limite,
    _plegar,
    _puntos,
    _puntuacion,
    nombre_fisico,
)
from datia.services.ai.compilador_mapeo import _ANIOS, _EMPRESAS

logger = logging.getLogger('query_builder')

_AGREGADOS = {'sum', 'count', 'avg', 'min', 'max', 'ninguno'}
_OPERADORES = {'=', '<>', '>', '<', '>=', '<=', 'like', 'between', 'vacio', 'no_vacio'}
_CONCEPTOS = {
    'cliente': ('cliente',),
    'articulo': ('articulo', 'producto'),
    'proveedor': ('proveedor',),
    'cuenta': ('cuenta',),
}
_NO_VALOR = {
    'han', 'ha', 'el', 'la', 'los', 'las', 'de', 'del', 'al', 'por', 'con', 'un', 'una',
    'que', 'comprado', 'comprar', 'compra', 'compras', 'vendido', 'vendidos', 'venta',
    'ventas', 'neto', 'importe', 'albaran', 'pedido', 'durante', 'este', 'esta', 'ese',
    'esa', 'sus', 'son', 'hay', 'tengo', 'tienen', 'tiene', 'mas', 'menos', 'mejor',
    'mejores', 'peor', 'peores', 'numero', 'codigo', 'producto', 'productos', 'articulo',
    'articulos', 'cliente', 'clientes', 'proveedor', 'proveedores', 'cuenta', 'cuentas',
}
_VALOR = re.compile(r'^[\w .,\-/%]{1,80}$', re.UNICODE)
_FILTRO = re.compile(
    r'\b(producto|productos|articulo|articulos|cliente|clientes|proveedor|proveedores|cuenta|cuentas)\s+'
    r'(?:numero\s+|codigo\s+)?'
    r'([a-z0-9][a-z0-9._\-]{0,40})',
)
_MENSAJE = 'Esa pregunta no está en los datos mapeados.'


def _no_esta():
    return {
        'reply': {
            'type': 'text',
            'text': _MENSAJE,
            'answer': _MENSAJE,
            'source': 'mapeo',
        }
    }


def _normalizar_concepto(palabra):
    texto = _plegar(palabra)
    if texto.startswith('product') or texto.startswith('articul'):
        return 'articulo'
    if texto.startswith('cliente'):
        return 'cliente'
    if texto.startswith('proveedor'):
        return 'proveedor'
    if texto.startswith('cuenta'):
        return 'cuenta'
    return ''


_FECHAS = ('FechaAlbaran', 'FechaPedido', 'FechaDocumento', 'Fecha')
_ATRIBUTOS = (
    'codigo', 'descripcion', 'nombre', 'razon', 'cif', 'nif', 'dni', 'familia',
    'precio', 'stock', 'unidad', 'poblacion', 'telefono', 'email', 'direccion',
)


def _es_venta(pregunta):
    return bool(re.search(r'\bventas?\b', _plegar(pregunta)))


def _es_compra(pregunta):
    return bool(re.search(r'\bcompras?\b', _plegar(pregunta)))


def _pide_grafica(pregunta):
    return bool(re.search(r'\b(grafica|grafico|comparativa|comparar|vs)\b', _plegar(pregunta)))


def _periodos(pregunta):
    return [int(anio) for anio in re.findall(r'\b(20\d{2})\b', pregunta or '')]


def _lado(pregunta):
    folded = _plegar(pregunta)
    cliente = bool(re.search(r'\b(clientes?|ventas?)\b', folded))
    proveedor = bool(re.search(r'\b(proveedores?|compras?)\b', folded))
    if proveedor and not cliente:
        return 'proveedor'
    if cliente and not proveedor:
        return 'cliente'
    return ''


def _tabla_ok(campo, lado):
    if not lado:
        return True
    tabla = _plegar(getattr(campo, 'source_table', ''))
    if lado == 'cliente':
        return 'proveedor' not in tabla
    if lado == 'proveedor':
        return 'cliente' not in tabla
    return True


def _texto_campo(campo):
    sinonimos = ' '.join(str(item) for item in (getattr(campo, 'synonyms', None) or []))
    return _plegar(f'{campo.field_name} {campo.business_name} {sinonimos}')


def _puntos_campo(campo, folded):
    puntos = _puntuacion(campo, folded)
    for sinonimo in getattr(campo, 'synonyms', None) or []:
        puntos = max(puntos, _puntos(str(sinonimo), folded))
    return puntos


def _contiene(campo, raices):
    texto = _texto_campo(campo)
    return any(raiz in texto for raiz in raices)


def senala_mapeo(pregunta, campos):
    """La frase nombra un concepto o un campo que está en el catálogo."""
    folded = _plegar(pregunta)
    if not folded or not campos:
        return False
    for concepto, raices in _CONCEPTOS.items():
        if re.search(r'\b' + concepto + r'\w*\b', folded) or (
            concepto == 'articulo' and re.search(r'\bproductos?\b', folded)
        ):
            if any(_contiene(campo, raices) and campo.papel != 'dato' for campo in campos):
                return True
    if re.search(r'\b(ventas?|compras?)\b', folded):
        lado = _lado(pregunta)
        if any(_es_importe_neto(campo) and _tabla_ok(campo, lado) for campo in campos):
            return True
    return any(_puntos_campo(campo, folded) > 0 for campo in campos)


def _pide_conjunto(pregunta):
    """Todos, todas, todo, completo, completa o listado completo. Un número concreto no lo es."""
    folded = _plegar(pregunta)
    if re.search(r'\b(primeros|primeras)\b', folded):
        return False
    if re.search(r'\b(?:top|los|las)\s+\d{1,3}\b', folded):
        return False
    if 'listado completo' in folded:
        return True
    return bool(re.search(r'\b(todos|todas|todo|completo|completa)\b', folded))


def _corte(pregunta):
    """Número de filas que la frase pide. None si no nombra ninguno."""
    folded = _plegar(pregunta)
    hallado = re.search(r'\b(?:top|primeros|primeras|los|las)\s+(\d{1,3})\b', folded or '')
    if not hallado:
        hallado = re.search(r'\b(\d{1,3})\s+(?:primeros|primeras|top)\b', folded or '')
    if not hallado:
        return None
    numero = int(hallado.group(1))
    if numero < 1:
        return 1
    return 100 if numero > 100 else numero


_ROTULOS = {
    'codigo': 'Código',
    'descripcion': 'Descripción',
    'familia': 'Familia',
    'nombre': 'Nombre',
    'razon': 'Razón social',
    'cif': 'CIF',
    'nif': 'NIF',
    'dni': 'DNI',
    'precio': 'Precio',
    'stock': 'Stock',
    'unidad': 'Unidad',
    'poblacion': 'Población',
    'telefono': 'Teléfono',
    'email': 'Email',
    'direccion': 'Dirección',
}


def _pide_modelo(pregunta):
    folded = _plegar(pregunta)
    return bool(re.search(
        r'\b(entre|desde|hasta|excepto|distinto|distinta|diferente|nulo|nulos|vacio|vacios|'
        r'vacia|sin|no han|no ha|mayor que|menor que|despues|antes)\b',
        folded,
    ))


def _tiene_valor(pregunta):
    return bool(_valores(pregunta))


def _valores(pregunta):
    encontrados = []
    for concepto, valor in _FILTRO.findall(_plegar(pregunta)):
        if valor in _NO_VALOR or not _VALOR.fullmatch(valor):
            continue
        clave = _normalizar_concepto(concepto)
        if clave:
            encontrados.append((clave, valor))
    return encontrados


def _grupo(pregunta):
    folded = _plegar(pregunta)
    hallado = re.search(
        r'\b(?:que|cuales|quienes)\s+(clientes|articulos|productos|proveedores|cuentas)\b',
        folded,
    )
    if hallado:
        return _normalizar_concepto(hallado.group(1))
    hallado = re.search(r'\bpor\s+(cliente|articulo|producto|proveedor|cuenta)s?\b', folded)
    if hallado:
        return _normalizar_concepto(hallado.group(1))
    for palabra, concepto in (
        ('clientes', 'cliente'),
        ('productos', 'articulo'),
        ('articulos', 'articulo'),
        ('proveedores', 'proveedor'),
        ('cuentas', 'cuenta'),
    ):
        if re.search(r'\b' + palabra + r'\b', folded):
            return concepto
    return ''


def _agregado(pregunta):
    folded = _plegar(pregunta)
    if re.search(r'\b(promedio|media)\b', folded):
        return 'avg'
    if re.search(r'\b(cuantos|cuantas|numero de|cantidad de)\b', folded):
        return 'count'
    if re.search(r'\b(maximo|maxima)\b', folded):
        return 'max'
    if re.search(r'\b(minimo|minima)\b', folded):
        return 'min'
    if re.search(r'\b(listado|lista|muestra|mostrar)\b', folded) and not re.search(r'\b(importe|total|suma)\b', folded):
        return 'ninguno'
    if any(re.search(r'\b' + raiz + r'\w*\b', folded) for raiz in _ATRIBUTOS) and not re.search(
        r'\b(importe|total|suma|ventas|compras)\b', folded,
    ):
        return 'ninguno'
    return 'sum'


def _es_importe_neto(campo):
    junto = _texto_campo(campo).replace(' ', '')
    suelto = _texto_campo(campo)
    return 'importeneto' in junto or ('importe' in suelto and 'neto' in suelto)


def _es_codigo(valor):
    return bool(re.search(r'\d', valor or ''))


def _es_maestro_de(campo, concepto):
    if not concepto:
        return False
    tabla = _plegar(getattr(campo, 'source_table', ''))
    if 'linea' in tabla or 'cabecera' in tabla:
        return False
    return any(raiz in tabla for raiz in _CONCEPTOS.get(concepto, ()))


def _elegir_atributo(maestros, atributo, concepto):
    candidatos = [campo for campo in maestros if atributo in _texto_campo(campo).replace(' ', '')]
    if not candidatos:
        return None

    def clave(campo):
        texto = _texto_campo(campo).replace(' ', '')
        return (
            1 if 'empresa' in texto or 'ejercicio' in texto else 0,
            0 if concepto and concepto[:4] in texto else 1,
            0 if campo.is_key else 1,
            len(texto),
            campo.id,
        )

    return min(candidatos, key=clave)


def _columnas_lista(pregunta, campos, concepto, lado):
    """Columnas del maestro que la frase pide ver, sin convertirlas en un importe."""
    if not concepto:
        return []
    maestros = [campo for campo in campos if _es_maestro_de(campo, concepto) and _tabla_ok(campo, lado)]
    if not maestros:
        return []
    atributos = []
    for raiz in _ATRIBUTOS:
        if raiz == 'codigo' and concepto == 'cuenta':
            continue
        if re.search(r'\b' + raiz + r'\w*\b', _plegar(pregunta)):
            atributos.append(raiz)
    if atributos:
        elegidos = []
        vistos = set()
        for atributo in atributos:
            campo = _elegir_atributo(maestros, atributo, concepto)
            if campo is None or campo.id in vistos:
                continue
            vistos.add(campo.id)
            elegidos.append((campo, _ROTULOS.get(atributo)))
        return elegidos
    claves = [
        campo for campo in maestros
        if campo.is_key and 'empresa' not in _plegar(campo.field_name) and 'ejercicio' not in _plegar(campo.field_name)
    ]
    nombres = [
        campo for campo in maestros
        if any(raiz in _texto_campo(campo) for raiz in ('descripcion', 'razon social', 'nombre'))
    ]
    salida = []
    for grupo in (claves[:1], nombres[:1]):
        for campo in grupo:
            if campo not in salida:
                salida.append(campo)
    return [(campo, None) for campo in salida]


def _alias_de(campo, usados):
    from datia.services.ai.compilador_mapeo import _sanear
    base = _sanear(campo.business_name) or _sanear(campo.field_name) or 'campo'
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', base):
        base = 'campo'
    alias = base
    n = 2
    while alias in usados:
        alias = f'{base}_{n}'
        n += 1
    usados.add(alias)
    return alias


def _alias_columnas(plan, campos):
    por_id = {campo.id: campo for campo in campos}
    usados = set()
    pares = []
    for item in plan['campos']:
        campo = por_id[item['id']]
        pares.append((
            _alias_de(campo, usados),
            item.get('titulo') or campo.business_name or campo.field_name,
        ))
    return pares


def _campo_de(campos, raices, lado, junto_a=None, maestro=False, nombre=False):
    candidatos = [
        campo for campo in campos
        if _tabla_ok(campo, lado) and _contiene(campo, raices) and campo.papel != 'cifra'
    ]
    if nombre:
        nombrados = []
        for campo in candidatos:
            piezas = set(_texto_campo(campo).split())
            if {'razon', 'social'} <= piezas or 'descripcion' in piezas or 'nombre' in piezas:
                nombrados.append(campo)
        candidatos = nombrados or candidatos
    if not candidatos:
        return None

    def clave(campo):
        tabla = _plegar(campo.source_table)
        es_maestro = 0 if maestro and 'linea' not in tabla and 'cabecera' not in tabla and any(
            raiz in tabla for raiz in raices
        ) else 1
        junto = 0 if junto_a and campo.source_id == junto_a else 1
        codigo = 0 if campo.is_key or 'codigo' in _plegar(campo.field_name) else 1
        preferencia = es_maestro if maestro else junto
        return (preferencia, codigo, 0 if campo.is_key else 1, campo.id)

    return min(candidatos, key=clave)


def _es_medida(campo):
    return campo.papel == 'cifra' or _es_importe_neto(campo)


def _cifras(pregunta, campos, lado):
    folded = _plegar(pregunta)
    puntuadas = [(_puntos_campo(campo, folded), campo) for campo in campos if _es_medida(campo) and _tabla_ok(campo, lado)]
    mejor = max((puntos for puntos, _campo in puntuadas), default=0)
    if mejor <= 0:
        return []
    return [campo for puntos, campo in puntuadas if puntos == mejor]


def _documento(pregunta):
    folded = _plegar(pregunta)
    if re.search(r'\bpedidos?\b', folded):
        return 'pedido'
    return 'albaran'


def _cifra_defecto(campos, lado, filtro_concepto, documento):
    cifras = [campo for campo in campos if _es_medida(campo) and _tabla_ok(campo, lado)]
    netos = [campo for campo in cifras if _es_importe_neto(campo)] or cifras
    if not netos:
        return None

    def clave(campo):
        tabla = _plegar(campo.source_table)
        if filtro_concepto == 'articulo':
            sitio = 0 if 'linea' in tabla else 1
        else:
            sitio = 0 if 'cabecera' in tabla else 1 if 'linea' in tabla else 2
        ajeno = 1 if lado == '' and 'proveedor' in tabla else 0
        return (ajeno, 0 if documento in tabla else 1, sitio, 0 if _es_importe_neto(campo) else 1, campo.id)

    return min(netos, key=clave)


def _forma_de(pregunta, agregado):
    periodos = _periodos(pregunta)
    if agregado == 'ninguno':
        return 'listado', periodos, 'ejercicio'
    if _pide_grafica(pregunta) or len(periodos) >= 2:
        return 'grafica', periodos, 'mes'
    return 'tabla', periodos, 'ejercicio'


def plan_determinista(pregunta, campos, limite=20):
    """Plan con columnas, cifra, corte, filtros y periodos. None si no basta."""
    if not pregunta or not campos:
        return None
    lado = _lado(pregunta)
    grupo = _grupo(pregunta)
    valores = _valores(pregunta)
    if grupo and any(clave == grupo for clave, _valor in valores):
        grupo = ''
    agregado = _agregado(pregunta)
    explicitas = _cifras(pregunta, campos, lado)
    venta = _es_venta(pregunta)
    compra = _es_compra(pregunta)
    if agregado == 'ninguno' and not explicitas:
        columnas = _columnas_lista(pregunta, campos, grupo, lado)
        if not columnas or (grupo and len(_periodos(pregunta)) >= 2):
            return None
        completo = _pide_conjunto(pregunta)
        return {
            'campos': [
                {'id': campo.id, 'agregado': 'ninguno', 'titulo': titulo}
                for campo, titulo in columnas
            ],
            'filtros': [],
            'agrupar': [],
            'orden': {'id': columnas[0][0].id, 'sentido': 'asc'},
            'limite': None if completo else (_corte(pregunta) or 100),
            'completo': completo,
            'forma': 'listado',
            'periodos': [],
            'grano': 'ejercicio',
        }
    if not grupo and not valores and not explicitas and not venta and not compra:
        return None
    if not grupo and not valores and len(explicitas) != 1 and not venta and not compra:
        return None
    if grupo and len(_periodos(pregunta)) >= 2:
        return None
    filtro_concepto = valores[0][0] if valores else ''
    cifra = explicitas[0] if len(explicitas) == 1 else _cifra_defecto(
        campos, lado, filtro_concepto, _documento(pregunta),
    )
    if cifra is None and agregado != 'count':
        return None
    filtros = []
    for clave, valor in valores:
        if _es_codigo(valor):
            campo = _campo_de(campos, _CONCEPTOS[clave], lado, getattr(cifra, 'source_id', None), maestro=False)
        else:
            campo = _campo_de(campos, _CONCEPTOS[clave], lado, maestro=True, nombre=True)
        if campo is None:
            return None
        filtros.append({
            'id': campo.id,
            'op': '=' if _es_codigo(valor) else 'like',
            'valor': valor,
        })
    agrupar = []
    if grupo:
        campo_grupo = _campo_de(campos, _CONCEPTOS[grupo], lado, maestro=True)
        if campo_grupo is None:
            return None
        if agregado == 'count':
            cifra = campo_grupo
        else:
            agrupar.append(campo_grupo.id)
    if cifra is None:
        return None
    if agregado == 'count' and grupo:
        campos_plan = [{'id': cifra.id, 'agregado': 'count'}]
        agrupar = []
    else:
        campos_plan = [{'id': cifra.id, 'agregado': agregado if agregado != 'count' else 'count'}]
    forma, periodos, grano = _forma_de(pregunta, agregado if not (agregado == 'count' and grupo) else 'count')
    tope = 100 if forma == 'grafica' else _limite(pregunta, limite)
    return {
        'campos': campos_plan,
        'filtros': filtros,
        'agrupar': agrupar,
        'orden': {'id': cifra.id, 'sentido': 'asc' if _plegar(pregunta).find(' peor') >= 0 else 'desc'},
        'limite': tope,
        'forma': forma,
        'periodos': periodos,
        'grano': grano,
    }


def leer_plan(texto):
    if not texto:
        return None
    inicio = texto.find('{')
    fin = texto.rfind('}')
    if inicio < 0 or fin < inicio:
        return None
    try:
        data = json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data:
        return None
    return data


def validar_plan(data, campos, limite=20):
    """Plan normalizado, None si viene vacío y False si nombra un campo ajeno al catálogo."""
    if not isinstance(data, dict) or not data:
        return None
    por_id = {campo.id: campo for campo in campos}

    def entero(valor):
        try:
            return int(valor)
        except (TypeError, ValueError):
            return None

    def conocido(valor):
        numero = entero(valor)
        if numero is None or numero not in por_id:
            return False
        return numero

    vistos = []
    for item in data.get('campos') or []:
        if not isinstance(item, dict):
            return False
        numero = conocido(item.get('id'))
        if numero is False:
            return False
        agregado = str(item.get('agregado') or '').lower()
        if agregado not in _AGREGADOS:
            agregado = 'sum' if por_id[numero].papel == 'cifra' else 'ninguno'
        visto = {'id': numero, 'agregado': agregado}
        if item.get('titulo'):
            visto['titulo'] = str(item.get('titulo'))
        vistos.append(visto)
    filtros = []
    for item in data.get('filtros') or []:
        if not isinstance(item, dict):
            return False
        numero = conocido(item.get('id'))
        if numero is False:
            return False
        operador = str(item.get('op') or '=').lower()
        if operador not in _OPERADORES:
            return False
        filtro = {'id': numero, 'op': operador, 'valor': str(item.get('valor') or '').strip()}
        if item.get('valor2') not in (None, ''):
            filtro['valor2'] = str(item.get('valor2')).strip()
        if operador not in ('vacio', 'no_vacio') and not _VALOR.fullmatch(filtro['valor']):
            return False
        if operador == 'between' and not _VALOR.fullmatch(filtro.get('valor2') or ''):
            return False
        filtros.append(filtro)
    agrupar = []
    grupos = data.get('agrupar') or []
    if isinstance(grupos, int):
        grupos = [grupos]
    for valor in grupos:
        numero = conocido(valor)
        if numero is False:
            return False
        agrupar.append(numero)
    if not vistos and filtros:
        vistos.append({'id': filtros[0]['id'], 'agregado': 'count'})
    if not vistos and agrupar:
        vistos.append({'id': agrupar[0], 'agregado': 'ninguno'})
    if not vistos:
        return None
    orden = data.get('orden') or {}
    sentido = 'asc' if str((orden or {}).get('sentido') or '').lower() == 'asc' else 'desc'
    orden_id = conocido(orden.get('id')) if isinstance(orden, dict) and orden.get('id') not in (None, '') else vistos[0]['id']
    if orden_id is False:
        return False
    completo = bool(data.get('completo'))
    try:
        tope = int(data.get('limite') or limite or 20)
    except (TypeError, ValueError):
        tope = 20
    if tope < 1:
        tope = 1
    if tope > 100 and not completo:
        tope = 100
    forma = str(data.get('forma') or '').lower()
    if forma not in ('tabla', 'grafica', 'listado'):
        forma = 'listado' if vistos and all(item['agregado'] == 'ninguno' for item in vistos) and not agrupar else 'tabla'
    periodos = []
    for valor in data.get('periodos') or []:
        try:
            anio = int(valor)
        except (TypeError, ValueError):
            continue
        if 2000 <= anio <= 2100 and anio not in periodos:
            periodos.append(anio)
    grano = 'mes' if str(data.get('grano') or '').lower() == 'mes' else 'ejercicio'
    return {
        'campos': vistos,
        'filtros': filtros,
        'agrupar': agrupar,
        'orden': {'id': orden_id, 'sentido': sentido},
        'limite': tope,
        'completo': completo,
        'forma': forma,
        'periodos': periodos,
        'grano': grano,
    }


def _grupos(relaciones):
    grupos = {}
    for relacion in relaciones or []:
        grupos.setdefault((relacion.source_id, relacion.target_id), []).append(relacion)
    return grupos


def _vecinos(nodo, grupos):
    salida = {}
    for (origen, destino), relaciones in grupos.items():
        if origen == nodo:
            salida.setdefault(destino, []).extend(relaciones)
        elif destino == nodo:
            salida.setdefault(origen, []).extend(relaciones)
    return salida


def _ruta(origen, destino, grupos, tope=4):
    if origen == destino:
        return []
    cola = deque([(origen, [])])
    vistos = {origen}
    while cola:
        nodo, camino = cola.popleft()
        if len(camino) >= tope:
            continue
        for otro, relaciones in _vecinos(nodo, grupos).items():
            if otro in vistos:
                continue
            nuevo = camino + [(nodo, otro, relaciones)]
            if otro == destino:
                return nuevo
            vistos.add(otro)
            cola.append((otro, nuevo))
    return None


def _ident(nombre, dialecto):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', nombre or ''):
        return None
    if dialecto == 'sqlserver':
        return f'[{nombre}]'
    return f'"{nombre}"'


def _literal(valor, numerico=False):
    texto = str(valor or '').strip()
    if not _VALOR.fullmatch(texto):
        return None
    if numerico and re.fullmatch(r'-?\d+(?:[.,]\d+)?', texto):
        return texto.replace(',', '.')
    return "'" + texto.replace("'", "''") + "'"


def _condicion(alias, columna, filtro, dialecto):
    operador = filtro['op']
    if operador == 'vacio':
        if dialecto == 'sqlserver':
            return f"({alias}.{columna} IS NULL OR LTRIM(RTRIM(CAST({alias}.{columna} AS varchar(200)))) = '')"
        return f"({alias}.{columna} IS NULL OR BTRIM({alias}.{columna}::text) = '')"
    if operador == 'no_vacio':
        if dialecto == 'sqlserver':
            return f"({alias}.{columna} IS NOT NULL AND LTRIM(RTRIM(CAST({alias}.{columna} AS varchar(200)))) <> '')"
        return f"({alias}.{columna} IS NOT NULL AND BTRIM({alias}.{columna}::text) <> '')"
    if operador == 'like':
        comodin = _literal(filtro.get('valor'))
        if not comodin:
            return None
        limpio = comodin[1:-1].replace('%', '').replace('_', '')
        comparador = 'LIKE' if dialecto == 'sqlserver' else 'ILIKE'
        return f"{alias}.{columna} {comparador} '%{limpio}%'"
    if operador == 'between':
        inicio = _literal(filtro.get('valor'), numerico=True)
        fin = _literal(filtro.get('valor2'), numerico=True)
        if not inicio or not fin:
            return None
        return f'{alias}.{columna} BETWEEN {inicio} AND {fin}'
    derecho = _literal(filtro.get('valor'), numerico=operador in ('>', '<', '>=', '<='))
    if not derecho:
        return None
    return f'{alias}.{columna} {operador} {derecho}'


def _expr_texto(expr, dialecto):
    if dialecto == 'sqlserver':
        return f"LTRIM(RTRIM(CAST({expr} AS varchar(200))))"
    return f'BTRIM({expr}::text)'


def _tabla_base(plan, campos):
    por_id = {campo.id: campo for campo in campos}
    ids = []
    for item in plan['campos']:
        if item['agregado'] in ('sum', 'avg', 'min', 'max'):
            ids.append(por_id[item['id']].source_id)
    for item in plan['filtros']:
        ids.append(por_id[item['id']].source_id)
    for item in plan['campos']:
        ids.append(por_id[item['id']].source_id)
    for grupo in plan['agrupar']:
        ids.append(por_id[grupo].source_id)

    def tiene_anio(source_id):
        return any(campo.source_id == source_id and campo.field_name in _ANIOS for campo in campos)

    unicos = []
    for source_id in ids:
        if source_id not in unicos:
            unicos.append(source_id)
    if not unicos:
        return None
    unicos.sort(key=lambda source_id: (0 if tiene_anio(source_id) else 1, ids.index(source_id)))
    return unicos[0]


def _enganchar(base, destino, grupos, alias, joins, columnas, dialecto, contador):
    if destino in alias:
        return contador, True
    camino = _ruta(base, destino, grupos)
    if camino is None:
        return contador, False
    for padre, hijo, relaciones in camino:
        if hijo in alias:
            continue
        if padre not in alias:
            return contador, False
        pares = []
        tabla = None
        for relacion in relaciones:
            pieza = _fisico_de_relacion(relacion, padre, columnas)
            if not pieza:
                return contador, False
            nuevo, local, par = pieza
            if nuevo != hijo or par in pares:
                continue
            pares.append(par)
            tabla = local
        if not pares or not tabla:
            return contador, False
        nombre = _ident(tabla, dialecto)
        if not nombre:
            return contador, False
        alias_hijo = f't{contador}'
        contador += 1
        condiciones = []
        for izquierda, derecha in pares:
            izq = _ident(izquierda, dialecto)
            der = _ident(derecha, dialecto)
            if not izq or not der:
                return contador, False
            condiciones.append(f'{alias[padre]}.{izq} = {alias_hijo}.{der}')
        alias[hijo] = alias_hijo
        joins.append(f'JOIN {nombre} {alias_hijo} ON ' + ' AND '.join(condiciones))
    return contador, destino in alias


def _preparar_desde(plan, campos, relaciones, columnas, empresa, dialecto, base):
    """FROM, alias y filtro de empresa. None si no hay cruce o columna de empresa."""
    por_id = {campo.id: campo for campo in campos}
    local = next(campo.local for campo in campos if campo.source_id == base)
    tabla = _ident(local, dialecto)
    if not tabla:
        return None
    grupos = _grupos(relaciones)
    alias = {base: 't1'}
    joins = []
    contador = 2
    destinos = [por_id[item['id']].source_id for item in plan['campos']]
    destinos.extend(por_id[item['id']].source_id for item in plan['filtros'])
    destinos.extend(por_id[grupo].source_id for grupo in plan['agrupar'])
    for destino in destinos:
        contador, bien = _enganchar(base, destino, grupos, alias, joins, columnas, dialecto, contador)
        if not bien:
            return None
    empresa_col = _ident(_columna_de(campos, base, _EMPRESAS, columnas.get(base, set())), dialecto)
    if not empresa_col:
        return None
    where = [f't1.{empresa_col} = {int(empresa)}']
    for item in plan['filtros']:
        campo = por_id[item['id']]
        columna = _ident(nombre_fisico(campo, columnas.get(campo.source_id, set())), dialecto)
        if not columna:
            return None
        condicion = _condicion(alias[campo.source_id], columna, item, dialecto)
        if not condicion:
            return None
        where.append(condicion)
    return por_id, alias, joins, tabla, where


def _compilar_listado(plan, campos, relaciones, columnas, empresa, dialecto):
    por_id = {campo.id: campo for campo in campos}
    cuentas = {}
    for item in plan['campos']:
        origen = por_id[item['id']].source_id
        cuentas[origen] = cuentas.get(origen, 0) + 1
    base = max(cuentas, key=lambda origen: (cuentas[origen], -origen))
    preparado = _preparar_desde(plan, campos, relaciones, columnas, empresa, dialecto, base)
    if not preparado:
        return None
    _por_id, alias, joins, tabla, where = preparado
    selects = []
    for alias_col, _titulo in _alias_columnas(plan, campos):
        item = plan['campos'][len(selects)]
        campo = por_id[item['id']]
        columna = _ident(nombre_fisico(campo, columnas.get(campo.source_id, set())), dialecto)
        nombre = _ident(alias_col, dialecto)
        if not columna or not nombre:
            return None
        selects.append(f'{alias[campo.source_id]}.{columna} AS {nombre}')
    orden = ' ORDER BY 1 ASC'
    if plan.get('completo'):
        select = 'SELECT ' + ', '.join(selects)
        cola = ''
    elif dialecto == 'sqlserver':
        select = f'SELECT TOP {int(plan["limite"])} ' + ', '.join(selects)
        cola = ''
    else:
        select = 'SELECT ' + ', '.join(selects)
        cola = f' LIMIT {int(plan["limite"])}'
    sql = f'{select} FROM {tabla} t1 {" ".join(joins)} WHERE {" AND ".join(where)}{orden}{cola}'
    return ' '.join(sql.split())


def _compilar_grafica(plan, campos, relaciones, columnas, empresa, dialecto):
    periodos = [int(anio) for anio in (plan.get('periodos') or [])]
    por_id = {campo.id: campo for campo in campos}
    medida = next((por_id[item['id']] for item in plan['campos'] if item['agregado'] in ('sum', 'avg', 'min', 'max')), None)
    if medida is None:
        return None
    base = medida.source_id
    preparado = _preparar_desde(plan, campos, relaciones, columnas, empresa, dialecto, base)
    if not preparado:
        return None
    _por_id, alias, joins, tabla, where = preparado
    anio = _ident(_columna_de(campos, base, _ANIOS, columnas.get(base, set())), dialecto)
    if not anio:
        return None
    columna = _ident(nombre_fisico(medida, columnas.get(base, set())), dialecto)
    if not columna:
        return None
    agregado = next(item['agregado'] for item in plan['campos'] if por_id[item['id']].id == medida.id)
    expr = f'{agregado.upper()}({alias[base]}.{columna})'
    fecha = _ident(_columna_de(campos, base, _FECHAS, columnas.get(base, set())), dialecto)
    if periodos:
        lista = ', '.join(str(anio_valor) for anio_valor in periodos)
        where.append(f'{alias[base]}.{anio} IN ({lista})')
    if plan.get('grano') == 'mes' and fecha:
        if dialecto == 'sqlserver':
            label = f'DATEPART(MONTH, {alias[base]}.{fecha})'
        else:
            label = f'EXTRACT(MONTH FROM {alias[base]}.{fecha})'
        if len(periodos) >= 2:
            select = f'SELECT {label} AS label, {alias[base]}.{anio} AS serie, {expr} AS val, COUNT(*) AS ops'
            group = ' GROUP BY 1, 2 ORDER BY 2, 1'
        else:
            select = f'SELECT {label} AS label, {expr} AS val, COUNT(*) AS ops'
            group = ' GROUP BY 1 ORDER BY 1'
    elif len(periodos) >= 2:
        select = f'SELECT {alias[base]}.{anio} AS label, {expr} AS val, COUNT(*) AS ops'
        group = ' GROUP BY 1 ORDER BY 1'
    else:
        return None
    sql = f'{select} FROM {tabla} t1 {" ".join(joins)} WHERE {" AND ".join(where)}{group}'
    return ' '.join(sql.split())


def compilar_plan(plan, campos, relaciones, columnas, empresa, year, dialecto='postgres'):
    """SELECT del plan. None si falta un cruce, una columna o el valor no es seguro."""
    if not plan or not campos:
        return None
    if plan.get('forma') == 'listado' or (
        plan.get('campos') and all(item.get('agregado') == 'ninguno' for item in plan['campos']) and not plan.get('agrupar')
    ):
        return _compilar_listado(plan, campos, relaciones, columnas, empresa, dialecto)
    if plan.get('forma') == 'grafica':
        grafica = _compilar_grafica(plan, campos, relaciones, columnas, empresa, dialecto)
        if grafica or len(plan.get('periodos') or []) >= 2:
            return grafica
    por_id = {campo.id: campo for campo in campos}
    base = _tabla_base(plan, campos)
    if base is None or not any(campo.source_id == base for campo in campos):
        return None
    local = next(campo.local for campo in campos if campo.source_id == base)
    tabla = _ident(local, dialecto)
    if not tabla:
        return None
    grupos = _grupos(relaciones)
    alias = {base: 't1'}
    joins = []
    contador = 2
    destinos = []
    for item in plan['campos']:
        destinos.append(por_id[item['id']].source_id)
    for item in plan['filtros']:
        destinos.append(por_id[item['id']].source_id)
    for grupo in plan['agrupar']:
        destinos.append(por_id[grupo].source_id)
    for destino in destinos:
        contador, bien = _enganchar(base, destino, grupos, alias, joins, columnas, dialecto, contador)
        if not bien:
            return None
    empresa_col = _ident(_columna_de(campos, base, _EMPRESAS, columnas.get(base, set())), dialecto)
    if not empresa_col:
        return None
    where = [f't1.{empresa_col} = {int(empresa)}']
    filtra_fecha = False
    for item in plan['filtros']:
        campo = por_id[item['id']]
        if campo.field_name in _ANIOS or campo.papel == 'fecha':
            filtra_fecha = True
        columna = _ident(nombre_fisico(campo, columnas.get(campo.source_id, set())), dialecto)
        if not columna:
            return None
        condicion = _condicion(alias[campo.source_id], columna, item, dialecto)
        if not condicion:
            return None
        where.append(condicion)
    if not filtra_fecha and year is not None:
        anio_col = _ident(_columna_de(campos, base, _ANIOS, columnas.get(base, set())), dialecto)
        if anio_col:
            where.append(f't1.{anio_col} = {int(year)}')
    medida = por_id[plan['campos'][0]['id']]
    col_medida = _ident(nombre_fisico(medida, columnas.get(medida.source_id, set())), dialecto)
    if not col_medida:
        return None
    alias_medida = alias[medida.source_id]
    agregado = plan['campos'][0]['agregado']
    expr = f'{alias_medida}.{col_medida}'
    if agregado == 'count':
        valor = f'COUNT(DISTINCT {expr})'
    elif agregado == 'ninguno':
        valor = f'MAX({expr})' if plan['agrupar'] else expr
    else:
        valor = f'{agregado.upper()}({expr})'
    group = ''
    if plan['agrupar']:
        corte = por_id[plan['agrupar'][0]]
        grupo, visible = _etiqueta(corte, campos, columnas)
        grupo = _ident(grupo, dialecto)
        visible = _ident(visible, dialecto)
        if not grupo or not visible:
            return None
        alias_corte = alias[corte.source_id]
        if visible == grupo:
            select = f'SELECT {alias_corte}.{grupo} AS label, {valor} AS val'
            group = ' GROUP BY 1'
        else:
            select = (
                f"SELECT COALESCE(NULLIF({_expr_texto(f'MAX({alias_corte}.{visible})', dialecto)}, ''), "
                f"{_expr_texto(f'MAX({alias_corte}.{grupo})', dialecto)}) AS label, {valor} AS val"
            )
            group = f' GROUP BY {alias_corte}.{grupo}'
    else:
        select = f"SELECT 'Total' AS label, {valor} AS val"
    sentido = 'ASC' if plan['orden']['sentido'] == 'asc' else 'DESC'
    orden = ' ORDER BY val ' + sentido
    tope = int(plan['limite'])
    if dialecto == 'sqlserver':
        select = select.replace('SELECT ', f'SELECT TOP {tope} ', 1)
        cola = ''
    else:
        cola = f' LIMIT {tope}'
    sql = f'{select} FROM {tabla} t1 {" ".join(joins)} WHERE {" AND ".join(where)}{group}{orden}{cola}'
    return ' '.join(sql.split())


def _campos_modelo(pregunta, campos, relaciones):
    folded = _plegar(pregunta)
    directos = [campo for campo in campos if _puntos_campo(campo, folded) > 0 or any(
        _contiene(campo, raices) and re.search(r'\b' + concepto + r'\w*\b', folded)
        for concepto, raices in _CONCEPTOS.items()
    )]
    tablas = {campo.source_id for campo in directos}
    vecinos = set(tablas)
    for relacion in relaciones or []:
        if relacion.source_id in tablas or relacion.target_id in tablas:
            vecinos.add(relacion.source_id)
            vecinos.add(relacion.target_id)
    elegidos = [
        campo for campo in campos
        if campo.source_id in vecinos and (campo.papel != 'dato' or campo in directos or campo.is_key)
    ]
    elegidos.sort(key=lambda campo: _puntos_campo(campo, folded), reverse=True)
    return elegidos[:80]


def _pedir_plan(pregunta, campos, relaciones, limite):
    from datia.services.ollama_service import OllamaService
    lineas = []
    for campo in _campos_modelo(pregunta, campos, relaciones):
        lineas.append(
            f"{campo.id}|{campo.source_table}|{campo.business_name or campo.field_name}|{campo.papel}"
        )
    if not lineas:
        return None
    prompt = (
        'Devuelve solo un JSON. No escribas SQL ni cifras.\n'
        'Los id solo pueden ser los de esta lista. Formato id|tabla|campo|papel:\n'
        + '\n'.join(lineas)
        + '\nClaves:\n'
        'campos: [{id, agregado: sum|count|avg|min|max|ninguno}]\n'
        'filtros: [{id, op: =|<>|>|<|>=|<=|like|between|vacio|no_vacio, valor, valor2}]\n'
        'agrupar: [id]\n'
        'orden: {id, sentido: asc|desc}\n'
        f'limite: entero de 1 a {int(limite or 20)}\n'
        'forma: tabla|grafica|listado\n'
        'periodos: [año, año]\n'
        'grano: mes|ejercicio\n'
        'Listado: varios campos con agregado ninguno, sin inventar un importe.\n'
        'Grafica comparativa: forma grafica, grano mes, periodos con los años de la pregunta, un solo campo sum.\n'
        'Usa like para un nombre y = para un codigo. La empresa ya se añade. No filtres el año si rellenas periodos.\n'
        'Si la pregunta no se puede leer con estos campos, devuelve {}\n'
        f'Pregunta: {pregunta}\nJSON:\n'
    )
    texto = OllamaService().generate_text(
        prompt,
        timeout=45,
        model='qwen2.5:14b-instruct-q4_k_m',
        stream=False,
        options={'temperature': 0, 'num_predict': 280},
    )
    return leer_plan(texto)


def _titulo(plan, campos):
    por_id = {campo.id: campo for campo in campos}
    medida = por_id[plan['campos'][0]['id']]
    titulo = medida.business_name or medida.field_name
    if plan['agrupar']:
        corte = por_id[plan['agrupar'][0]]
        titulo = f'{titulo} por {corte.business_name or corte.field_name}'
    if plan['filtros']:
        titulo = f'{titulo} filtrado'
    return titulo


def _probar(sql, dialecto):
    from django.db import connections
    alias = 'analytics' if 'analytics' in connections.databases else 'default'
    try:
        with connections[alias].cursor() as cur:
            if dialecto == 'sqlserver':
                cur.execute(f'SELECT TOP 0 * FROM ({sql}) AS sonda')
            else:
                cur.execute('EXPLAIN ' + sql)
        return True
    except Exception as exc:
        logger.info('Interprete: la base rechazo la consulta: %s', exc)
        return False


def _cargar():
    from types import SimpleNamespace

    from datia.models.semantic import DataField, DataRelation
    from datia.services.ai.diccionario import papel_de

    campos = []
    for field in DataField.objects.filter(is_active=True, source__is_active=True).exclude(usage_type='none').select_related('source'):
        local = field.source.get_local_table_name()
        if not local:
            continue
        papel = papel_de(field.usage_type, field.field_name, field.business_name)
        if papel is None and (field.usage_type or '').lower() == 'data':
            papel = 'dato'
        if papel is None:
            continue
        sinonimos = field.synonyms if isinstance(field.synonyms, list) else []
        campos.append(SimpleNamespace(
            id=field.id,
            papel=papel,
            field_name=field.field_name,
            business_name=field.business_name or '',
            source_id=field.source_id,
            source_table=field.source.source_table,
            local=local,
            is_key=bool(field.is_key),
            usage_type=field.usage_type,
            synonyms=sinonimos,
        ))
    relaciones = list(
        DataRelation.objects.filter(source__is_active=True, target__is_active=True)
        .select_related('source', 'target', 'from_field', 'to_field')
    )
    return campos, relaciones


def _completar_forma(plan, pregunta):
    if not plan or plan.get('forma') == 'listado':
        return plan
    periodos = list(plan.get('periodos') or []) or _periodos(pregunta)
    plan['periodos'] = periodos
    if _pide_grafica(pregunta) or len(periodos) >= 2:
        plan['forma'] = 'grafica'
        plan['grano'] = 'mes'
        plan['limite'] = max(int(plan.get('limite') or 20), 100)
    return plan


def consultar(pregunta, empresa, ejercicio, limite=20, campos=None, relaciones=None, columnas=None, pedir=None, dialecto=None, sondear=True):
    """Respuesta del mapeo, un aviso si el dato no está, o None si la frase no habla de datos mapeados."""
    try:
        empresa_id = int(empresa)
    except (TypeError, ValueError):
        return None
    try:
        return _consultar(pregunta, empresa_id, ejercicio, limite, campos, relaciones, columnas, pedir, dialecto, sondear)
    except Exception:
        logger.exception('Interprete: no se pudo leer la pregunta en el mapeo')
        if _grupo(pregunta) or _es_venta(pregunta) or _es_compra(pregunta) or _tiene_valor(pregunta) or _pide_modelo(pregunta):
            return _no_esta()
        return None


def _salida(plan, campos, sql, year):
    from datia.services.ai.open_question import OpenQuestion
    ano = None if plan.get('forma') in ('listado', 'grafica') else year
    salida = OpenQuestion._match(
        sql,
        _titulo(plan, campos),
        'table',
        ano,
        source='mapeo',
        formula='Lectura de los campos mapeados, con los filtros de la pregunta y el cruce de las relaciones.',
    )
    if plan.get('forma') == 'listado':
        pares = _alias_columnas(plan, campos)
        salida['type'] = 'listado'
        salida['columnas'] = [alias for alias, _titulo in pares]
        salida['titulos'] = [titulo for _alias, titulo in pares]
        salida['completo'] = bool(plan.get('completo'))
        return salida
    if plan.get('forma') == 'grafica':
        salida['type'] = 'chart'
        salida['chart_type'] = 'line' if ' AS serie' in sql else 'bar'
        salida['key'] = 'evolution_comparison'
        salida['intent_meta']['is_comparison'] = ' AS serie' in sql
        periodos = plan.get('periodos') or []
        if len(periodos) >= 2:
            salida['label'] = f'Comparativa {periodos[0]} vs {periodos[-1]}'
        if _es_compra(plan.get('_pregunta') or ''):
            salida['intent_meta']['metric'] = 'purchase'
    return salida


def _consultar(pregunta, empresa, ejercicio, limite, campos, relaciones, columnas, pedir, dialecto, sondear=True):
    if campos is None or relaciones is None:
        campos, relaciones = _cargar()
    if not senala_mapeo(pregunta, campos):
        return None
    if _pide_modelo(pregunta):
        plan = None
    else:
        plan = plan_determinista(pregunta, campos, limite)
    if plan is None:
        try:
            bruto = _pedir_plan(pregunta, campos, relaciones, limite) if pedir is None else pedir(pregunta, campos, limite)
        except Exception:
            logger.warning('Interprete: el modelo local no contestó')
            bruto = None
        if bruto:
            plan = validar_plan(bruto, campos, limite)
            if not plan:
                return _no_esta()
    if not plan:
        return _no_esta()
    plan = _completar_forma(plan, pregunta)
    plan['_pregunta'] = pregunta
    if dialecto is None:
        from datia.services.ai.semantic_plan import SemanticPlan
        dialecto = SemanticPlan.dialecto_actual()
    year = _anio(pregunta, ejercicio)
    if columnas is None:
        from datia.services.ai.compilador_mapeo import _mapa
        columnas = _mapa(campos, [])
    sql = compilar_plan(plan, campos, relaciones, columnas, empresa, year, dialecto)
    if not sql:
        return _no_esta()
    from datia.services.security.sql_guard import SQLGuard
    if not SQLGuard.check_sql(sql).get('allowed'):
        logger.info('Interprete: la consulta sale de las tablas permitidas')
        return _no_esta()
    if sondear and not _probar(sql, dialecto):
        return _no_esta()
    return _salida(plan, campos, sql, year)
