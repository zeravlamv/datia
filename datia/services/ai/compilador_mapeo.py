"""Arma una consulta a partir de los campos activos y de las relaciones del mapeo."""
import logging
import re
import unicodedata

from django.db import connections
from django.db.models import Q

from datia.models.semantic import DataField, DataRelation
from datia.services.ai.diccionario import papel_de

logger = logging.getLogger('query_builder')

_GENERICOS = {
    'codigo', 'empresa', 'ejercicio', 'numero', 'serie', 'fecha', 'total', 'datos', 'campo',
}
_ANIOS = ('EjercicioAlbaran', 'EjercicioPedido', 'Ejercicio')
_EMPRESAS = ('CodigoEmpresa', 'Empresa')
_ETIQUETAS = (
    ('razon', 'social'),
    ('descripcion',),
    ('nombre',),
)


def _plegar(texto):
    raw = unicodedata.normalize('NFD', texto or '')
    raw = ''.join(ch for ch in raw if unicodedata.category(ch) != 'Mn')
    return raw.lower()


def _trocear(nombre):
    texto = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', nombre or '')
    texto = re.sub(r'[^0-9A-Za-z]+', ' ', texto)
    return [t for t in _plegar(texto).split() if t]


def _sanear(nombre):
    texto = (nombre or '').strip().lower()
    texto = re.sub(r'\s+', '_', texto)
    texto = texto.replace('.', '_')
    return re.sub(r'[^a-z0-9_]', '', texto)


def _cita(nombre):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', nombre or ''):
        return None
    return f'"{nombre}"'


def _palabra(token, folded):
    for hallado in re.finditer(r'\b' + re.escape(token) + r'\w*\b', folded or ''):
        palabra = hallado.group(0)
        if palabra == token or (len(token) >= 5 and palabra.startswith(token)):
            return True
    return False


def _puntos(nombre, folded):
    piezas = [t for t in _trocear(nombre) if t not in _GENERICOS and len(t) >= 4]
    if not piezas or not all(_palabra(t, folded) for t in piezas):
        return 0
    return sum(len(t) for t in piezas)


def _puntuacion(campo, folded):
    return max(_puntos(campo.field_name, folded), _puntos(campo.business_name, folded))


def nombre_fisico(campo, columnas):
    """Nombre real en Postgres. columnas es el conjunto en minúsculas."""
    candidatos = []
    for nombre in (getattr(campo, 'business_name', ''), getattr(campo, 'field_name', '')):
        sano = _sanear(nombre)
        if sano:
            candidatos.append(sano)
        bajo = (nombre or '').strip().lower()
        if bajo:
            candidatos.append(bajo)
    for candidato in candidatos:
        if candidato in columnas and _cita(candidato):
            return candidato
    return None


def _columnas(tabla):
    alias = 'analytics' if 'analytics' in connections.databases else 'default'
    with connections[alias].cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            [(tabla or '').lower()],
        )
        return {fila[0].lower() for fila in cur.fetchall()}


def _cargar():
    campos = []
    for field in DataField.objects.filter(is_active=True, source__is_active=True).select_related('source'):
        local = field.source.get_local_table_name()
        if not local:
            continue
        campos.append({
            'id': field.id,
            'papel': papel_de(field.usage_type, field.field_name, field.business_name),
            'field_name': field.field_name,
            'business_name': field.business_name or '',
            'source_id': field.source_id,
            'source_table': field.source.source_table,
            'local': local,
            'is_key': bool(field.is_key),
        })
    return campos


def _objeto(ficha):
    return type('Campo', (), ficha)


