"""Examen de cien preguntas sobre los datos mapeados, con la cifra que sale de la tabla."""
import logging
import re

from django.db import connections

logger = logging.getLogger('datia')


def _alias():
    return 'analytics' if 'analytics' in connections.databases else 'default'


def _cerca(obtenido, esperado) -> bool:
    try:
        a = float(obtenido)
        b = float(esperado)
    except (TypeError, ValueError):
        return False
    return abs(a - b) <= max(0.05, abs(b) * 0.001)


def _euros(valor) -> str:
    return f"{float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'


def _aplanar(respuesta):
    resp = dict(respuesta or {})
    anidada = resp.get('reply')
    if isinstance(anidada, dict):
        resp.update(anidada)
    return resp


def _texto(resp) -> str:
    return f"{resp.get('text') or ''} {resp.get('answer') or ''}".strip()


def _es_euro(kpi) -> bool:
    suffix = str((kpi or {}).get('suffix') or '')
    label = str((kpi or {}).get('label') or '')
    return '€' in suffix or '€' in label or 'eur' in label.casefold()


def _principal(kpis):
    if not kpis:
        return None
    return kpis[0].get('value')


def _importes_tabla(filas):
    salida = []
    for fila in filas or []:
        if not isinstance(fila, (list, tuple)) or len(fila) < 2:
            continue
        for celda in fila[1:]:
            try:
                salida.append(float(celda))
                break
            except (TypeError, ValueError):
                continue
    return salida


def _vals_data(resp):
    salida = []
    for fila in resp.get('data') or []:
        if not isinstance(fila, dict) or 'val' not in fila:
            continue
        try:
            salida.append(float(fila.get('val') or 0))
        except (TypeError, ValueError):
            continue
    return salida


def _primera_columna(filas):
    textos = []
    for fila in filas or []:
        if isinstance(fila, (list, tuple)) and fila and fila[0] is not None:
            textos.append(str(fila[0]).strip())
    return textos


def _en_orden(texto, esperados):
    pos = 0
    for item in esperados:
        hallado = (texto or '').find(item, pos)
        if hallado < 0:
            return False
        pos = hallado + len(item)
    return True


def _totales_serie(resp):
    filas = [fila for fila in (resp.get('data') or []) if isinstance(fila, dict)]
    if not filas:
        return []
    claves = [str(clave) for clave in filas[0].keys() if re.fullmatch(r'20\d{2}', str(clave))]
    if not claves:
        return []
    totales = []
    for clave in sorted(claves):
        acumulado = 0.0
        for fila in filas:
            try:
                acumulado += float(fila.get(clave) or 0)
            except (TypeError, ValueError):
                continue
        totales.append(acumulado)
    return totales


def _numeros_en_texto(texto):
    encontrados = []
    for crudo in re.findall(r'\d{1,3}(?:\.\d{3})+,\d+|\d+,\d+|\d+\.\d+|\d+', texto or ''):
        limpio = crudo
        if ',' in limpio and '.' in limpio:
            limpio = limpio.replace('.', '').replace(',', '.')
        elif ',' in limpio:
            limpio = limpio.replace(',', '.')
        try:
            encontrados.append(float(limpio))
        except ValueError:
            continue
    return encontrados


