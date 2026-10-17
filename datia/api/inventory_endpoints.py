from ninja import Router
from django.http import JsonResponse
from django.db import connections
from datia.services.etl_service import ETLService
from datia.services.cache_service import compute_mssql_fingerprint

router = Router()

def table_exists(cursor, name):
    try:
        cursor.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?", (name,))
        return cursor.fetchone() is not None
    except:
        return False

def get_columns(cursor, table):
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (table,))
    return [r[0] for r in cursor.fetchall()]

def pick_column(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None

def resolve_stock_table(cursor):
    for name in ["AcumuladoStock", "AcumuladosStock", "AcumuladoStocks"]:
        if table_exists(cursor, name):
            return name
    return None

def build_mapping(cursor, table):
    cols = get_columns(cursor, table)
    m = {}
    m['empresa'] = pick_column(cols, ['CodigoEmpresa','Empresa','EmpresaCodigo'])
    m['ejercicio'] = pick_column(cols, ['Ejercicio','EjercicioStock','Year'])
    m['periodo'] = pick_column(cols, ['Periodo','Mes'])
    m['articulo'] = pick_column(cols, ['Articulo','CodigoArticulo','Codigo'])
    m['descripcion'] = pick_column(cols, ['Descripcion','NombreArticulo','Nombre'])
    m['tipologia'] = pick_column(cols, ['Tipologia','Tipo','Familia','Categoria'])
    m['almacen'] = pick_column(cols, ['Almacen','CodigoAlmacen'])
    m['ubicacion'] = pick_column(cols, ['Ubicacion','UbicacionAlmacen','Ubic'])
    m['unidad_saldo'] = pick_column(cols, ['UnidadSaldo','SaldoUnidades','CantidadSaldo','UnidadesSaldo'])
    m['cantidad'] = pick_column(cols, ['Cantidad','Unidades','Qty'])
    m['precio_compra'] = pick_column(cols, ['PrecioCompra','PCosto','CosteUnitario','PrecioCoste'])
    m['precio_medio'] = pick_column(cols, ['PrecioMedio','CosteMedio','PrecioPonderado'])
    m['precio_ultima'] = pick_column(cols, ['PrecioUltimaEntrada','UltimoPrecio','PrecioUltimo'])
    m['precio_venta'] = pick_column(cols, ['PrecioVenta','PVP','Tarifa','PrecioTarifa'])
    m['coste_estandar'] = pick_column(cols, ['CosteEstandar','PrecioEstandar','CosteStd','PrecioStd'])
    m['precio_lista'] = pick_column(cols, ['PrecioLista','PLista','PrecioTarifa','Tarifa'])
    m['precio_promocion'] = pick_column(cols, ['PrecioPromocion','PPromocion','PrecioOferta','Oferta'])
    m['coste_reposicion'] = pick_column(cols, ['CosteReposicion','Reposicion','PrecioCompraNuevo'])
    m['valor_mercado'] = pick_column(cols, ['ValorMercado','VMercado','PrecioActualizado'])
    m['importe_saldo'] = pick_column(cols, ['ImporteSaldo','SaldoImporte','Importe','SaldoValor','ValorSaldo'])
    m['fecha_caducidad'] = pick_column(cols, ['FechaCaducidad','Caducidad','FechaCad'])
    return m

def get_connection_and_mapping():
    service = ETLService()
    conn = service.get_connection()
    cursor = conn.cursor()
    table = resolve_stock_table(cursor)
    if not table:
        return conn, cursor, None, {}
    return conn, cursor, table, build_mapping(cursor, table)

def pg_has_stocks(empresa: int, ejercicio: int) -> bool:
    try:
        c = connections['analytics'].cursor()
        cols = pg_get_columns('datia_acumulados_stocks')
        if 'source_fp' in cols:
            fp = compute_mssql_fingerprint()
            c.execute("SELECT 1 FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s AND source_fp=%s LIMIT 1", [empresa, ejercicio, fp])
        else:
            c.execute("SELECT 1 FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s LIMIT 1", [empresa, ejercicio])
        return c.fetchone() is not None
    except:
        return False

def pg_filters(empresa: int, ejercicio: int):
    c = connections['analytics'].cursor()
    almacenes = []
    ubicaciones = []
    tipologias = []
    almacenes_named = []
    try:
        # Base lists
        cols = pg_get_columns('datia_acumulados_stocks')
        if 'source_fp' in cols:
            fp = compute_mssql_fingerprint()
            c.execute("SELECT DISTINCT almacen FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s AND source_fp=%s", [empresa, ejercicio, fp])
        else:
            c.execute("SELECT DISTINCT almacen FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s", [empresa, ejercicio])
        almacenes = [r[0] for r in c.fetchall() if r[0] is not None and r[0] != ""]
    except:
        almacenes = []
    try:
        cols = pg_get_columns('datia_acumulados_stocks')
        if 'source_fp' in cols:
            fp = compute_mssql_fingerprint()
            c.execute("SELECT DISTINCT ubicacion FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s AND source_fp=%s", [empresa, ejercicio, fp])
        else:
            c.execute("SELECT DISTINCT ubicacion FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s", [empresa, ejercicio])
        ubicaciones = [r[0] for r in c.fetchall() if r[0] is not None and r[0] != ""]
    except:
        ubicaciones = []
    try:
        cols = pg_get_columns('datia_acumulados_stocks')
        if 'source_fp' in cols:
            fp = compute_mssql_fingerprint()
            c.execute("SELECT DISTINCT tipologia FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s AND source_fp=%s", [empresa, ejercicio, fp])
        else:
            c.execute("SELECT DISTINCT tipologia FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s", [empresa, ejercicio])
        tipologias = [r[0] for r in c.fetchall() if r[0] is not None and r[0] != ""]
    except:
        tipologias = []
    # Named warehouses if column exists
    try:
        cols = pg_get_columns('datia_acumulados_stocks')
        if 'almacen_name' in cols:
            if 'source_fp' in cols:
                fp = compute_mssql_fingerprint()
                c.execute("SELECT DISTINCT almacen, almacen_name FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s AND source_fp=%s", [empresa, ejercicio, fp])
            else:
                c.execute("SELECT DISTINCT almacen, almacen_name FROM datia_acumulados_stocks WHERE empresa=%s AND ejercicio=%s", [empresa, ejercicio])
            almacenes_named = [{'code': r[0], 'name': (r[1] or r[0])} for r in c.fetchall() if r[0] is not None and r[0] != ""]
    except:
        almacenes_named = []
    return (almacenes, ubicaciones, tipologias, almacenes_named)

def pg_get_columns(table_name: str):
    try:
        c = connections['analytics'].cursor()
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", [table_name])
        return [r[0] for r in c.fetchall()]
    except:
        return []

def pg_pick_column(cols, candidates):
    for c in candidates:
        if c in cols:
            return c
    return None

def pg_unit_and_price(method: str):
    cols = pg_get_columns('datia_acumulados_stocks')
    unit_col = pg_pick_column(cols, ['unidadsaldo','saldounidades','cantidadesaldo','unidades'])
    if method == 'medio':
        price_col = pg_pick_column(cols, ['preciomedio','costemedio','precioponderado'])
    elif method == 'ultima':
        price_col = pg_pick_column(cols, ['precioultimaentrada','ultimoprecio','precioultimo'])
    elif method == 'compra':
        price_col = pg_pick_column(cols, ['preciocompra','pcosto','costeunitario','preciocoste'])
    else:
        price_col = None
    return unit_col, price_col

def pg_where_and_params(empresa: int, ejercicio: int, almacen: str = "", ubicacion: str = "", tipologia: str = "", extra: str = ""):
    where = "WHERE empresa=%s AND ejercicio=%s"
    params = [empresa, ejercicio]
    if almacen:
        where += " AND almacen=%s"
        params.append(almacen)
    if ubicacion:
        where += " AND ubicacion=%s"
        params.append(ubicacion)
    if tipologia:
        where += " AND tipologia=%s"
        params.append(tipologia)
    cols = pg_get_columns('datia_acumulados_stocks')
    if 'source_fp' in cols:
        fp = compute_mssql_fingerprint()
        where += " AND source_fp=%s"
        params.append(fp)
    if extra:
        where += f" {extra}"
    return where, params

def resolve_article_mapping(cursor):
    try:
        for tname in ["Articulo", "Articulos", "ARTICULO", "ARTICULOS"]:
            if table_exists(cursor, tname):
                cols = get_columns(cursor, tname)
                code = pick_column(cols, ['Articulo','CodigoArticulo','Codigo'])
                desc = pick_column(cols, ['DescripcionArticulo','DescricpionArticulo','Descripcion','Nombre'])
                empresa = pick_column(cols, ['CodigoEmpresa','Empresa'])
                price = pick_column(cols, ['PrecioCompra','PCosto','CosteUnitario','PrecioCoste'])
                if code and desc:
                    return {'table': tname, 'code': code, 'desc': desc, 'empresa': empresa, 'price': price}
    except:
        pass
    return None

def resolve_warehouse_mapping(cursor):
    try:
        for tname in ["Almacenes", "Almacen", "ALMACENES"]:
            if table_exists(cursor, tname):
                cols = get_columns(cursor, tname)
                code = pick_column(cols, ['CodigoAlmacen','Almacen','Codigo'])
                name = pick_column(cols, ['Almacen','Nombre','Descripcion'])
                empresa = pick_column(cols, ['CodigoEmpresa','Empresa'])
                if code and name:
                    return {'table': tname, 'code': code, 'name': name, 'empresa': empresa}
    except:
        pass
    return None

def parse_int(v, default=0):
    try:
        return int(v)
    except:
        return default

def valor_field(m, method):
    if method == 'medio':
        return m['precio_medio'] or m['precio_compra'] or m['precio_ultima']
    if method == 'ultima':
        return m['precio_ultima'] or m['precio_compra'] or m['precio_medio']
    if method == 'venta':
        return m['precio_venta'] or m['precio_medio'] or m['precio_compra'] or m['precio_ultima']
    if method == 'estandar':
        return m['coste_estandar'] or m['precio_compra'] or m['precio_medio'] or m['precio_ultima']
    if method == 'lista':
        return m['precio_lista'] or m['precio_venta'] or m['precio_medio'] or m['precio_compra'] or m['precio_ultima']
    if method == 'promocion':
        return m['precio_promocion'] or m['precio_lista'] or m['precio_venta'] or m['precio_medio'] or m['precio_compra'] or m['precio_ultima']
    if method == 'reposicion':
        return m['coste_reposicion'] or m['precio_compra'] or m['precio_medio'] or m['precio_ultima']
    if method == 'mercado':
        return m['valor_mercado'] or m['precio_lista'] or m['precio_venta'] or m['precio_medio'] or m['precio_compra'] or m['precio_ultima']
    return m['precio_compra'] or m['precio_medio'] or m['precio_ultima']

@router.get("/filters")
def get_filters(request, empresa: int, ejercicio: int):
    if pg_has_stocks(empresa, ejercicio):
        almacenes, ubicaciones, tipologias, almacenes_named = pg_filters(empresa, ejercicio)
        return JsonResponse({'status': 'ok', 'almacenes': almacenes, 'almacenes_named': almacenes_named, 'ubicaciones': ubicaciones, 'tipologias': tipologias})
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('empresa') or not m.get('ejercicio'):
        return JsonResponse({'status': 'error', 'message': 'Tabla de stock no encontrada'}, status=404)
    q = f"SELECT DISTINCT {m['almacen']} as almacen FROM {table} WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
    almacenes = []
    almacenes_named = []
    try:
        cursor.execute(q, (empresa, ejercicio))
        almacenes = [r[0] for r in cursor.fetchall() if r[0] is not None]
    except:
        almacenes = []
    # Try named warehouses via join
    try:
        wmap = resolve_warehouse_mapping(cursor)
        if wmap:
            cursor.execute(f"SELECT DISTINCT S.{m['almacen']} as code, W.{wmap['name']} as name FROM {table} S LEFT JOIN {wmap['table']} W ON W.{wmap['code']} = S.{m['almacen']}" + (f" AND W.{wmap['empresa']} = S.{m['empresa']}" if wmap.get('empresa') and m.get('empresa') else "") + f" WHERE S.{m['empresa']}=? AND S.{m['ejercicio']}=?", (empresa, ejercicio))
            almacenes_named = [{'code': r[0], 'name': (r[1] or r[0])} for r in cursor.fetchall() if r[0] is not None]
    except:
        almacenes_named = []
    ubicaciones = []
    if m.get('ubicacion'):
        try:
            cursor.execute(f"SELECT DISTINCT {m['ubicacion']} as ubicacion FROM {table} WHERE {m['empresa']}=? AND {m['ejercicio']}=?", (empresa, ejercicio))
            ubicaciones = [r[0] for r in cursor.fetchall() if r[0] is not None]
        except:
            ubicaciones = []
    tipologias = []
    if m.get('tipologia'):
        try:
            cursor.execute(f"SELECT DISTINCT {m['tipologia']} as tipologia FROM {table} WHERE {m['empresa']}=? AND {m['ejercicio']}=?", (empresa, ejercicio))
            tipologias = [r[0] for r in cursor.fetchall() if r[0] is not None]
        except:
            tipologias = []
    conn.close()
    return JsonResponse({'status': 'ok', 'almacenes': almacenes, 'almacenes_named': almacenes_named, 'ubicaciones': ubicaciones, 'tipologias': tipologias})

@router.get("/snapshot")
def snapshot(request, empresa: int, ejercicio: int, valoracion: str = 'compra', periodo: int = 0, critical_threshold: int = 5, days_to_expire: int = 30, almacen: str = "", ubicacion: str = "", tipologia: str = ""):
    if pg_has_stocks(empresa, ejercicio):
        try:
            c = connections['analytics'].cursor()
            unit_col, price_col = pg_unit_and_price(valoracion)
            if periodo and periodo not in [0, 99]:
                where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia, extra="AND periodo=%s")
                if unit_col and price_col:
                    c.execute(f"SELECT SUM(({unit_col})*({price_col})) FROM datia_acumulados_stocks {where}", params + [periodo])
                else:
                    c.execute(f"SELECT SUM(importesaldo) FROM datia_acumulados_stocks {where}", params + [periodo])
            else:
                where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia, extra="AND (periodo=0 OR periodo BETWEEN %s AND %s)")
                params.extend([1, 12])
                if unit_col and price_col:
                    c.execute(f"SELECT SUM(({unit_col})*({price_col})) FROM datia_acumulados_stocks {where}", params)
                else:
                    c.execute(f"SELECT SUM(importesaldo) FROM datia_acumulados_stocks {where}", params)
            total_valor = float(c.fetchone()[0] or 0)
            return JsonResponse({'status': 'ok', 'total_unidades': 0, 'total_valor': round(total_valor, 2), 'expiring': 0, 'critical': 0})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('empresa') or not m.get('ejercicio'):
        return JsonResponse({'status': 'error', 'message': 'Tabla de stock no encontrada'}, status=404)
    pcol = m.get('periodo')
    where = f"WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
    params = [empresa, ejercicio]
    if pcol:
        if periodo and periodo not in [0, 99]:
            where += f" AND {pcol}=?"
            params.append(periodo)
        else:
            where += f" AND ({pcol}=0 OR {pcol} BETWEEN 1 AND 12)"
    if m.get('almacen') and almacen:
        where += f" AND {m['almacen']}=?"
        params.append(almacen)
    if m.get('ubicacion') and ubicacion:
        where += f" AND {m['ubicacion']}=?"
        params.append(ubicacion)
    if m.get('tipologia') and tipologia:
        where += f" AND {m['tipologia']}=?"
        params.append(tipologia)
    ucol = m.get('unidad_saldo') or m.get('cantidad')
    total_unidades = 0
    total_valor = 0.0
    expiring = 0
    critical = 0
    try:
        if ucol:
            cursor.execute(f"SELECT SUM({ucol}) FROM {table} {where}", tuple(params))
            total_unidades = int(cursor.fetchone()[0] or 0)
            cursor.execute(f"SELECT {ucol} FROM {table} {where}", tuple(params))
            units_rows = [r[0] for r in cursor.fetchall()]
            critical = sum(1 for u in units_rows if int(u or 0) <= critical_threshold)
        price_expr = None
        if valoracion == 'medio' and m.get('precio_medio'):
            price_expr = f"S.{m['precio_medio']}"
        elif valoracion == 'ultima' and m.get('precio_ultima'):
            price_expr = f"S.{m['precio_ultima']}"
        elif valoracion == 'compra':
            amap = resolve_article_mapping(cursor)
            if amap and amap.get('price') and m.get('articulo'):
                join = f" LEFT JOIN {amap['table']} A ON A.{amap['code']} = S.{m['articulo']}"
                if amap.get('empresa') and m.get('empresa'):
                    join += f" AND A.{amap['empresa']} = S.{m['empresa']}"
                cursor.execute(f"SELECT SUM(CAST(S.{ucol} AS FLOAT) * CAST(A.{amap['price']} AS FLOAT)) FROM {table} S{join} {where}", tuple(params))
                total_valor = float(cursor.fetchone()[0] or 0)
            else:
                if m.get('precio_compra'):
                    price_expr = f"S.{m['precio_compra']}"
        if price_expr and ucol:
            cursor.execute(f"SELECT SUM(CAST(S.{ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) FROM {table} S {where}", tuple(params))
            total_valor = float(cursor.fetchone()[0] or 0)
        if m.get('fecha_caducidad'):
            cursor.execute(f"SELECT {m['fecha_caducidad']} FROM {table} {where}", tuple(params))
            cad_rows = cursor.fetchall()
            from datetime import datetime, timedelta
            now = datetime.now()
            for (cad,) in cad_rows:
                try:
                    v = cad.date() if hasattr(cad, 'date') else cad
                    if v and v <= (now + timedelta(days=days_to_expire)).date():
                        expiring += 1
                except:
                    pass
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn.close()
    return JsonResponse({'status': 'ok', 'total_unidades': total_unidades, 'total_valor': round(total_valor, 2), 'expiring': expiring, 'critical': critical})