def elegir(pregunta, campos):
    """Cifra obligatoria y, si la frase lo nombra, un agrupador o una fecha."""
    folded = _plegar(pregunta)
    if not folded:
        return None
    cifras = []
    cortes = []
    for ficha in campos:
        campo = ficha if hasattr(ficha, 'field_name') else _objeto(ficha)
        puntos = _puntuacion(campo, folded)
        if puntos <= 0 or not getattr(campo, 'papel', None):
            continue
        if campo.papel == 'cifra':
            cifras.append((puntos, campo))
        elif campo.papel in ('agrupador', 'nombre', 'fecha'):
            cortes.append((puntos, campo))
    if not cifras:
        return None
    mejor = max(punto for punto, _campo in cifras)
    finalistas = [campo for punto, campo in cifras if punto == mejor]
    cifra = _afinar(finalistas, folded)
    corte = None
    if cortes:
        mejor_corte = max(punto for punto, _campo in cortes)
        opciones = [
            campo for punto, campo in cortes
            if punto == mejor_corte and campo.id != cifra.id
        ]
        if opciones:
            corte = _afinar(opciones, folded)
    if corte is not None:
        mismas = [campo for campo in finalistas if campo.source_id == corte.source_id]
        if mismas:
            cifra = _afinar(mismas, folded)
    return cifra, corte


def _afinar(candidatos, folded):
    def rango(campo):
        tabla = _plegar(campo.source_table)
        compra = bool(re.search(r'\b(compra|proveedor)\w*', folded))
        venta = bool(re.search(r'\b(venta|cliente|albaran)\w*', folded))
        if compra and 'proveedor' in tabla:
            return 0
        if venta and 'cliente' in tabla and 'proveedor' not in tabla:
            return 0
        if 'albaran' in tabla and 'cliente' in tabla:
            return 1
        return 2

    return sorted(candidatos, key=rango)[0]


def _camino(desde, hasta):
    if desde == hasta:
        return []
    grupos = _grupos_de_todos(desde, hasta)
    directo = _tramo(desde, hasta, grupos)
    if directo:
        return [directo]
    vecinos = set()
    for origen, destino in grupos:
        if origen == desde:
            vecinos.add(destino)
        elif destino == desde:
            vecinos.add(origen)
    mejor = None
    for medio in vecinos:
        if medio == hasta:
            continue
        primero = _tramo(desde, medio, grupos)
        segundo = _tramo(medio, hasta, grupos)
        if not primero or not segundo:
            continue
        claves = len(primero[2]) + len(segundo[2])
        if mejor is None or claves > mejor[0]:
            mejor = (claves, [primero, segundo])
    return mejor[1] if mejor else None


def _grupos_de_todos(desde, hasta):
    """Relaciones que salen de las tablas del camino, no solo el par directo."""
    filas = DataRelation.objects.filter(
        Q(source_id=desde) | Q(target_id=desde) | Q(source_id=hasta) | Q(target_id=hasta)
    ).select_related('source', 'target', 'from_field', 'to_field')
    grupos = {}
    for rel in filas:
        grupos.setdefault((rel.source_id, rel.target_id), []).append(rel)
    return grupos


def _tramo(desde, hasta, grupos):
    if (desde, hasta) in grupos:
        return (desde, hasta, grupos[(desde, hasta)])
    if (hasta, desde) in grupos:
        return (hasta, desde, grupos[(hasta, desde)])
    return None


def _asegurar(columnas, source_id, local):
    if source_id not in columnas:
        columnas[source_id] = _columnas(local)
    return columnas[source_id]


def _fisico_de_relacion(rel, actual, columnas):
    if rel.source_id == actual:
        izquierda = nombre_fisico(rel.from_field, _asegurar(columnas, rel.source_id, rel.source.get_local_table_name()))
        derecha = nombre_fisico(rel.to_field, _asegurar(columnas, rel.target_id, rel.target.get_local_table_name()))
        nuevo = rel.target_id
        tabla = rel.target.get_local_table_name()
    elif rel.target_id == actual:
        izquierda = nombre_fisico(rel.to_field, _asegurar(columnas, rel.target_id, rel.target.get_local_table_name()))
        derecha = nombre_fisico(rel.from_field, _asegurar(columnas, rel.source_id, rel.source.get_local_table_name()))
        nuevo = rel.source_id
        tabla = rel.source.get_local_table_name()
    else:
        return None
    if not izquierda or not derecha or not tabla:
        return None
    return nuevo, tabla, (izquierda, derecha)