def clasificar(spec, respuesta) -> str:
    """Devuelve cifra_tabla, otra_cifra o sin_respuesta."""
    resp = _aplanar(respuesta)
    texto = _texto(resp)
    kpis = resp.get('kpis') or []
    filas = ((resp.get('table') or {}).get('rows')) or []
    fallo = 'no he podido' in texto.casefold() or 'error al procesar' in texto.casefold()
    modo = spec.get('modo')
    datos = resp.get('data') or []

    if modo == 'rechazo':
        esperado = str(spec.get('texto') or '')
        hay_dato = bool(kpis or filas or datos or _numeros_en_texto(texto))
        if hay_dato:
            return 'otra_cifra'
        if esperado and esperado not in texto:
            return 'otra_cifra'
        return 'cifra_tabla'

    if spec.get('vinculo') == 'continuacion':
        if resp.get('vinculo') != 'continuacion':
            return 'otra_cifra'
        if list(resp.get('sustituye') or []) != list(spec.get('sustituye') or []):
            return 'otra_cifra'
    if spec.get('vinculo') == 'sola' and resp.get('hereda'):
        return 'otra_cifra'

    if modo == 'sin_cifra':
        if kpis or filas or _numeros_en_texto(texto):
            return 'otra_cifra'
        return 'sin_respuesta'

    if modo == 'conteo' and spec.get('valor') == 0 and re.search(r'\bno hay\b', texto, re.I):
        return 'cifra_tabla'
    if modo == 'importe' and spec.get('valor') == 0 and re.search(r'\bno hay\b', texto, re.I):
        return 'cifra_tabla'

    if fallo and not kpis and not filas and not datos:
        return 'sin_respuesta'
    if not kpis and not filas and not datos and not _numeros_en_texto(texto):
        return 'sin_respuesta'

    if modo == 'conteo':
        esperado = spec.get('valor')
        principal = _principal(kpis)
        if principal is not None:
            if _es_euro(kpis[0]) and not _cerca(principal, esperado):
                return 'otra_cifra'
            if _cerca(principal, esperado):
                return 'cifra_tabla'
            return 'otra_cifra'
        vals = _vals_data(resp)
        if vals and _cerca(vals[0], esperado):
            return 'cifra_tabla'
        if any(_cerca(n, esperado) for n in _numeros_en_texto(texto)):
            return 'cifra_tabla'
        return 'otra_cifra'

    if modo == 'importe':
        esperado = spec.get('valor')
        principal = _principal(kpis)
        if principal is not None and _cerca(principal, esperado):
            return 'cifra_tabla'
        if principal is not None:
            return 'otra_cifra'
        vals = _vals_data(resp)
        if len(vals) == 1 and _cerca(vals[0], esperado):
            return 'cifra_tabla'
        if any(_cerca(n, esperado) for n in _numeros_en_texto(texto)):
            return 'cifra_tabla'
        return 'otra_cifra'

    if modo == 'lista':
        esperados = [float(n) for n in (spec.get('importes') or [])]
        obtenidos = _importes_tabla(filas) or _vals_data(resp)
        if not obtenidos:
            return 'sin_respuesta' if not kpis else 'otra_cifra'
        if len(obtenidos) == len(esperados) and all(_cerca(a, b) for a, b in zip(obtenidos, esperados)):
            return 'cifra_tabla'
        return 'otra_cifra'

    if modo == 'textos':
        esperados = [str(item).strip() for item in (spec.get('textos') or []) if str(item).strip()]
        if not esperados:
            return 'sin_respuesta'
        if filas:
            if _primera_columna(filas)[:len(esperados)] == esperados:
                return 'cifra_tabla'
            return 'otra_cifra'
        if _en_orden(texto, esperados):
            return 'cifra_tabla'
        return 'otra_cifra' if texto else 'sin_respuesta'

    if modo == 'cifras':
        esperados = [float(n) for n in (spec.get('importes') or [])]
        if not esperados:
            return 'sin_respuesta'
        obtenidos = _totales_serie(resp)
        if len(obtenidos) == len(esperados) and all(_cerca(a, b) for a, b in zip(obtenidos, esperados)):
            return 'cifra_tabla'
        numeros = _numeros_en_texto(texto)
        if numeros and all(any(_cerca(n, esp) for n in numeros) for esp in esperados):
            return 'cifra_tabla'
        return 'otra_cifra' if (obtenidos or numeros or datos) else 'sin_respuesta'

    if modo == 'listado':
        total = spec.get('valor')
        esperados = [str(item).strip() for item in (spec.get('textos') or []) if str(item).strip()]
        familias = [str(item).strip() for item in (spec.get('familias') or [])]
        principal = _principal(kpis)
        coincide_total = principal is not None and _cerca(principal, total)
        if not coincide_total and len(filas) != int(total or -1):
            return 'otra_cifra' if (filas or kpis or datos) else 'sin_respuesta'
        if esperados and _primera_columna(filas)[:len(esperados)] != esperados:
            return 'otra_cifra'
        if familias:
            columnas = ((resp.get('table') or {}).get('columns')) or []
            indice = next((i for i, columna in enumerate(columnas) if 'familia' in str(columna).casefold()), None)
            if indice is None:
                return 'otra_cifra'
            obtenidas = []
            for fila in filas[:len(familias)]:
                if isinstance(fila, (list, tuple)) and len(fila) > indice and fila[indice] is not None:
                    obtenidas.append(str(fila[indice]).strip())
                else:
                    obtenidas.append('')
            if obtenidas != familias:
                return 'otra_cifra'
        return 'cifra_tabla'

    return 'sin_respuesta'