@router.get("/distribution")
def distribution(request, empresa: int, ejercicio: int, by: str = 'tipologia', periodo: int = 0, metric: str = 'unidades', valoracion: str = 'compra', almacen: str = "", ubicacion: str = "", tipologia: str = ""):
    if pg_has_stocks(empresa, ejercicio):
        try:
            col = by if by in ['tipologia', 'almacen', 'ubicacion'] else None
            if not col:
                return JsonResponse({'status': 'error', 'message': 'Campo de agrupación no disponible'}, status=404)
            where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia)
            if periodo and periodo not in [0, 99]:
                where += " AND periodo=%s"
                params.append(periodo)
            else:
                where += " AND (periodo=0 OR periodo BETWEEN %s AND %s)"
                params.extend([1, 12])
            c = connections['analytics'].cursor()
            if metric == 'valor':
                unit_col, price_col = pg_unit_and_price(valoracion)
                if unit_col and price_col:
                    c.execute(f"SELECT {col} as k, SUM(({unit_col})*({price_col})) as v FROM datia_acumulados_stocks {where} GROUP BY {col}", params)
                    data = [{'label': r[0] or 'N/D', 'value': float(r[1] or 0)} for r in c.fetchall()]
                else:
                    c.execute(f"SELECT {col} as k, SUM(importesaldo) as v FROM datia_acumulados_stocks {where} GROUP BY {col}", params)
                    data = [{'label': r[0] or 'N/D', 'value': float(r[1] or 0)} for r in c.fetchall()]
            else:
                data = []
            return JsonResponse({'status': 'ok', 'items': data})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    key = m.get(by)
    if not table or not key:
        return JsonResponse({'status': 'error', 'message': 'Campo de agrupación no disponible'}, status=404)
    ucol = m.get('unidad_saldo') or m.get('cantidad')
    sval = m.get('importe_saldo')
    pcol = m.get('periodo')
    where = f"WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
    params = [empresa, ejercicio]
    if pcol:
        if periodo and periodo not in [0, 99]:
            where += f" AND {pcol}=?"
            params.append(periodo)
        else:
            where += f" AND ({pcol}=0 OR {pcol} BETWEEN ? AND ?)"
            params.extend([1, 12])
    if m.get('almacen') and almacen:
        where += f" AND {m['almacen']}=?"
        params.append(almacen)
    if m.get('ubicacion') and ubicacion:
        where += f" AND {m['ubicacion']}=?"
        params.append(ubicacion)
    if m.get('tipologia') and tipologia:
        where += f" AND {m['tipologia']}=?"
        params.append(tipologia)
    try:
        if metric == 'valor' and sval:
            cursor.execute(f"SELECT {key} as k, SUM({sval}) as v FROM {table} {where} GROUP BY {key}")
            data = [{'label': r[0] or 'N/D', 'value': float(r[1] or 0)} for r in cursor.fetchall()]
        else:
            if ucol:
                cursor.execute(f"SELECT {key} as k, SUM({ucol}) as u FROM {table} {where} GROUP BY {key}")
                data = [{'label': r[0] or 'N/D', 'value': int(r[1] or 0)} for r in cursor.fetchall()]
            else:
                data = []
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn.close()
    return JsonResponse({'status': 'ok', 'items': data})

