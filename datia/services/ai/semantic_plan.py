"""Plan de una pregunta: métrica, corte y filtro. El SQL lo escribe este módulo."""
import json
import logging
import re
import unicodedata

logger = logging.getLogger('query_builder')

_MESES = (
    "CASE mes WHEN 1 THEN 'Enero' WHEN 2 THEN 'Febrero' WHEN 3 THEN 'Marzo' "
    "WHEN 4 THEN 'Abril' WHEN 5 THEN 'Mayo' WHEN 6 THEN 'Junio' "
    "WHEN 7 THEN 'Julio' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Septiembre' "
    "WHEN 10 THEN 'Octubre' WHEN 11 THEN 'Noviembre' WHEN 12 THEN 'Diciembre' "
    "ELSE CAST(mes AS varchar(2)) END"
)
_NOMBRE = "COALESCE(NULLIF(LTRIM(RTRIM({campo})), ''), {codigo})"

FUENTES = {
    'ventas_ejercicio': {
        'tabla': 'metrics_totales_empresa_ejercicio',
        'etiqueta': "'Ejercicio'",
    },
    'ventas_mes': {
        'tabla': 'metrics_totales_empresa_ejercicio_mes',
        'etiqueta': _MESES,
        'orden_fijo': 'mes',
    },
    'ventas_cliente': {
        'tabla': 'metrics_totales_empresa_ejercicio_cliente',
        'etiqueta': _NOMBRE.format(campo='nombre', codigo='cliente'),
    },
    'ventas_cliente_mes': {
        'tabla': 'metrics_totales_empresa_ejercicio_cliente_mes',
        'etiqueta': f"CONCAT({_NOMBRE.format(campo='nombre', codigo='cliente')}, ' ', {_MESES})",
        'orden_fijo': 'mes',
    },
    'ventas_articulo': {
        'tabla': 'metrics_totales_empresa_ejercicio_articulo',
        'etiqueta': _NOMBRE.format(campo='descripcion', codigo='articulo'),
    },
    'compras_ejercicio': {
        'tabla': 'metrics_totales_empresa_ejercicio_compra',
        'etiqueta': "'Compras'",
    },
    'compras_mes': {
        'tabla': 'metrics_totales_empresa_ejercicio_compra_mes',
        'etiqueta': _MESES,
        'orden_fijo': 'mes',
    },
    'compras_proveedor': {
        'tabla': 'metrics_totales_empresa_ejercicio_proveedor',
        'etiqueta': _NOMBRE.format(campo='nombre', codigo='proveedor'),
    },
    'kilos_venta': {'forma': 'kilos', 'tabla': 'datiadb_lineasalbarancliente', 'corte': 'total'},
    'kilos_compra': {'forma': 'kilos', 'tabla': 'datiadb_lineasalbaranproveedor', 'corte': 'total'},
    'kilos_articulo': {'forma': 'kilos', 'tabla': 'datiadb_lineasalbarancliente', 'corte': 'articulo'},
    'kilos_articulo_compra': {'forma': 'kilos', 'tabla': 'datiadb_lineasalbaranproveedor', 'corte': 'articulo'},
    'kilos_cliente': {'forma': 'kilos', 'tabla': 'datiadb_lineasalbarancliente', 'corte': 'cliente'},
    'stock_articulo': {'forma': 'stock', 'tabla': 'datia_acumulados_stocks'},
    'lineas_venta': {'forma': 'lineas', 'tabla': 'datiadb_lineasalbarancliente'},
    'lineas_compra': {'forma': 'lineas', 'tabla': 'datiadb_lineasalbaranproveedor'},
}

_KILOS = 'COALESCE(SUM(CASE WHEN L.precio <> 0 THEN L.importeneto / L.precio END), 0)'

METRICAS = {
    'importe': 'importe_neto_total',
    'coste': 'importe_coste_total',
    'margen': '(importe_neto_total - importe_coste_total)',
    'albaranes': 'albaranes_count',
    'conteo': 'COUNT(*)',
    'kilos': 'kilos',
    'stock': 'stock',
    'precio_medio': '(importe_neto_total / NULLIF(albaranes_count, 0))',
}

FILTROS = {
    'ninguno': '',
    'margen_negativo': 'importe_neto_total > 0 AND importe_coste_total > importe_neto_total',
    'con_movimiento': 'importe_neto_total <> 0',
}