def _leer_efectos_pago(empresa, year):
    sql = """
        SELECT COALESCE(NULLIF(BTRIM(p.descripcion), ''), c.codigo_titular) AS nombre,
               (c.importe - c.importe_cobrado) AS pendiente
        FROM datia_financial_cartera c
        LEFT JOIN datia_financial_plan p
          ON p.empresa = c.empresa
         AND p.ejercicio = c.ejercicio
         AND p.codigo = c.codigo_titular
        WHERE c.empresa = %s
          AND c.ejercicio = %s
          AND c.tipo_efecto = 'P'
          AND COALESCE(c.estado, '') NOT IN ('COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO')
          AND (c.importe - c.importe_cobrado) > 0.01
        ORDER BY pendiente DESC
    """
    with connections[_alias()].cursor() as cur:
        cur.execute(sql, [int(empresa), int(year)])
        rows = cur.fetchall()
    return [
        {'nombre': str(nombre or 'Sin nombre').strip(), 'pendiente': float(pendiente or 0)}
        for nombre, pendiente in rows
    ]


def _banco(efectos):
    total = round(sum(fila['pendiente'] for fila in efectos), 2)
    top = efectos[:10]
    importes = [round(fila['pendiente'], 2) for fila in top]
    titular = top[0]['nombre'] if top else ''
    del_titular = [fila for fila in efectos if fila['nombre'] == titular][:10] if titular else []
    preguntas = [
        {
            'pregunta': 'cuantos efectos de pago siguen pendientes',
            'modo': 'conteo',
            'valor': len(efectos),
            'esperado': f'{len(efectos)} efectos',
        },
        {
            'pregunta': 'cual es el importe pendiente de pago',
            'modo': 'importe',
            'valor': total,
            'esperado': _euros(total),
        },
        {
            'pregunta': 'muestra una lista de los 10 efectos pendientes de pago de mayor importe',
            'modo': 'lista',
            'importes': importes,
            'esperado': ', '.join(_euros(n) for n in importes) or 'ningún efecto',
        },
    ]
    if titular:
        preguntas.append({
            'pregunta': f'lista de los efectos pendientes de pago de {titular} de mayor importe',
            'modo': 'lista',
            'importes': [round(fila['pendiente'], 2) for fila in del_titular],
            'esperado': ', '.join(_euros(fila['pendiente']) for fila in del_titular),
        })
    preguntas.append({
        'pregunta': 'dime cuantas facturas tengo pendientes de cobrar',
        'modo': 'sin_cifra',
        'esperado': 'No hay columna de factura. La respuesta fiel no da un número de facturas.',
    })
    return preguntas


_ETIQUETAS = {
    'cifra_tabla': 'Cifra de la tabla',
    'otra_cifra': 'Otra cifra',
    'sin_respuesta': 'Sin respuesta',
}


_TOPE = 100
_CACHE = {}
_CODIGO = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._\-]{0,40}$')


def _sin_modelo(*_args, **_kwargs):
    return None


def _numero(valor):
    numero = round(float(valor or 0), 2)
    if numero == int(numero):
        return int(numero)
    return numero


def _codigo_usable(valor):
    texto = str(valor or '').strip()
    if not texto or not _CODIGO.fullmatch(texto) or not re.search(r'\d', texto):
        return ''
    return texto


def _codigos(sql, params, limite):
    alias = _alias()
    try:
        with connections[alias].cursor() as cur:
            cur.execute(sql, params)
            filas = cur.fetchall()
    except Exception:
        logger.exception('Examen: no se pudieron leer los códigos')
        connections[alias].rollback()
        return []
    vistos = []
    for fila in filas:
        codigo = _codigo_usable(fila[0] if fila else '')
        if codigo and codigo not in vistos:
            vistos.append(codigo)
        if len(vistos) >= limite:
            break
    return vistos


_FRASE_CATALOGO = 'lista de todos los articulos con el codigo, la descripcion y la familia'