@router.get("/evolution")
def evolution(request, empresa: int, ejercicio: int, metric: str = 'valor', valoracion: str = 'compra', almacen: str = "", ubicacion: str = "", tipologia: str = ""):
    if pg_has_stocks(empresa, ejercicio):
        try:
            where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia, extra="AND periodo BETWEEN %s AND %s")
            params.extend([1, 12])
            c = connections['analytics'].cursor()
            c.execute(f"SELECT periodo as p, SUM(importesaldo) as v FROM datia_acumulados_stocks {where} GROUP BY periodo ORDER BY periodo", params)
            serie = [{'periodo': int(r[0] or 0), 'valor': float(r[1] or 0)} for r in c.fetchall()]
            return JsonResponse({'status': 'ok', 'serie': serie})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('periodo'):
        return JsonResponse({'status': 'error', 'message': 'Campo periodo no disponible'}, status=404)
    ucol = m.get('unidad_saldo') or m.get('cantidad')
    sval = m.get('importe_saldo')
    try:
        where_base = f"WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
        params_base = [empresa, ejercicio]
        if m.get('almacen') and almacen:
            where_base += f" AND {m['almacen']}=?"
            params_base.append(almacen)
        if m.get('ubicacion') and ubicacion:
            where_base += f" AND {m['ubicacion']}=?"
            params_base.append(ubicacion)
        if m.get('tipologia') and tipologia:
            where_base += f" AND {m['tipologia']}=?"
            params_base.append(tipologia)
        if sval:
            cursor.execute(f"SELECT {m['periodo']} as p, SUM({sval}) as v FROM {table} {where_base} AND {m['periodo']} BETWEEN 1 AND 12 GROUP BY {m['periodo']} ORDER BY {m['periodo']}", tuple(params_base))
            serie = [{'periodo': int(r[0] or 0), 'valor': float(r[1] or 0)} for r in cursor.fetchall()]
        else:
            if ucol:
                cursor.execute(f"SELECT {m['periodo']} as p, SUM({ucol}) as u FROM {table} {where_base} AND {m['periodo']} BETWEEN 1 AND 12 GROUP BY {m['periodo']} ORDER BY {m['periodo']}", tuple(params_base))
                serie = [{'periodo': int(r[0] or 0), 'unidades': int(r[1] or 0)} for r in cursor.fetchall()]
            else:
                serie = []
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn.close()
    return JsonResponse({'status': 'ok', 'serie': serie})