_PROMPT = """Devuelve solo un JSON. No escribas SQL.
Claves:
fuente: ventas_ejercicio | ventas_mes | ventas_cliente | ventas_cliente_mes | ventas_articulo | compras_ejercicio | compras_mes | compras_proveedor | kilos_venta | kilos_compra | kilos_articulo | kilos_articulo_compra | kilos_cliente | stock_articulo | lineas_venta | lineas_compra
metrica: importe | coste | margen | albaranes | conteo | kilos | stock | precio_medio
orden: asc | desc
limite: entero de 1 a {limite}
filtro: ninguno | margen_negativo | con_movimiento
Si la pregunta no cabe en esas fuentes, devuelve {{}}.
Pregunta: {pregunta}
JSON:
"""


def _fold(text: str) -> str:
    raw = unicodedata.normalize('NFD', text or '')
    return ''.join(ch for ch in raw if unicodedata.category(ch) != 'Mn').lower()


class SemanticPlan:
    @staticmethod
    def dialecto_actual() -> str:
        try:
            from django.db import connections
            alias = 'analytics' if 'analytics' in connections.databases else 'default'
            vendor = connections[alias].vendor
        except Exception:
            return 'postgres'
        if vendor in ('microsoft', 'mssql'):
            return 'sqlserver'
        return 'postgres'

    @staticmethod
    def normalizar(data, limite_defecto=10):
        if not isinstance(data, dict):
            return None
        fuente = str(data.get('fuente') or '')
        metrica = str(data.get('metrica') or '')
        if fuente not in FUENTES or metrica not in METRICAS:
            return None
        orden = 'asc' if str(data.get('orden') or '').lower() == 'asc' else 'desc'
        filtro = str(data.get('filtro') or 'ninguno')
        if filtro not in FILTROS:
            filtro = 'ninguno'
        try:
            limite = int(data.get('limite') or limite_defecto)
        except (TypeError, ValueError):
            limite = int(limite_defecto or 10)
        if limite < 1:
            limite = 1
        if limite > 100:
            limite = 100
        texto = str(data.get('texto') or '').strip().lower()
        codigo = str(data.get('codigo') or '').strip()
        plan = {
            'fuente': fuente,
            'metrica': metrica,
            'orden': orden,
            'limite': limite,
            'filtro': filtro,
        }
        if re.fullmatch(r'[a-z0-9 ]{2,40}', texto):
            plan['texto'] = texto
        if re.fullmatch(r'[A-Za-z0-9._\-]{1,40}', codigo):
            plan['codigo'] = codigo
        return plan

    @staticmethod
    def leer_json(texto, limite_defecto=10):
        raw = texto or ''
        inicio = raw.find('{')
        fin = raw.rfind('}')
        if inicio < 0 or fin < inicio:
            return None
        try:
            data = json.loads(raw[inicio:fin + 1])
        except json.JSONDecodeError:
            return None
        return SemanticPlan.normalizar(data, limite_defecto)

    @staticmethod
    def desde_frase(question, limit=10):
        folded = _fold(question)
        if not folded:
            return None
        fisico = SemanticPlan._plan_fisico(folded, limit)
        if fisico:
            return fisico
        if re.search(r'\b(litros|litro)\b', folded):
            return None
        clientes = bool(re.search(r'\bclientes?\b', folded))
        articulos = bool(re.search(r'\b(articulos?|productos?)\b', folded))
        proveedores = bool(re.search(r'\bproveedores?\b', folded))
        if sum((clientes, articulos, proveedores)) > 1:
            return None
        ventas = bool(re.search(r'\bventas?\b', folded))
        compras = bool(re.search(r'\b(compras?|gastos?)\b', folded))
        if ventas and compras:
            return None
        mensual = bool(re.search(
            r'\b(mensual|por mes|mes a mes|enero|febrero|marzo|abril|mayo|junio|julio|agosto|'
            r'septiembre|setiembre|octubre|noviembre|diciembre)\b',
            folded,
        ))
        if proveedores or (compras and not clientes and not articulos):
            if proveedores:
                fuente = 'compras_proveedor'
            elif mensual:
                fuente = 'compras_mes'
            else:
                fuente = 'compras_ejercicio'
        elif articulos:
            fuente = 'ventas_articulo'
        elif clientes:
            fuente = 'ventas_cliente_mes' if mensual else 'ventas_cliente'
        elif mensual and (ventas or compras or 'margen' in folded):
            fuente = 'compras_mes' if compras else 'ventas_mes'
        elif ventas or compras or re.search(r'\b(margen|coste|costo|albaranes?|importe|precio|ticket)\b', folded):
            fuente = 'compras_ejercicio' if compras else 'ventas_ejercicio'
        else:
            return None
        if re.search(r'\b(medio|media|promedio|ticket)\b', folded):
            metrica = 'precio_medio'
        elif re.search(r'\b(cuantos|cuantas|numero de|cantidad de)\b', folded):
            metrica = 'conteo'
        elif 'margen' in folded:
            metrica = 'margen'
        elif re.search(r'\b(coste|costo)\b', folded):
            metrica = 'coste'
        elif re.search(r'\balbaranes?\b', folded) and 'importe' not in folded:
            metrica = 'albaranes'
        else:
            metrica = 'importe'
        orden = 'desc'
        if re.search(r'\b(peor|peores|menor|menores|menos)\b', folded) and not re.search(
            r'\b(mas|mayor|mayores|mejor|mejores|top)\b', folded,
        ):
            orden = 'asc'
        filtro = 'ninguno'
        if re.search(r'\b(margen negativo|por debajo del coste|en perdidas)\b', folded):
            filtro = 'margen_negativo'
        pedido = re.search(r'\b(?:top|primeros|primeras|mejores|peores)\s+(\d{1,3})\b', folded)
        tope = int(pedido.group(1)) if pedido else limit
        return SemanticPlan.normalizar({
            'fuente': fuente,
            'metrica': metrica,
            'orden': orden,
            'limite': tope,
            'filtro': filtro,
        }, limit)

    @staticmethod
    def _plan_fisico(folded, limit):
        stock = bool(re.search(r'\b(stock|existencias|existencia|inventario)\b', folded))
        kilos = bool(re.search(r'\b(kilos?|kg|kilogramos?)\b', folded))
        unidades = bool(re.search(r'\b(unidades|unidad)\b', folded)) and bool(re.search(
            r'\b(vendid|venta|ventas|albaran|compra|compras|comprad)\b', folded,
        ))
        lineas = bool(re.search(r'\b(lineas?|detalle)\b', folded)) and bool(re.search(r'\balbaran', folded))
        if not (stock or kilos or unidades or lineas):
            return None
        compras = bool(re.search(r'\b(compra|compras|comprad|proveedor|proveedores)\b', folded))
        clientes = bool(re.search(r'\b(cliente|clientes|a quien|al que)\b', folded))
        articulos = bool(re.search(r'\b(articulo|articulos|producto|productos)\b', folded))
        if stock:
            fuente, metrica = 'stock_articulo', 'stock'
        elif lineas and not (kilos or unidades):
            fuente, metrica = ('lineas_compra' if compras else 'lineas_venta'), 'importe'
        elif clientes and not compras:
            fuente, metrica = 'kilos_cliente', 'kilos'
        elif articulos or SemanticPlan._texto_seguro(folded):
            fuente, metrica = ('kilos_articulo_compra' if compras else 'kilos_articulo'), 'kilos'
        elif compras:
            fuente, metrica = 'kilos_compra', 'kilos'
        else:
            fuente, metrica = 'kilos_venta', 'kilos'
        orden = 'desc'
        if re.search(r'\b(peor|peores|menor|menores|menos)\b', folded) and not re.search(
            r'\b(mas|mayor|mayores|mejor|mejores|top)\b', folded,
        ):
            orden = 'asc'
        pedido = re.search(r'\b(?:top|primeros|primeras|mejores|peores)\s+(\d{1,3})\b', folded)
        datos = {
            'fuente': fuente,
            'metrica': metrica,
            'orden': orden,
            'limite': int(pedido.group(1)) if pedido else limit,
            'filtro': 'ninguno',
        }
        texto = SemanticPlan._texto_seguro(folded)
        codigo = SemanticPlan._codigo_seguro(folded)
        if texto and not codigo:
            datos['texto'] = texto
        if codigo:
            datos['codigo'] = codigo
        return SemanticPlan.normalizar(datos, limit)

    @staticmethod
    def _texto_seguro(folded):
        hallado = re.search(
            r'\b(?:kilos?|kg|kilogramos?|unidades|unidad|stock|existencias|existencia|inventario|lineas?|detalle)\b'
            r'(?:\s+\w+){0,4}\s+(?:de|del)\s+([a-z0-9 ]+)',
            folded or '',
        )
        if not hallado:
            return ''
        resto = re.split(
            r'\b(se|han|en|durante|del|ejercicio|ano|vendid\w*|compr\w*|albaran\w*|cliente\w*|proveedor\w*)\b',
            hallado.group(1),
        )[0]
        resto = re.sub(r'[^a-z0-9 ]', '', resto).strip()
        if resto in ('la', 'el', 'los', 'las', 'articulo', 'articulos', 'producto', 'productos'):
            return ''
        return resto if re.fullmatch(r'[a-z0-9 ]{2,40}', resto) else ''

    @staticmethod
    def _codigo_seguro(folded):
        hallado = re.search(r'\b(?:de|del|codigo)\s+([a-z0-9][a-z0-9._\-]{0,39})\b', folded or '')
        if not hallado or not re.search(r'\d', hallado.group(1)):
            return ''
        return hallado.group(1)

    @staticmethod
    def desde_modelo(question, limit=10):
        try:
            from datia.services.ollama_service import OllamaService
            prompt = _PROMPT.format(limite=int(limit or 10), pregunta=question or '')
            palabras = len((question or '').split())
            modelo = (
                'qwen2.5:3b-instruct-q4_k_m'
                if palabras <= 8
                else 'qwen2.5:14b-instruct-q4_k_m'
            )
            texto = OllamaService().generate_text(
                prompt,
                timeout=45,
                model=modelo,
                stream=False,
                options={'temperature': 0, 'num_predict': 180},
            )
        except Exception:
            logger.warning('SemanticPlan: el modelo local no contestó')
            return None
        return SemanticPlan.leer_json(texto, limit)

    @staticmethod
    def compilar(plan, empresa, ejercicio, dialecto='postgres'):
        normal = SemanticPlan.normalizar(plan, (plan or {}).get('limite') if isinstance(plan, dict) else 10)
        if not normal:
            return None
        try:
            emp = int(empresa)
            year = int(ejercicio)
        except (TypeError, ValueError):
            return None
        fuente = FUENTES[normal['fuente']]
        if fuente.get('forma') in ('kilos', 'stock', 'lineas'):
            return SemanticPlan._compilar_operativo(normal, fuente, emp, year, dialecto)
        metrica = METRICAS[normal['metrica']]
        filtro = FILTROS[normal['filtro']]
        where = f'empresa = {emp} AND ejercicio = {year}'
        if filtro:
            where = f'{where} AND {filtro}'
        if normal['metrica'] == 'conteo':
            select = f"SELECT 'Total' AS label, {metrica} AS val, 0 AS coste, 0 AS ops"
            orden = ''
        else:
            select = (
                f"SELECT {fuente['etiqueta']} AS label, {metrica} AS val, "
                f"importe_coste_total AS coste, albaranes_count AS ops"
            )
            columna = fuente.get('orden_fijo') or 'val'
            sentido = 'ASC' if normal['orden'] == 'asc' else 'DESC'
            orden = f' ORDER BY {columna} {sentido}'
        cabeza = ''
        cola = ''
        if dialecto == 'sqlserver':
            cabeza = f"TOP {normal['limite']} "
        else:
            cola = f' LIMIT {normal["limite"]}'
        sql = f"{select.replace('SELECT ', 'SELECT ' + cabeza, 1)} FROM {fuente['tabla']} WHERE {where}{orden}{cola}"
        return ' '.join(sql.split())

    @staticmethod
    def _cerrar(select, orden, limite, dialecto):
        if dialecto == 'sqlserver':
            select = select.replace('SELECT ', f'SELECT TOP {int(limite)} ', 1)
            sql = f'{select}{orden}'
        else:
            sql = f'{select}{orden} LIMIT {int(limite)}'
        return ' '.join(sql.split())

    @staticmethod
    def _compilar_operativo(plan, fuente, empresa, year, dialecto):
        forma = fuente.get('forma')
        sentido = 'ASC' if plan['orden'] == 'asc' else 'DESC'
        texto = str(plan.get('texto') or '')
        codigo = str(plan.get('codigo') or '')
        filtro_texto = ''
        if texto:
            filtro_texto = f" AND LOWER(A.descripcion) LIKE '%{texto}%'"
        if forma == 'stock':
            where = f'empresa = {empresa} AND ejercicio = {year}'
            where += (
                ' AND periodo = (SELECT MAX(periodo) FROM datia_acumulados_stocks '
                f'WHERE empresa = {empresa} AND ejercicio = {year} AND periodo BETWEEN 0 AND 12)'
            )
            if codigo:
                where += f" AND LOWER(articulo) = '{codigo.lower()}'"
            if texto:
                where += f" AND (LOWER(articulo_desc) LIKE '%{texto}%' OR LOWER(articulo) LIKE '%{texto}%')"
            select = (
                'SELECT COALESCE(NULLIF(LTRIM(RTRIM(MAX(articulo_desc))), \'\'), articulo) AS label, '
                'SUM(unidadsaldo) AS val, SUM(importesaldo) AS coste, MAX(periodo) AS ops '
                f'FROM datia_acumulados_stocks WHERE {where} GROUP BY articulo'
            )
            return SemanticPlan._cerrar(select, f' ORDER BY val {sentido}', plan['limite'], dialecto)
        if forma == 'lineas':
            select = (
                'SELECT COALESCE(NULLIF(LTRIM(RTRIM(A.descripcion)), \'\'), L.codigoarticulo) AS label, '
                'L.importeneto AS val, 0 AS coste, '
                'CASE WHEN L.precio <> 0 THEN L.importeneto / L.precio ELSE 0 END AS ops '
                f"FROM {fuente['tabla']} L "
                'LEFT JOIN datia_articulos A ON A.empresa = L.codigoempresa AND A.articulo = L.codigoarticulo '
                f'WHERE L.codigoempresa = {empresa} AND L.ejercicioalbaran = {year}{filtro_texto}'
            )
            return SemanticPlan._cerrar(select, f' ORDER BY val {sentido}', plan['limite'], dialecto)
        corte = fuente.get('corte')
        if corte == 'articulo':
            select = (
                'SELECT COALESCE(NULLIF(LTRIM(RTRIM(MAX(A.descripcion))), \'\'), L.codigoarticulo) AS label, '
                f'{_KILOS} AS val, 0 AS coste, COUNT(*) AS ops '
                f"FROM {fuente['tabla']} L "
                'LEFT JOIN datia_articulos A ON A.empresa = L.codigoempresa AND A.articulo = L.codigoarticulo '
                f'WHERE L.codigoempresa = {empresa} AND L.ejercicioalbaran = {year}{filtro_texto} '
                f'GROUP BY L.codigoarticulo HAVING {_KILOS} <> 0'
            )
            return SemanticPlan._cerrar(select, f' ORDER BY val {sentido}', plan['limite'], dialecto)
        if corte == 'cliente':
            select = (
                'SELECT COALESCE(NULLIF(LTRIM(RTRIM(MAX(C.razonsocial))), \'\'), C.codigocliente) AS label, '
                f'{_KILOS} AS val, 0 AS coste, COUNT(*) AS ops '
                f"FROM {fuente['tabla']} L "
                'JOIN datiadb_cabeceraalbarancliente C '
                'ON C.codigoempresa = L.codigoempresa AND C.ejercicioalbaran = L.ejercicioalbaran '
                'AND C.seriealbaran = L.seriealbaran AND C.numeroalbaran = L.numeroalbaran '
                f'WHERE L.codigoempresa = {empresa} AND L.ejercicioalbaran = {year} '
                f'GROUP BY C.codigocliente HAVING {_KILOS} <> 0'
            )
            return SemanticPlan._cerrar(select, f' ORDER BY val {sentido}', plan['limite'], dialecto)
        etiqueta = "'Kilos compra'" if 'proveedor' in fuente['tabla'] else "'Kilos'"
        select = (
            f"SELECT {etiqueta} AS label, {_KILOS} AS val, 0 AS coste, COUNT(*) AS ops "
            f"FROM {fuente['tabla']} L "
            f'WHERE L.codigoempresa = {empresa} AND L.ejercicioalbaran = {year}'
        )
        return SemanticPlan._cerrar(select, '', plan['limite'], dialecto)