def _frases(ejercicio, articulos, clientes):
    anio = int(ejercicio)
    previo = anio - 1
    frases = [
        _FRASE_CATALOGO,
        'ventas del ejercicio',
        f'ventas del ejercicio {anio}',
        f'ventas del ejercicio {previo}',
        'compras del ejercicio',
        f'compras del ejercicio {anio}',
        f'compras del ejercicio {previo}',
        'cuantos articulos hay',
        'cuantos clientes hay',
        'cuantos proveedores hay',
        'lista de articulos con el codigo y descripcion',
        'lista de clientes con el codigo y el nombre',
        'lista de proveedores con el codigo y el nombre',
        f'grafica de ventas comparativa {previo} vs {anio}',
        f'grafica de compras comparativa {previo} vs {anio}',
        'ventas por cliente',
        'compras por proveedor',
        'ventas por articulo',
        'compras por articulo',
    ]
    for codigo in articulos:
        frases.append(f'ventas del producto {codigo}')
        frases.append(f'compras del producto {codigo}')
        frases.append(f'cuantos clientes han comprado el producto {codigo}')
        frases.append(f'que clientes han comprado el producto {codigo}')
        frases.append(f'ventas del producto {codigo} en {previo}')
    for codigo in clientes:
        frases.append(f'ventas del cliente {codigo}')
    return frases


def _ejecutar(sql):
    with connections[_alias()].cursor() as cur:
        cur.execute(sql)
        columnas = [col[0] for col in cur.description]
        return columnas, cur.fetchall()


def _spec_de(pregunta, salida):
    sql = salida.get('sql') or ''
    tipo = salida.get('type')
    columnas, filas = _ejecutar(sql)
    nombres = [str(col).lower() for col in columnas]
    if tipo == 'listado':
        textos = [
            str(fila[0]).strip()
            for fila in filas[:12]
            if fila and fila[0] is not None and str(fila[0]).strip()
        ]
        if not textos:
            return None
        if salida.get('completo'):
            titulos = [str(titulo).casefold() for titulo in (salida.get('titulos') or [])]
            indice = next((i for i, titulo in enumerate(titulos) if 'familia' in titulo), None)
            muestra = textos[:8]
            familias = []
            if indice is not None:
                for fila in filas[:len(muestra)]:
                    valor = fila[indice] if fila and len(fila) > indice else ''
                    familias.append('' if valor is None else str(valor).strip())
            return {
                'pregunta': pregunta,
                'modo': 'listado',
                'valor': len(filas),
                'textos': muestra,
                'familias': familias,
                'esperado': f'{len(filas)} registros. ' + ', '.join(muestra),
            }
        muestra = textos[:8]
        return {
            'pregunta': pregunta,
            'modo': 'textos',
            'textos': textos,
            'esperado': ', '.join(muestra) + ('…' if len(textos) > 8 else ''),
        }
    if tipo == 'chart':
        if 'val' not in nombres:
            return None
        idx_val = nombres.index('val')
        idx_serie = nombres.index('serie') if 'serie' in nombres else None
        totales = {}
        for fila in filas:
            if idx_serie is None or fila[idx_serie] is None:
                clave = 'total'
            else:
                clave = str(int(fila[idx_serie]))
            totales[clave] = totales.get(clave, 0.0) + float(fila[idx_val] or 0)
        if not totales:
            return None
        importes = [_numero(totales[clave]) for clave in sorted(totales)]
        return {
            'pregunta': pregunta,
            'modo': 'cifras',
            'importes': importes,
            'esperado': ' y '.join(_euros(n) for n in importes),
        }
    if 'val' not in nombres:
        return None
    idx_val = nombres.index('val')
    valores = [_numero(fila[idx_val]) for fila in filas] or [0]
    if 'count(' in sql.casefold() and len(valores) == 1:
        return {
            'pregunta': pregunta,
            'modo': 'conteo',
            'valor': valores[0],
            'esperado': f'{int(valores[0])} registros',
        }
    if len(valores) <= 1:
        return {
            'pregunta': pregunta,
            'modo': 'importe',
            'valor': valores[0],
            'esperado': _euros(valores[0]),
        }
    return {
        'pregunta': pregunta,
        'modo': 'lista',
        'importes': valores,
        'esperado': ', '.join(_euros(n) for n in valores[:5]) + ('…' if len(valores) > 5 else ''),
    }


_FORMAS = (
    'filtrar', 'varios_filtros', 'agrupar', 'sumar', 'contar', 'promediar',
    'maximo', 'minimo', 'listar', 'conjunto', 'numero', 'periodo',
    'comparacion', 'tabla', 'grafica',
)
_CACHE_REVISION = 3