def _saltos(cifra, corte, columnas):
    if corte is None or corte.source_id == cifra.source_id:
        return []
    tramos = _camino(cifra.source_id, corte.source_id)
    if not tramos:
        return None
    actual = cifra.source_id
    saltos = []
    for _origen, _destino, relaciones in tramos:
        pares = []
        nuevo = None
        tabla = None
        for rel in relaciones:
            pieza = _fisico_de_relacion(rel, actual, columnas)
            if not pieza:
                return None
            este, tabla, par = pieza
            if nuevo is None:
                nuevo = este
            elif este != nuevo:
                return None
            pares.append(par)
        if not pares or nuevo is None:
            return None
        saltos.append({'tabla': tabla, 'pares': pares, 'source_id': nuevo})
        actual = nuevo
    if actual != corte.source_id:
        return None
    return saltos


def _columna_de(campos, source_id, nombres, columnas):
    por_nombre = {}
    for campo in campos:
        if campo.source_id == source_id:
            por_nombre[campo.field_name] = campo
    for nombre in nombres:
        campo = por_nombre.get(nombre)
        if campo is None:
            continue
        fisico = nombre_fisico(campo, columnas)
        if fisico:
            return fisico
    return None


def _etiqueta(corte, campos, columnas):
    if corte is None:
        return None, None
    grupo = nombre_fisico(corte, columnas.get(corte.source_id, set()))
    if not grupo:
        return None, None
    mejor = None
    for campo in campos:
        if campo.source_id != corte.source_id or campo.id == corte.id:
            continue
        piezas = set(_trocear(campo.field_name)) | set(_trocear(campo.business_name))
        for indice, buscada in enumerate(_ETIQUETAS):
            if all(token in piezas for token in buscada):
                fisico = nombre_fisico(campo, columnas.get(corte.source_id, set()))
                if fisico and (mejor is None or indice < mejor[0]):
                    mejor = (indice, fisico)
                break
    if mejor is None:
        return grupo, grupo
    return grupo, mejor[1]


def _limite(pregunta, tope):
    folded = _plegar(pregunta)
    hallado = re.search(r'\b(?:top|primeros|primeras|los|las)\s+(\d{1,3})\b', folded or '')
    try:
        numero = int(hallado.group(1) if hallado else tope or 20)
    except (TypeError, ValueError):
        numero = 20
    if numero < 1:
        return 1
    if numero > 100:
        return 100
    return numero


def _anio(pregunta, ejercicio):
    hallado = re.search(r'\b(20\d{2})\b', pregunta or '')
    try:
        return int(hallado.group(1) if hallado else ejercicio)
    except (TypeError, ValueError):
        return None


def _orden(pregunta):
    folded = _plegar(pregunta)
    if re.search(r'\b(menos|peor|peores|menor|menores)\b', folded) and not re.search(
        r'\b(mas|mayor|mayores|mejor|mejores|top)\b', folded,
    ):
        return 'ASC'
    return 'DESC'