@router.get("/variation")
def variation(request, empresa: int, ejercicio: int, almacen: str = "", ubicacion: str = "", tipologia: str = ""):
    if pg_has_stocks(empresa, ejercicio):
        try:
            where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia)
            c = connections['analytics'].cursor()
            c.execute(f"SELECT SUM(importesaldo) FROM datia_acumulados_stocks {where} AND periodo=%s", params + [0])
            valor_inicial = float(c.fetchone()[0] or 0)
            c.execute(f"SELECT periodo as p, SUM(importesaldo) as s FROM datia_acumulados_stocks {where} AND periodo BETWEEN %s AND %s GROUP BY periodo ORDER BY periodo", params + [1, 12])
            rows = c.fetchall()
            saldo_by_month = {int(r[0] or 0): float(r[1] or 0) for r in rows}
            serie = [{'periodo': 0, 'variacion': round(valor_inicial, 2)}]
            acumulado = 0.0
            for mth in range(1, 13):
                acumulado += saldo_by_month.get(mth, 0.0)
                serie.append({'periodo': mth, 'variacion': round(valor_inicial + acumulado, 2)})
            variacion_total = sum(saldo_by_month.values())
            existencia_fin = valor_inicial + variacion_total
            return JsonResponse({
                'status': 'ok',
                'valor_inicial': round(valor_inicial, 2),
                'variacion_total': round(variacion_total, 2),
                'existencia_fin': round(existencia_fin, 2),
                'serie': serie
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('periodo') or not m.get('importe_saldo'):
        return JsonResponse({'status': 'error', 'message': 'Campos requeridos no disponibles'}, status=404)
    try:
        where_base = f"WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
        params_base = [empresa, ejercicio]
        if m.get('almacen') and almacen:
            where_base += f" AND {m['almacen']}=?"
            params_base.append(almacen)
        if m.get('ubicacion') and ubicacion:
            where_base += f" AND {m['ubicacion']}=?"
            params_base.append(ubicacion)
        if m.get('tipologia') and tipologia:
            where_base += f" AND {m['tipologia']}=?"
            params_base.append(tipologia)
        cursor.execute(
            f"SELECT SUM({m['importe_saldo']}) FROM {table} {where_base} AND {m['periodo']}=0",
            tuple(params_base)
        )
        valor_inicial = float(cursor.fetchone()[0] or 0)
        cursor.execute(
            f"SELECT {m['periodo']} as p, SUM({m['importe_saldo']}) as s FROM {table} {where_base} AND {m['periodo']} BETWEEN 1 AND 12 GROUP BY {m['periodo']} ORDER BY {m['periodo']}",
            tuple(params_base)
        )
        rows = cursor.fetchall()
        saldo_by_month = {int(r[0] or 0): float(r[1] or 0) for r in rows}
        serie = [{'periodo': 0, 'variacion': round(valor_inicial, 2)}]
        acumulado = 0.0
        for mth in range(1, 13):
            acumulado += saldo_by_month.get(mth, 0.0)
            serie.append({'periodo': mth, 'variacion': round(valor_inicial + acumulado, 2)})
        variacion_total = sum(saldo_by_month.values())
        existencia_fin = valor_inicial + variacion_total
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn.close()
    return JsonResponse({
        'status': 'ok',
        'valor_inicial': round(valor_inicial, 2),
        'variacion_total': round(variacion_total, 2),
        'existencia_fin': round(existencia_fin, 2),
        'serie': serie
    })

@router.get("/period_saldo")
def period_saldo(request, empresa: int, ejercicio: int, almacen: str = "", ubicacion: str = "", tipologia: str = ""):
    if pg_has_stocks(empresa, ejercicio):
        try:
            where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia)
            c = connections['analytics'].cursor()
            c.execute(f"SELECT periodo as p, SUM(importesaldo) as s FROM datia_acumulados_stocks {where} AND (periodo=%s OR periodo BETWEEN %s AND %s) GROUP BY periodo ORDER BY periodo", params + [0, 1, 12])
            rows = c.fetchall()
            items = [{'periodo': int(r[0] or 0), 'importesaldo': float(r[1] or 0)} for r in rows]
            return JsonResponse({'status': 'ok', 'items': items})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('periodo') or not m.get('importe_saldo'):
        return JsonResponse({'status': 'error', 'message': 'Campos requeridos no disponibles'}, status=404)
    try:
        where_base = f"WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
        params_base = [empresa, ejercicio]
        if m.get('almacen') and almacen:
            where_base += f" AND {m['almacen']}=?"
            params_base.append(almacen)
        if m.get('ubicacion') and ubicacion:
            where_base += f" AND {m['ubicacion']}=?"
            params_base.append(ubicacion)
        if m.get('tipologia') and tipologia:
            where_base += f" AND {m['tipologia']}=?"
            params_base.append(tipologia)
        cursor.execute(
            f"SELECT {m['periodo']} as p, SUM({m['importe_saldo']}) as s FROM {table} {where_base} AND ({m['periodo']}=0 OR ({m['periodo']} BETWEEN 1 AND 12)) GROUP BY {m['periodo']} ORDER BY {m['periodo']}",
            tuple(params_base)
        )
        rows = cursor.fetchall()
        items = [{'periodo': int(r[0] or 0), 'importesaldo': float(r[1] or 0)} for r in rows]
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn.close()
    return JsonResponse({'status': 'ok', 'items': items})

@router.get("/by_warehouse")
def by_warehouse(request, empresa: int, ejercicio: int, periodo: int = 0, metric: str = 'unidades', valoracion: str = 'compra', almacen: str = "", ubicacion: str = "", tipologia: str = ""):
    if pg_has_stocks(empresa, ejercicio):
        try:
            where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia)
            cols = pg_get_columns('datia_acumulados_stocks')
            has_name = 'almacen_name' in cols
            if periodo and periodo not in [0, 99]:
                where += " AND periodo=%s"
                params.append(periodo)
            else:
                where += " AND (periodo=0 OR periodo BETWEEN %s AND %s)"
                params.extend([1, 12])
            c = connections['analytics'].cursor()
            group = "almacen" + (", almacen_name" if has_name else "")
            if metric == 'valor':
                unit_col, price_col = pg_unit_and_price(valoracion)
                if unit_col and price_col:
                    select = (
                        f"SELECT almacen{', almacen_name' if has_name else ''}, "
                        f"CASE WHEN SUM(({unit_col})*({price_col})) > 0 "
                        f"THEN SUM(({unit_col})*({price_col})) "
                        f"ELSE SUM(importesaldo) END AS v "
                        f"FROM datia_acumulados_stocks {where} "
                        f"GROUP BY {group} "
                        f"HAVING (CASE WHEN SUM(({unit_col})*({price_col})) > 0 THEN SUM(({unit_col})*({price_col})) ELSE SUM(importesaldo) END) > 0"
                    )
                    c.execute(select, params)
                    rows = c.fetchall()
                    data = []
                    for r in rows:
                        if has_name:
                            data.append({'almacen': r[0], 'almacen_name': r[1], 'valor': float(r[2] or 0)})
                        else:
                            data.append({'almacen': r[0], 'valor': float(r[1] or 0)})
                else:
                    select = f"SELECT almacen{', almacen_name' if has_name else ''}, SUM(importesaldo) FROM datia_acumulados_stocks {where} GROUP BY {group} HAVING SUM(importesaldo) > 0"
                    c.execute(select, params)
                    rows = c.fetchall()
                    data = []
                    for r in rows:
                        if has_name:
                            data.append({'almacen': r[0], 'almacen_name': r[1], 'valor': float(r[2] or 0)})
                        else:
                            data.append({'almacen': r[0], 'valor': float(r[1] or 0)})
            else:
                data = []
            return JsonResponse({'status': 'ok', 'items': data})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('almacen'):
        return JsonResponse({'status': 'error', 'message': 'Campos de almacén no disponibles'}, status=404)
    ucol = m.get('unidad_saldo') or m.get('cantidad')
    pcol = m.get('periodo')
    where = f"WHERE S.{m['empresa']}=? AND S.{m['ejercicio']}=?"
    params = [empresa, ejercicio]
    if pcol:
        if periodo and periodo not in [0, 99]:
            where += f" AND S.{pcol}=?"
            params.append(periodo)
        else:
            where += f" AND (S.{pcol}=0 OR S.{pcol} BETWEEN ? AND ?)"
            params.extend([1, 12])
    if m.get('almacen') and almacen:
        where += f" AND S.{m['almacen']}=?"
        params.append(almacen)
    if m.get('ubicacion') and ubicacion:
        where += f" AND S.{m['ubicacion']}=?"
        params.append(ubicacion)
    if m.get('tipologia') and tipologia:
        where += f" AND S.{m['tipologia']}=?"
        params.append(tipologia)
    wmap = resolve_warehouse_mapping(cursor)
    try:
        if wmap:
            join = f"LEFT JOIN {wmap['table']} W ON W.{wmap['code']} = S.{m['almacen']}"
            if wmap.get('empresa') and m.get('empresa'):
                join += f" AND W.{wmap['empresa']} = S.{m['empresa']}"
            if metric == 'valor' and ucol:
                price_expr = None
                if valoracion == 'medio' and m.get('precio_medio'):
                    price_expr = f"S.{m['precio_medio']}"
                elif valoracion == 'ultima' and m.get('precio_ultima'):
                    price_expr = f"S.{m['precio_ultima']}"
                elif valoracion == 'compra':
                    amap = resolve_article_mapping(cursor)
                    if amap and amap.get('price') and m.get('articulo'):
                        join += f" LEFT JOIN {amap['table']} A ON A.{amap['code']} = S.{m['articulo']}"
                        if amap.get('empresa') and m.get('empresa'):
                            join += f" AND A.{amap['empresa']} = S.{m['empresa']}"
                        cursor.execute(
                            f"SELECT W.{wmap['name']} as wn, "
                            f"CASE WHEN SUM(CAST(S.{ucol} AS FLOAT) * CAST(A.{amap['price']} AS FLOAT)) > 0 "
                            f"THEN SUM(CAST(S.{ucol} AS FLOAT) * CAST(A.{amap['price']} AS FLOAT)) "
                            f"ELSE SUM(CAST(S.{m.get('importe_saldo') or '0'} AS FLOAT)) END AS v "
                            f"FROM {table} S {join} {where} "
                            f"GROUP BY W.{wmap['name']} "
                            f"HAVING (CASE WHEN SUM(CAST(S.{ucol} AS FLOAT) * CAST(A.{amap['price']} AS FLOAT)) > 0 "
                            f"THEN SUM(CAST(S.{ucol} AS FLOAT) * CAST(A.{amap['price']} AS FLOAT)) "
                            f"ELSE SUM(CAST(S.{m.get('importe_saldo') or '0'} AS FLOAT)) END) > 0"
                        )
                        data = [{'almacen': None, 'almacen_name': r[0], 'valor': float(r[1] or 0)} for r in cursor.fetchall()]
                    else:
                        price_expr = m.get('precio_compra') and f"S.{m['precio_compra']}" or None
                if price_expr:
                    cursor.execute(
                        f"SELECT W.{wmap['name']} as wn, "
                        f"CASE WHEN SUM(CAST(S.{ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) > 0 "
                        f"THEN SUM(CAST(S.{ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) "
                        f"ELSE SUM(CAST(S.{m.get('importe_saldo') or '0'} AS FLOAT)) END AS v "
                        f"FROM {table} S {join} {where} "
                        f"GROUP BY W.{wmap['name']} "
                        f"HAVING (CASE WHEN SUM(CAST(S.{ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) > 0 "
                        f"THEN SUM(CAST(S.{ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) "
                        f"ELSE SUM(CAST(S.{m.get('importe_saldo') or '0'} AS FLOAT)) END) > 0"
                    )
                    data = [{'almacen': None, 'almacen_name': r[0], 'valor': float(r[1] or 0)} for r in cursor.fetchall()]
            else:
                cursor.execute(f"SELECT W.{wmap['name']} as wn, SUM(S.{ucol}) as u FROM {table} S {join} {where} GROUP BY W.{wmap['name']}")
                data = [{'almacen': None, 'almacen_name': r[0], 'unidades': int(r[1] or 0)} for r in cursor.fetchall()]
        else:
            group = m['almacen']
            if metric == 'valor' and ucol:
                price_expr = None
                if valoracion == 'medio' and m.get('precio_medio'):
                    price_expr = m['precio_medio']
                elif valoracion == 'ultima' and m.get('precio_ultima'):
                    price_expr = m['precio_ultima']
                elif valoracion == 'compra' and m.get('precio_compra'):
                    price_expr = m['precio_compra']
                if price_expr:
                    cursor.execute(f"SELECT {group}, SUM(CAST({ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) FROM {table} {where} GROUP BY {group} HAVING SUM(CAST({ucol} AS FLOAT) * CAST({price_expr} AS FLOAT)) > 0")
                    data = [{'almacen': r[0], 'valor': float(r[1] or 0)} for r in cursor.fetchall()]
                else:
                    cursor.execute(f"SELECT {group}, SUM({ucol}) FROM {table} {where} GROUP BY {group}")
                    data = [{'almacen': r[0], 'unidades': int(r[1] or 0)} for r in cursor.fetchall()]
            else:
                cursor.execute(f"SELECT {group}, SUM({ucol}) FROM {table} {where} GROUP BY {group}")
                data = [{'almacen': r[0], 'unidades': int(r[1] or 0)} for r in cursor.fetchall()]
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn.close()
    return JsonResponse({'status': 'ok', 'items': data})