def _frases_forma(ejercicio):
    anio = int(ejercicio)
    previo = anio - 1
    return {
        'filtrar': 'ventas del producto 01110',
        'varios_filtros': 'ventas del producto 01110 del cliente 43000008820',
        'agrupar': 'ventas por cliente',
        'sumar': 'ventas del ejercicio',
        'contar': 'cuantos clientes hay',
        'promediar': 'promedio de ventas del ejercicio',
        'maximo': 'maximo de ventas del ejercicio',
        'minimo': 'minimo de ventas del ejercicio',
        'listar': 'lista de articulos con el codigo y la descripcion',
        'conjunto': 'lista de todos los articulos con el codigo, la descripcion y la familia',
        'numero': 'los 10 primeros articulos con el codigo y la descripcion',
        'periodo': f'ventas del ejercicio {anio}',
        'comparacion': f'grafica de ventas comparativa {previo} vs {anio}',
        'tabla': 'ventas por cliente',
        'grafica': f'grafica de ventas comparativa {previo} vs {anio}',
    }


def _frase_sola_distinta(frase):
    if 'articulo' in frase:
        return 'ventas del ejercicio'
    return 'lista de todos los articulos con el codigo y la descripcion'


def _lectura_publica(salida):
    lectura = (salida or {}).get('lectura') or {}
    return lectura if lectura.get('plan') else None


def cubrir_territorio(campos, relaciones, columnas, ejercicio, consultar_fn):
    """Una pregunta por columna, relación y forma, más la pareja de memoria. No es el producto cartesiano."""
    from datia.services.ai.compilador_mapeo import nombre_fisico
    from datia.services.ai.interprete_mapeo import _MENSAJE

    preguntas = []
    faltan = []
    sqls = []

    def anotar(pieza, frase, vinculo='sola', lectura_previa=None, sustituye=None):
        try:
            salida = consultar_fn(frase, lectura_previa)
        except Exception:
            logger.exception('Examen: no se pudo preparar %s', frase)
            faltan.append(pieza)
            return None
        if not isinstance(salida, dict) or salida.get('reply') or not salida.get('sql'):
            faltan.append(pieza)
            return None
        if vinculo == 'continuacion' and salida.get('vinculo') != 'continuacion':
            faltan.append(pieza)
            return None
        if vinculo == 'sola' and salida.get('vinculo') not in (None, 'sola'):
            faltan.append(pieza)
            return None
        if vinculo == 'sola' and salida.get('hereda'):
            faltan.append(pieza)
            return None
        item = {
            'pregunta': frase,
            'vinculo': salida.get('vinculo') or vinculo,
            'pieza': pieza,
            'sql': salida.get('sql') or '',
            'salida': salida,
            'lectura_previa': lectura_previa,
            'sustituye': list(salida.get('sustituye') or sustituye or []),
            'hereda': list(salida.get('hereda') or []),
            'es_probe': False,
        }
        preguntas.append(item)
        sqls.append(item['sql'].lower())
        return item

    formas = _frases_forma(ejercicio)
    for forma in _FORMAS:
        base = anotar(f'forma:{forma}', formas[forma])
        if base is None:
            faltan.append(f'pareja:{forma}')
            continue
        previo = int(ejercicio) - 1
        anotar(
            f'pareja:{forma}:continuacion',
            f'y en {previo}',
            vinculo='continuacion',
            lectura_previa=_lectura_publica(base['salida']),
            sustituye=['periodo'],
        )
        anotar(f'pareja:{forma}:sola', _frase_sola_distinta(formas[forma]), vinculo='sola')

    for campo in campos:
        fisico = nombre_fisico(campo, columnas.get(campo.source_id, set()) if isinstance(columnas, dict) else set())
        token = str(fisico or '').lower()
        if token and any(token in sql for sql in sqls):
            continue
        faltan.append(f'columna:{getattr(campo, "business_name", None) or getattr(campo, "field_name", campo.id)}')

    vistos = set()
    for relacion in relaciones or []:
        par = (relacion.source_id, relacion.target_id)
        if par in vistos:
            continue
        vistos.add(par)
        origen = str(getattr(relacion.source, 'get_local_table_name', lambda: '')() or '').lower()
        destino = str(getattr(relacion.target, 'get_local_table_name', lambda: '')() or '').lower()
        if origen and destino and any(origen in sql and destino in sql for sql in sqls):
            continue
        faltan.append('relacion:' + str(par[0]) + '-' + str(par[1]))

    probes = []
    for frase, texto in (
        ('que tiempo hace hoy', ''),
        ('listado de clientes con el motivo', _MENSAJE),
    ):
        try:
            salida = consultar_fn(frase, None)
        except Exception:
            salida = None
        respuesta = ''
        if isinstance(salida, dict):
            respuesta = ((salida.get('reply') or {}).get('answer')) or salida.get('answer') or ''
        probes.append({
            'pregunta': frase,
            'vinculo': 'rechazo',
            'es_probe': True,
            'modo': 'rechazo',
            'texto': texto,
            'esperado': texto or 'Sin cifra de la empresa',
            'respuesta': respuesta,
        })
    return {
        'preguntas': preguntas,
        'probes': probes,
        'incompleta': bool(faltan),
        'falta': faltan[0] if faltan else '',
        'faltan': faltan,
    }