def compilar_sql(cifra, corte, campos, columnas, saltos, empresa, year, limite, orden):
    tabla = _cita(cifra.local)
    col_cifra = _cita(nombre_fisico(cifra, columnas.get(cifra.source_id, set())))
    empresa_col = _cita(_columna_de(campos, cifra.source_id, _EMPRESAS, columnas.get(cifra.source_id, set())))
    if not tabla or not col_cifra or not empresa_col:
        return None
    anio_col = _cita(_columna_de(campos, cifra.source_id, _ANIOS, columnas.get(cifra.source_id, set())))
    grupo, visible = (None, None)
    if corte is not None:
        grupo, visible = _etiqueta(corte, campos, columnas)
        grupo = _cita(grupo)
        visible = _cita(visible)
        if not grupo or not visible:
            return None
    alias = 't1'
    joins = []
    for indice, salto in enumerate(saltos or [], start=2):
        siguiente = f't{indice}'
        tabla_salto = _cita(salto['tabla'])
        if not tabla_salto:
            return None
        pares = []
        for izquierda, derecha in salto['pares']:
            izq = _cita(izquierda)
            der = _cita(derecha)
            if not izq or not der:
                return None
            pares.append(f'{alias}.{izq} = {siguiente}.{der}')
        joins.append(f'JOIN {tabla_salto} {siguiente} ON ' + ' AND '.join(pares))
        alias = siguiente
    where = [f't1.{empresa_col} = {int(empresa)}']
    if anio_col and year is not None:
        where.append(f't1.{anio_col} = {int(year)}')
    if grupo:
        if visible == grupo:
            select = f'SELECT {alias}.{grupo} AS label, SUM(t1.{col_cifra}) AS val'
            group = ' GROUP BY 1'
        else:
            select = (
                f"SELECT COALESCE(NULLIF(BTRIM(MAX({alias}.{visible})::text), ''), "
                f"MAX({alias}.{grupo})::text) AS label, SUM(t1.{col_cifra}) AS val"
            )
            group = f' GROUP BY {alias}.{grupo}'
    else:
        select = f"SELECT 'Total' AS label, SUM(t1.{col_cifra}) AS val"
        group = ''
    sql = (
        f'{select} FROM {tabla} t1 {" ".join(joins)}'
        f' WHERE {" AND ".join(where)}{group}'
        f' ORDER BY val {orden} LIMIT {int(limite)}'
    )
    return ' '.join(sql.split())


def _mapa(campos, extra_ids):
    columnas = {}
    vistos = set()
    for campo in campos:
        if campo.source_id in vistos:
            continue
        vistos.add(campo.source_id)
        columnas[campo.source_id] = _columnas(campo.local)
    for source_id in extra_ids:
        if source_id not in columnas:
            from datia.models.semantic import DataSource
            origen = DataSource.objects.filter(id=source_id).first()
            if origen and origen.get_local_table_name():
                columnas[source_id] = _columnas(origen.get_local_table_name())
    return columnas


def _explicar(sql):
    alias = 'analytics' if 'analytics' in connections.databases else 'default'
    try:
        with connections[alias].cursor() as cur:
            cur.execute('EXPLAIN ' + sql)
        return True
    except Exception as exc:
        logger.info('Compilador: la base rechazó la consulta del mapeo: %s', exc)
        return False


def responder(pregunta, empresa, ejercicio, limite=20):
    """Consulta del mapeo, o None si la frase no nombra una cifra activa."""
    try:
        empresa_id = int(empresa)
    except (TypeError, ValueError):
        return None
    campos = [_objeto(ficha) for ficha in _cargar()]
    elegido = elegir(pregunta, campos)
    if not elegido:
        return None
    cifra, corte = elegido
    year = _anio(pregunta, ejercicio)
    columnas = _mapa(campos, [cifra.source_id] + ([corte.source_id] if corte else []))
    saltos = _saltos(cifra, corte, columnas)
    if saltos is None:
        return None
    sql = compilar_sql(
        cifra, corte, campos, columnas, saltos,
        empresa_id, year, _limite(pregunta, limite), _orden(pregunta),
    )
    if not sql:
        return None
    from datia.services.security.sql_guard import SQLGuard
    if not SQLGuard.check_sql(sql).get('allowed'):
        logger.info('Compilador: la consulta sale de las tablas permitidas')
        return None
    if not _explicar(sql):
        return None
    from datia.services.ai.open_question import OpenQuestion
    titulo = cifra.business_name or cifra.field_name
    if corte is not None:
        titulo = f'{titulo} por {corte.business_name or corte.field_name}'
    return OpenQuestion._match(sql, titulo, 'table', year, source='mapeo')