@router.get("/master")
def master(request, empresa: int, ejercicio: int, periodo: int = 0, almacen: str = "", ubicacion: str = "", tipologia: str = "", limit: int = 200, offset: int = 0, valoracion: str = 'compra'):
    if pg_has_stocks(empresa, ejercicio):
        try:
            c = connections['analytics'].cursor()
            cols = pg_get_columns('datia_acumulados_stocks')
            has_art = 'articulo' in cols
            has_desc = 'articulo_desc' in cols
            has_tip = 'tipologia' in cols
            has_al = 'almacen' in cols
            has_ub = 'ubicacion' in cols
            has_unit = 'unidadsaldo' in cols
            where, params = pg_where_and_params(empresa, ejercicio, almacen, ubicacion, tipologia)
            if periodo and periodo not in [0, 99]:
                where += " AND periodo=%s"
                params.append(periodo)
            else:
                where += " AND (periodo=0 OR periodo BETWEEN %s AND %s)"
                params.extend([1, 12])
            dims = []
            if has_art:
                dims.append('articulo')
            if has_desc:
                dims.append('articulo_desc')
            if has_tip:
                dims.append('tipologia')
            if has_al:
                dims.append('almacen')
            if has_ub:
                dims.append('ubicacion')
            select_parts = []
            for d in dims:
                select_parts.append(d)
            if has_unit:
                select_parts.append("SUM(unidadsaldo) as unidades")
            else:
                select_parts.append("0 as unidades")
            select = ", ".join(select_parts) if select_parts else "0 as unidades"
            group_by = ", ".join(dims) if dims else ""
            sql = f"SELECT {select} FROM datia_acumulados_stocks {where}"
            if group_by:
                sql += f" GROUP BY {group_by}"
            order_key = dims[0] if dims else "periodo"
            sql += " ORDER BY " + order_key + " LIMIT %s OFFSET %s"
            c.execute(sql, params + [limit, offset])
            rows = c.fetchall()
            items = []
            for r in rows:
                idx = 0
                d = {}
                if has_art:
                    d['articulo'] = r[idx]; idx += 1
                if has_desc:
                    d['descripcion'] = r[idx]; idx += 1
                if has_tip:
                    d['tipologia'] = r[idx]; idx += 1
                if has_al:
                    d['almacen'] = r[idx]; idx += 1
                if has_ub:
                    d['ubicacion'] = r[idx]; idx += 1
                d['unidades'] = int(r[idx] or 0); idx += 1
                items.append(d)
            return JsonResponse({'status': 'ok', 'items': items})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    conn, cursor, table, m = get_connection_and_mapping()
    if not table:
        return JsonResponse({'status': 'error', 'message': 'Tabla de stock no encontrada'}, status=404)
    ucol = m.get('unidad_saldo') or m.get('cantidad')
    vfield = valor_field(m, valoracion)
    amap = resolve_article_mapping(cursor)
    wmap = resolve_warehouse_mapping(cursor)
    select_parts = []
    index_keys = []
    if m.get('articulo'):
        select_parts.append(f"S.{m['articulo']} as articulo")
        index_keys.append('articulo')
    if amap:
        select_parts.append(f"A.{amap['desc']} as articulo_desc")
        index_keys.append('articulo_desc')
    elif m.get('descripcion'):
        select_parts.append(f"S.{m['descripcion']} as articulo_desc")
        index_keys.append('articulo_desc')
    if m.get('tipologia'):
        select_parts.append(f"S.{m['tipologia']} as tipologia")
        index_keys.append('tipologia')
    if m.get('almacen'):
        select_parts.append(f"S.{m['almacen']} as almacen_code")
        index_keys.append('almacen_code')
    if wmap:
        select_parts.append(f"W.{wmap['name']} as almacen_name")
        index_keys.append('almacen_name')
    if m.get('ubicacion'):
        select_parts.append(f"S.{m['ubicacion']} as ubicacion")
        index_keys.append('ubicacion')
    if ucol:
        select_parts.append(f"S.{ucol} as unidades")
        index_keys.append('unidades')
    else:
        select_parts.append(f"0 as unidades")
        index_keys.append('unidades')
    select = ", ".join(select_parts)
    where = f"WHERE S.{m['empresa']}=? AND S.{m['ejercicio']}=?"
    params = [empresa, ejercicio]
    if m.get('periodo'):
        if periodo and periodo not in [0, 99]:
            where += f" AND S.{m['periodo']}=?"
            params.append(periodo)
        else:
            where += f" AND (S.{m['periodo']}=0 OR S.{m['periodo']} BETWEEN ? AND ?)"
            params.extend([1, 12])
    if m.get('almacen') and almacen:
        where += f" AND S.{m['almacen']}=?"
        params.append(almacen)
    if m.get('ubicacion') and ubicacion:
        where += f" AND S.{m['ubicacion']}=?"
        params.append(ubicacion)
    if m.get('tipologia') and tipologia:
        where += f" AND S.{m['tipologia']}=?"
        params.append(tipologia)
    joins = ""
    if amap and m.get('articulo'):
        joins += f" LEFT JOIN {amap['table']} A ON A.{amap['code']} = S.{m['articulo']}"
        if amap.get('empresa') and m.get('empresa'):
            joins += f" AND A.{amap['empresa']} = S.{m['empresa']}"
    if wmap and m.get('almacen'):
        joins += f" LEFT JOIN {wmap['table']} W ON W.{wmap['code']} = S.{m['almacen']}"
        if wmap.get('empresa') and m.get('empresa'):
            joins += f" AND W.{wmap['empresa']} = S.{m['empresa']}"
    try:
        order_key = m.get('articulo') or m.get('descripcion') or m.get('almacen') or m.get('tipologia') or (m.get('periodo') or '')
        cursor.execute(f"SELECT {select} FROM {table} S{joins} {where} ORDER BY {order_key} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", tuple(params + [offset, limit]))
        rows = cursor.fetchall()
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    items = []
    for r in rows:
        d = {}
        for i, key in enumerate(index_keys):
            val = r[i]
            if key == 'unidades':
                d['unidades'] = int(val or 0)
            elif key == 'almacen_name':
                d['almacen'] = val
            elif key == 'almacen_code' and not d.get('almacen'):
                d['almacen'] = val
            elif key == 'articulo_desc':
                d['descripcion'] = val
            else:
                d[key] = val
        items.append(d)
    conn.close()
    return JsonResponse({'status': 'ok', 'items': items})