def revision_aceptada(incompleta, coinciden, total, rechazos, probes) -> bool:
    """Solo se acepta con territorio completo, todas las preguntas coincidiendo y todos los probes rechazados."""
    return (not incompleta) and total > 0 and coinciden == total and rechazos == probes


def empaquetar_revision(empresa, ejercicio, preguntas, probes, incompleta, falta, aviso=''):
    visibles = []
    for spec in list(preguntas or []) + list(probes or []):
        visibles.append({
            'pregunta': spec.get('pregunta') or '',
            'esperado': spec.get('esperado') or '',
            'vinculo': spec.get('vinculo') or '',
            'es_probe': bool(spec.get('es_probe')),
            'pieza': spec.get('pieza') or '',
        })
    return {
        'empresa': int(empresa),
        'ejercicio': int(ejercicio),
        'estado': 'Preparada',
        'aviso': aviso,
        'incompleta': bool(incompleta),
        'falta': falta or '',
        'territorio': len(preguntas or []),
        'probes': [
            {'pregunta': item.get('pregunta') or '', 'esperado': item.get('esperado') or ''}
            for item in (probes or [])
        ],
        'puede_aceptarse': False,
        'total': len(visibles),
        'preguntas': [
            {'indice': i, **item}
            for i, item in enumerate(visibles)
        ],
    }


def _banco_mapeado(empresa, ejercicio):
    from datia.services.ai.compilador_mapeo import _mapa
    from datia.services.ai.interprete_mapeo import _cargar as cargar_catalogo
    from datia.services.ai.interprete_mapeo import consultar

    campos, relaciones = cargar_catalogo()
    columnas = _mapa(campos, [])
    anio = int(ejercicio)
    articulos = _codigos(
        """
        SELECT codigoarticulo
        FROM datiadb_lineasalbarancliente
        WHERE codigoempresa = %s AND ejercicioalbaran = %s
        GROUP BY 1
        ORDER BY SUM(importeneto) DESC
        LIMIT 30
        """,
        [empresa, anio],
        22,
    )
    clientes = _codigos(
        """
        SELECT codigocliente
        FROM datiadb_cabeceraalbarancliente
        WHERE codigoempresa = %s AND ejercicioalbaran = %s
        GROUP BY 1
        ORDER BY SUM(importeneto) DESC
        LIMIT 20
        """,
        [empresa, anio],
        12,
    )
    banco = []
    catalogo = None
    vistas = set()
    alias = _alias()
    for frase in _frases(anio, articulos, clientes):
        if frase in vistas:
            continue
        vistas.add(frase)
        try:
            salida = consultar(
                frase,
                empresa,
                anio,
                10,
                campos=campos,
                relaciones=relaciones,
                columnas=columnas,
                pedir=_sin_modelo,
                sondear=False,
            )
        except Exception:
            logger.exception('Examen: la pregunta no se pudo preparar')
            connections[alias].rollback()
            continue
        if not isinstance(salida, dict) or salida.get('reply') or not salida.get('sql'):
            continue
        try:
            spec = _spec_de(frase, salida)
        except Exception:
            logger.exception('Examen: no se pudo calcular la cifra esperada')
            connections[alias].rollback()
            continue
        if not spec:
            continue
        spec['vinculo'] = (salida.get('vinculo') or 'sola')
        spec['sustituye'] = list(salida.get('sustituye') or [])
        spec['hereda'] = list(salida.get('hereda') or [])
        if frase == _FRASE_CATALOGO:
            catalogo = spec
            continue
        banco.append(spec)
    if catalogo:
        banco.insert(0, catalogo)

    def consultar_fn(frase, lectura=None):
        return consultar(
            frase,
            empresa,
            anio,
            10,
            campos=campos,
            relaciones=relaciones,
            columnas=columnas,
            pedir=_sin_modelo,
            dialecto=None,
            sondear=False,
            lectura=lectura,
        )

    cubierto = cubrir_territorio(campos, relaciones, columnas, anio, consultar_fn)
    ya = {item['pregunta'] for item in banco}
    for item in cubierto['preguntas']:
        clave = item['pregunta']
        if item.get('vinculo') != 'continuacion' and clave in ya:
            continue
        try:
            spec = _spec_de(item['pregunta'], item['salida'])
        except Exception:
            logger.exception('Examen: no se pudo calcular la cifra esperada')
            connections[alias].rollback()
            continue
        if not spec:
            continue
        spec['vinculo'] = item.get('vinculo') or 'sola'
        spec['pieza'] = item.get('pieza') or ''
        spec['lectura_previa'] = item.get('lectura_previa')
        spec['sustituye'] = list(item.get('sustituye') or [])
        spec['hereda'] = list(item.get('hereda') or [])
        banco.append(spec)
        ya.add(clave)
    for probe in cubierto['probes']:
        banco.append(probe)
    aviso = ''
    if cubierto['incompleta']:
        aviso = 'La revisión está incompleta. Falta ' + str(cubierto['falta'])
    return {
        'aviso': aviso,
        'banco': banco,
        'incompleta': cubierto['incompleta'],
        'falta': cubierto['falta'],
    }