@router.get("/expiring")
def expiring(request, empresa: int, ejercicio: int, days_to_expire: int = 30, periodo: int = 0, almacen: str = "", ubicacion: str = "", tipologia: str = "", limit: int = 200, offset: int = 0):
    conn, cursor, table, m = get_connection_and_mapping()
    if not table or not m.get('fecha_caducidad'):
        return JsonResponse({'status': 'error', 'message': 'Campo de caducidad no disponible'}, status=404)
    ucol = m.get('unidad_saldo') or m.get('cantidad')
    fields = [c for c in [m.get('articulo'), m.get('descripcion'), m.get('fecha_caducidad'), ucol, m.get('almacen'), m.get('ubicacion'), m.get('tipologia')] if c]
    select = ", ".join(fields)
    where = f"WHERE {m['empresa']}=? AND {m['ejercicio']}=?"
    params = [empresa, ejercicio]
    if m.get('periodo'):
        if periodo and periodo not in [0, 99]:
            where += f" AND {m['periodo']}=?"
            params.append(periodo)
        else:
            where += f" AND ({m['periodo']}=0 OR {m['periodo']} BETWEEN ? AND ?)"
            params.extend([1, 12])
    if m.get('almacen') and almacen:
        where += f" AND {m['almacen']}=?"
        params.append(almacen)
    if m.get('ubicacion') and ubicacion:
        where += f" AND {m['ubicacion']}=?"
        params.append(ubicacion)
    if m.get('tipologia') and tipologia:
        where += f" AND {m['tipologia']}=?"
        params.append(tipologia)
    try:
        cursor.execute(f"SELECT {select} FROM {table} {where} ORDER BY {m.get('fecha_caducidad')} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", tuple(params + [offset, limit]))
        rows = cursor.fetchall()
    except Exception as e:
        conn.close()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    from datetime import datetime, timedelta, date
    now = datetime.now().date()
    items = []
    for r in rows:
        idx = 0
        d = {}
        if m.get('articulo'):
            d['articulo'] = r[idx]; idx += 1
        if m.get('descripcion'):
            d['descripcion'] = r[idx]; idx += 1
        cad = r[idx]; idx += 1
        try:
            d['caducidad'] = cad.date() if hasattr(cad, 'date') else cad
        except:
            d['caducidad'] = cad
        if ucol:
            d['unidades'] = int(r[idx] or 0); idx += 1
        else:
            d['unidades'] = 0
        if m.get('almacen'):
            d['almacen'] = r[idx]; idx += 1
        if m.get('ubicacion'):
            d['ubicacion'] = r[idx]; idx += 1
        if m.get('tipologia'):
            d['tipologia'] = r[idx]; idx += 1
        try:
            if isinstance(d['caducidad'], date):
                d['dias'] = (d['caducidad'] - now).days
            else:
                d['dias'] = None
        except:
            d['dias'] = None
        if d['dias'] is None or d['dias'] <= days_to_expire:
            items.append(d)
    conn.close()
    return JsonResponse({'status': 'ok', 'items': items})