def _cargar(empresa, ejercicio):
    clave = (int(empresa), int(ejercicio), _CACHE_REVISION)
    guardado = _CACHE.get(clave)
    if guardado is not None:
        return guardado
    try:
        paquete = _banco_mapeado(clave[0], clave[1])
    except Exception:
        logger.exception('Examen: no se pudieron preparar las preguntas')
        paquete = {
            'aviso': 'No he podido preparar las preguntas de los datos mapeados.',
            'banco': [],
            'incompleta': True,
            'falta': 'territorio',
        }
    if paquete.get('banco'):
        _CACHE[clave] = paquete
    return paquete


def listar(empresa, ejercicio):
    paquete = _cargar(empresa, ejercicio)
    banco = paquete.get('banco') or []
    preguntas = [spec for spec in banco if not spec.get('es_probe')]
    probes = [spec for spec in banco if spec.get('es_probe')]
    vista = empaquetar_revision(
        empresa,
        ejercicio,
        preguntas,
        probes,
        paquete.get('incompleta'),
        paquete.get('falta') or '',
        paquete.get('aviso') or '',
    )
    vista['preguntas'] = [
        {
            'indice': i,
            'pregunta': spec.get('pregunta') or '',
            'esperado': spec.get('esperado') or '',
            'vinculo': spec.get('vinculo') or '',
            'es_probe': bool(spec.get('es_probe')),
            'pieza': spec.get('pieza') or '',
        }
        for i, spec in enumerate(banco)
    ]
    vista['total'] = len(banco)
    vista['territorio'] = len(preguntas)
    return vista


def responder_una(empresa, ejercicio, indice):
    from datia.services.ai_service import IAService
    from datia.services.embedding_service import examen_sin_guardar

    paquete = _cargar(empresa, ejercicio)
    banco = paquete.get('banco') or []
    if indice < 0 or indice >= len(banco):
        raise IndexError('Esa pregunta no está en el examen.')
    spec = banco[indice]
    marca = examen_sin_guardar.set(True)
    try:
        try:
            respuesta = IAService().generate_answer(
                spec['pregunta'],
                int(empresa),
                int(ejercicio),
                training_enabled=False,
                lectura=spec.get('lectura_previa'),
            )
        except Exception:
            logger.exception('Examen: la pregunta no se pudo ejecutar')
            respuesta = {'text': 'No he podido obtener un resultado para esta pregunta.', 'answer': ''}
    finally:
        examen_sin_guardar.reset(marca)
    verdict = clasificar(spec, respuesta)
    return {
        'indice': indice,
        'total': len(banco),
        'pregunta': spec['pregunta'],
        'veredicto': verdict,
        'etiqueta': _ETIQUETAS[verdict],
        'esperado': spec.get('esperado') or '',
        'obtenido': _texto(_aplanar(respuesta))[:500],
    }
