from datia.models import (
    MetricsTotalesEmpresaEjercicio,
    MetricsTotalesEmpresaEjercicioMes,
    MetricsTotalesEmpresaEjercicioCliente,
    MetricsTotalesEmpresaEjercicioArticulo,
    MetricsTotalesEmpresaEjercicioCodigoPostal,
    MetricsTotalesEmpresaEjercicioClienteMes,
    MetricsTotalesEmpresaEjercicioCompra,
    MetricsTotalesEmpresaEjercicioCompraMes,
    MetricsTotalesEmpresaEjercicioProveedor,
    MetricsTotalesEmpresaEjercicioArticuloCompra,
    MetricsTotalesEmpresaEjercicioProveedorMes,
)
from decimal import Decimal

class TotalsService:
    def process_row(self, row: dict):
        """
        Aggregates a single normalized row into all relevant Total tables.
        In production, this should be batched.
        """
        empresa = row['empresa']
        ejercicio = row['ejercicio']
        fecha = row['fecha']
        neto = Decimal(row['neto'])
        con_iva = Decimal(row.get('con_iva', 0))
        coste = Decimal(row['coste'])
        
        # 1. Global
        self._upsert_total(MetricsTotalesEmpresaEjercicio, {'empresa': empresa, 'ejercicio': ejercicio}, neto, coste, con_iva)
        
        # 2. Monthly
        if fecha:
            mes = fecha.month
            self._upsert_total(MetricsTotalesEmpresaEjercicioMes, 
                             {'empresa': empresa, 'ejercicio': ejercicio, 'mes': mes}, 
                             neto, coste)

        # 3. Client
        if row['cliente']:
            self._upsert_total(MetricsTotalesEmpresaEjercicioCliente,
                             {'empresa': empresa, 'ejercicio': ejercicio, 'cliente': row['cliente']},
                             neto, coste, extra={'nombre': row.get('nombre_cliente') or f"Client {row['cliente']}"})

        # 4. Articulo
        if row.get('articulo'):
            self._upsert_total(MetricsTotalesEmpresaEjercicioArticulo,
                              {'empresa': empresa, 'ejercicio': ejercicio, 'articulo': row['articulo']},
                              neto, coste, extra={'descripcion': row.get('descripcion')})

        # 5. Zip Code (Codigo Postal)
        # if row.get('cod_postal'):
        #     self._upsert_total(MetricsTotalesEmpresaEjercicioCodigoPostal,
        #                      {'empresa': empresa, 'ejercicio': ejercicio, 'cod_postal': row['cod_postal']},
        #                      neto, coste)

        # 6. Client/Month (Granular)
        if row['cliente'] and fecha:
            self._upsert_total(MetricsTotalesEmpresaEjercicioClienteMes,
                             {'empresa': empresa, 'ejercicio': ejercicio, 'cliente': row['cliente'], 'mes': fecha.month},
                             neto, coste, extra={'nombre': row.get('nombre_cliente') or f"Client {row['cliente']}"})

    def reset_sales_metrics(self, empresa: int, ejercicio: int):
        MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioArticulo.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioCodigoPostal.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioClienteMes.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()

    def process_sales_rows(self, rows):
        for row in rows:
            self.process_row(row)

    def process_purchase_row(self, row: dict):
        empresa = row['empresa']
        ejercicio = row['ejercicio']
        fecha = row.get('fecha')
        neto = Decimal(row['neto'])
        con_iva = Decimal(row.get('con_iva', 0))
        proveedor = row.get('proveedor') or ''
        nombre_proveedor = row.get('nombre_proveedor') or None
        articulo = row.get('articulo') or ''
        descripcion = row.get('descripcion') or None

        self._upsert_total(MetricsTotalesEmpresaEjercicioCompra, {'empresa': empresa, 'ejercicio': ejercicio}, neto, Decimal(0), con_iva)
        if fecha:
            self._upsert_total(MetricsTotalesEmpresaEjercicioCompraMes, {'empresa': empresa, 'ejercicio': ejercicio, 'mes': fecha.month}, neto, Decimal(0))
        if proveedor:
            self._upsert_total(MetricsTotalesEmpresaEjercicioProveedor, {'empresa': empresa, 'ejercicio': ejercicio, 'proveedor': proveedor}, neto, Decimal(0), extra={'nombre': nombre_proveedor})
        if articulo:
            self._upsert_total(MetricsTotalesEmpresaEjercicioArticuloCompra, {'empresa': empresa, 'ejercicio': ejercicio, 'articulo': articulo}, neto, Decimal(0), extra={'descripcion': descripcion})
        if proveedor and fecha:
            self._upsert_total(MetricsTotalesEmpresaEjercicioProveedorMes, {'empresa': empresa, 'ejercicio': ejercicio, 'proveedor': proveedor, 'mes': fecha.month}, neto, Decimal(0), extra={'nombre': nombre_proveedor})

    def process_purchase_rows(self, rows):
        for row in rows:
            self.process_purchase_row(row)

    def reset_purchases_metrics(self, empresa: int, ejercicio: int):
        MetricsTotalesEmpresaEjercicioCompra.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioArticuloCompra.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()
        MetricsTotalesEmpresaEjercicioProveedorMes.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()

    def _upsert_total(self, model, filters, neto, coste, con_iva=0, extra=None):
        obj, created = model.objects.get_or_create(**filters)
        
        obj.importe_neto_total += neto
        obj.importe_con_iva_total += con_iva
        obj.importe_coste_total += coste
        obj.albaranes_count += 1 # Rough count, strictly should verify unique albaranes
        
        if extra:
            for k, v in extra.items():
                setattr(obj, k, v)
        
        obj.save()

    def aggregate_from_datiadb_sales(self, empresa, ejercicio):
        from django.db import connections
        from django.utils import timezone
        cur = connections['analytics'].cursor()
        now = timezone.now()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name IN ('datiadb_lineasalbarancliente','datiadb_cabeceraalbarancliente','datiadb_cabecerapedidocliente')")
        tables = [r[0] for r in cur.fetchall()]
        if not tables:
            return
        if 'datiadb_lineasalbarancliente' in tables:
            table = 'datiadb_lineasalbarancliente'
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])
            cols = [r[0] for r in cur.fetchall()]
            s = set(cols)

            def pick(cands):
                for c in cands:
                    if c in s:
                        return c
                return None

            emp_col = pick(['codigoempresa', 'empresa', 'empresacodigo'])
            year_col = pick(['ejercicioalbaran', 'ejercicio', 'ejercicioalbarancliente', 'year'])
            date_col = pick(['fechaalbaran', 'fecha', 'fechapedido'])
            cli_col = pick(['codigocliente', 'cliente', 'id_cliente'])
            art_col = pick(['codigoarticulo', 'articulo', 'id_articulo'])
            qty_col = pick(['unidades', 'cantidad', 'cantidad1', 'unidades1', 'unidadesalbaran'])
            num_col = pick(['numeroalbaran', 'numeropedido', 'numero'])
            net_col = pick(['importeneto', 'importeliquido', 'baseimponible', 'importebruto'])
            coniva_col = pick(['importetotal', 'importefactura', 'importeconiva', 'totalconiva', 'importebruto'])
            precio_coste_col = pick(['preciocoste', 'precio_coste', 'precio_coste_unitario', 'costeunitario'])
            importe_coste_col = pick(['importecoste', 'importecosdte', 'importe_coste', 'importecostetotal', 'costetotal', 'importetotalcoste', 'importecostelineas'])

            if not emp_col or (not year_col and not date_col) or not net_col:
                return

            year_expr = year_col if year_col else f"CAST(EXTRACT(YEAR FROM {date_col}) AS INTEGER)"
            month_expr = f"CAST(EXTRACT(MONTH FROM {date_col}) AS INTEGER)" if date_col else "NULL"
            qty_expr = f"COALESCE({qty_col}, 1)" if qty_col else "1"

            if art_col:
                join_art = f"LEFT JOIN datia_articulos da ON da.empresa = %s AND da.articulo = {art_col}"
                price_fallback_expr = f"COALESCE(NULLIF(da.precio_compra, 0), 0)"
            else:
                join_art = ""
                price_fallback_expr = "0"

            if importe_coste_col and precio_coste_col:
                line_cost = f"""
                    CASE
                      WHEN {importe_coste_col} IS NOT NULL AND {importe_coste_col} <> 0 THEN {importe_coste_col}
                      WHEN {precio_coste_col} IS NOT NULL AND {precio_coste_col} <> 0 THEN {precio_coste_col} * {qty_expr}
                      WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr}
                      ELSE 0
                    END
                """
            elif importe_coste_col:
                line_cost = f"""
                    CASE
                      WHEN {importe_coste_col} IS NOT NULL AND {importe_coste_col} <> 0 THEN {importe_coste_col}
                      WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr}
                      ELSE 0
                    END
                """
            elif precio_coste_col:
                line_cost = f"""
                    CASE
                      WHEN {precio_coste_col} IS NOT NULL AND {precio_coste_col} <> 0 THEN {precio_coste_col} * {qty_expr}
                      WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr}
                      ELSE 0
                    END
                """
            else:
                line_cost = "0"

            net_expr = f"COALESCE(SUM({net_col}), 0)"
            coniva_expr = f"COALESCE(SUM({coniva_col}), 0)" if coniva_col else "0"
            cost_expr = f"COALESCE(SUM({line_cost}), 0)"
            count_expr = f"COUNT(DISTINCT {num_col})" if num_col else "COUNT(*)"

            cur.execute("DELETE FROM metrics_totales_empresa_ejercicio WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            sql_global = f"""
                INSERT INTO metrics_totales_empresa_ejercicio
                (empresa, ejercicio, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                FROM {table}
                {join_art}
                WHERE {emp_col} = %s AND {year_expr} = %s
            """
            params_global = [empresa, ejercicio, now]
            if art_col:
                params_global.append(empresa)
            params_global.extend([empresa, ejercicio])
            cur.execute(sql_global, params_global)

            cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_mes WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            if date_col:
                sql_mes = f"""
                    INSERT INTO metrics_totales_empresa_ejercicio_mes
                    (empresa, ejercicio, mes, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                    SELECT %s, %s, {month_expr}, {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                    FROM {table}
                    {join_art}
                    WHERE {emp_col} = %s AND {year_expr} = %s AND {date_col} IS NOT NULL
                    GROUP BY {month_expr}
                """
                params_mes = [empresa, ejercicio, now]
                if art_col:
                    params_mes.append(empresa)
                params_mes.extend([empresa, ejercicio])
                cur.execute(sql_mes, params_mes)

            cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_cliente WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            if cli_col:
                sql_cli = f"""
                    INSERT INTO metrics_totales_empresa_ejercicio_cliente
                    (empresa, ejercicio, cliente, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                    SELECT %s, %s, {cli_col},
                           COALESCE(MAX(dc.nombre), CAST({cli_col} AS TEXT)),
                           {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                    FROM {table}
                    LEFT JOIN datia_cliente dc ON dc.empresa = %s AND dc.cliente = {cli_col}
                    {join_art}
                    WHERE {emp_col} = %s AND {year_expr} = %s AND {cli_col} IS NOT NULL
                    GROUP BY {cli_col}
                """
                params_cli = [empresa, ejercicio, now, empresa]
                if art_col:
                    params_cli.append(empresa)
                params_cli.extend([empresa, ejercicio])
                cur.execute(sql_cli, params_cli)
            elif 'datiadb_cabeceraalbarancliente' in tables and year_col and num_col:
                hdr_table = 'datiadb_cabeceraalbarancliente'
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [hdr_table])
                hdr_cols = [r[0] for r in cur.fetchall()]
                hs = set(hdr_cols)
                def pick_hdr(cands):
                    for c in cands:
                        if c in hs:
                            return c
                    return None
                hdr_emp = pick_hdr(['codigoempresa', 'empresa', 'empresacodigo'])
                hdr_year = pick_hdr(['ejercicioalbaran', 'ejercicio', 'year'])
                hdr_serie = pick_hdr(['seriealbaran', 'serie', 'seriedocumento', 'serie_documento'])
                hdr_num = pick_hdr(['numeroalbaran', 'numero'])
                hdr_cli = pick_hdr(['id_cliente', 'codigocliente', 'cliente'])
                serie_col = pick(['seriealbaran', 'serie', 'seriedocumento', 'serie_documento', 'seriepedido'])
                if hdr_emp and hdr_year and hdr_num and hdr_cli:
                    join_art_l = ""
                    price_fallback_expr = "0"
                    if art_col:
                        join_art_l = f"LEFT JOIN datia_articulos da ON da.empresa = %s AND da.articulo = L.{art_col}"
                        price_fallback_expr = f"COALESCE(NULLIF(da.precio_compra, 0), 0)"
                    qty_expr_l = f"COALESCE(L.{qty_col}, 1)" if qty_col else "1"
                    if importe_coste_col and precio_coste_col:
                        line_cost_l = f"""
                            CASE
                              WHEN L.{importe_coste_col} IS NOT NULL AND L.{importe_coste_col} <> 0 THEN L.{importe_coste_col}
                              WHEN L.{precio_coste_col} IS NOT NULL AND L.{precio_coste_col} <> 0 THEN L.{precio_coste_col} * {qty_expr_l}
                              WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr_l}
                              ELSE 0
                            END
                        """
                    elif importe_coste_col:
                        line_cost_l = f"""
                            CASE
                              WHEN L.{importe_coste_col} IS NOT NULL AND L.{importe_coste_col} <> 0 THEN L.{importe_coste_col}
                              WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr_l}
                              ELSE 0
                            END
                        """
                    elif precio_coste_col:
                        line_cost_l = f"""
                            CASE
                              WHEN L.{precio_coste_col} IS NOT NULL AND L.{precio_coste_col} <> 0 THEN L.{precio_coste_col} * {qty_expr_l}
                              WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr_l}
                              ELSE 0
                            END
                        """
                    else:
                        line_cost_l = "0"
                    year_expr_l = f"L.{year_col}"
                    month_expr_l = f"CAST(EXTRACT(MONTH FROM L.{date_col}) AS INTEGER)" if date_col else "NULL"
                    net_expr_l = f"COALESCE(SUM(L.{net_col}), 0)"
                    coniva_expr_l = f"COALESCE(SUM(L.{coniva_col}), 0)" if coniva_col else "0"
                    cost_expr_l = f"COALESCE(SUM({line_cost_l}), 0)"
                    if hdr_serie:
                        count_expr_l = f"COUNT(DISTINCT (H.{hdr_serie}, H.{hdr_num}))"
                    else:
                        count_expr_l = f"COUNT(DISTINCT H.{hdr_num})"
                    sql_cli = f"""
                        INSERT INTO metrics_totales_empresa_ejercicio_cliente
                        (empresa, ejercicio, cliente, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                        SELECT %s, %s, H.{hdr_cli},
                               COALESCE(MAX(dc.nombre), CAST(H.{hdr_cli} AS TEXT)),
                               {net_expr_l}, {coniva_expr_l}, {cost_expr_l}, {count_expr_l}, %s
                        FROM {table} L
                        JOIN {hdr_table} H
                          ON L.{emp_col} = H.{hdr_emp}
                         AND L.{year_col} = H.{hdr_year}
                         {"AND L."+serie_col+" = H."+hdr_serie if (serie_col and hdr_serie) else ""}
                         AND L.{num_col} = H.{hdr_num}
                        LEFT JOIN datia_cliente dc ON dc.empresa = %s AND dc.cliente = H.{hdr_cli}
                        {join_art_l}
                        WHERE L.{emp_col} = %s AND {year_expr_l} = %s AND H.{hdr_cli} IS NOT NULL
                        GROUP BY H.{hdr_cli}
                    """
                    params_cli = [empresa, ejercicio, now, empresa]
                    if art_col:
                        params_cli.append(empresa)
                    params_cli.extend([empresa, ejercicio])
                    cur.execute(sql_cli, params_cli)

            cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_cliente_mes WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            if cli_col and date_col:
                sql_cli_mes = f"""
                    INSERT INTO metrics_totales_empresa_ejercicio_cliente_mes
                    (empresa, ejercicio, cliente, mes, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                    SELECT %s, %s, {cli_col}, {month_expr},
                           COALESCE(MAX(dc.nombre), CAST({cli_col} AS TEXT)),
                           {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                    FROM {table}
                    LEFT JOIN datia_cliente dc ON dc.empresa = %s AND dc.cliente = {cli_col}
                    {join_art}
                    WHERE {emp_col} = %s AND {year_expr} = %s AND {cli_col} IS NOT NULL AND {date_col} IS NOT NULL
                    GROUP BY {cli_col}, {month_expr}
                """
                params_cli_mes = [empresa, ejercicio, now, empresa]
                if art_col:
                    params_cli_mes.append(empresa)
                params_cli_mes.extend([empresa, ejercicio])
                cur.execute(sql_cli_mes, params_cli_mes)
            elif 'datiadb_cabeceraalbarancliente' in tables and year_col and num_col and date_col:
                hdr_table = 'datiadb_cabeceraalbarancliente'
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [hdr_table])
                hdr_cols = [r[0] for r in cur.fetchall()]
                hs = set(hdr_cols)
                def pick_hdr(cands):
                    for c in cands:
                        if c in hs:
                            return c
                    return None
                hdr_emp = pick_hdr(['codigoempresa', 'empresa', 'empresacodigo'])
                hdr_year = pick_hdr(['ejercicioalbaran', 'ejercicio', 'year'])
                hdr_serie = pick_hdr(['seriealbaran', 'serie', 'seriedocumento', 'serie_documento'])
                hdr_num = pick_hdr(['numeroalbaran', 'numero'])
                hdr_cli = pick_hdr(['id_cliente', 'codigocliente', 'cliente'])
                serie_col = pick(['seriealbaran', 'serie', 'seriedocumento', 'serie_documento', 'seriepedido'])
                if hdr_emp and hdr_year and hdr_num and hdr_cli:
                    join_art_l = ""
                    price_fallback_expr = "0"
                    if art_col:
                        join_art_l = f"LEFT JOIN datia_articulos da ON da.empresa = %s AND da.articulo = L.{art_col}"
                        price_fallback_expr = f"COALESCE(NULLIF(da.precio_compra, 0), 0)"
                    qty_expr_l = f"COALESCE(L.{qty_col}, 1)" if qty_col else "1"
                    if importe_coste_col and precio_coste_col:
                        line_cost_l = f"""
                            CASE
                              WHEN L.{importe_coste_col} IS NOT NULL AND L.{importe_coste_col} <> 0 THEN L.{importe_coste_col}
                              WHEN L.{precio_coste_col} IS NOT NULL AND L.{precio_coste_col} <> 0 THEN L.{precio_coste_col} * {qty_expr_l}
                              WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr_l}
                              ELSE 0
                            END
                        """
                    elif importe_coste_col:
                        line_cost_l = f"""
                            CASE
                              WHEN L.{importe_coste_col} IS NOT NULL AND L.{importe_coste_col} <> 0 THEN L.{importe_coste_col}
                              WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr_l}
                              ELSE 0
                            END
                        """
                    elif precio_coste_col:
                        line_cost_l = f"""
                            CASE
                              WHEN L.{precio_coste_col} IS NOT NULL AND L.{precio_coste_col} <> 0 THEN L.{precio_coste_col} * {qty_expr_l}
                              WHEN {price_fallback_expr} <> 0 THEN {price_fallback_expr} * {qty_expr_l}
                              ELSE 0
                            END
                        """
                    else:
                        line_cost_l = "0"
                    year_expr_l = f"L.{year_col}"
                    month_expr_l = f"CAST(EXTRACT(MONTH FROM L.{date_col}) AS INTEGER)"
                    net_expr_l = f"COALESCE(SUM(L.{net_col}), 0)"
                    coniva_expr_l = f"COALESCE(SUM(L.{coniva_col}), 0)" if coniva_col else "0"
                    cost_expr_l = f"COALESCE(SUM({line_cost_l}), 0)"
                    if hdr_serie:
                        count_expr_l = f"COUNT(DISTINCT (H.{hdr_serie}, H.{hdr_num}))"
                    else:
                        count_expr_l = f"COUNT(DISTINCT H.{hdr_num})"
                    sql_cli_mes = f"""
                        INSERT INTO metrics_totales_empresa_ejercicio_cliente_mes
                        (empresa, ejercicio, cliente, mes, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                        SELECT %s, %s, H.{hdr_cli}, {month_expr_l},
                               COALESCE(MAX(dc.nombre), CAST(H.{hdr_cli} AS TEXT)),
                               {net_expr_l}, {coniva_expr_l}, {cost_expr_l}, {count_expr_l}, %s
                        FROM {table} L
                        JOIN {hdr_table} H
                          ON L.{emp_col} = H.{hdr_emp}
                         AND L.{year_col} = H.{hdr_year}
                         {"AND L."+serie_col+" = H."+hdr_serie if (serie_col and hdr_serie) else ""}
                         AND L.{num_col} = H.{hdr_num}
                        LEFT JOIN datia_cliente dc ON dc.empresa = %s AND dc.cliente = H.{hdr_cli}
                        {join_art_l}
                        WHERE L.{emp_col} = %s AND {year_expr_l} = %s AND H.{hdr_cli} IS NOT NULL AND L.{date_col} IS NOT NULL
                        GROUP BY H.{hdr_cli}, {month_expr_l}
                    """
                    params_cli_mes = [empresa, ejercicio, now, empresa]
                    if art_col:
                        params_cli_mes.append(empresa)
                    params_cli_mes.extend([empresa, ejercicio])
                    cur.execute(sql_cli_mes, params_cli_mes)

            cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_articulo WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            if art_col:
                sql_art = f"""
                    INSERT INTO metrics_totales_empresa_ejercicio_articulo
                    (empresa, ejercicio, articulo, descripcion, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                    SELECT %s, %s, {art_col},
                           COALESCE(MAX(da.descripcion), CAST({art_col} AS TEXT)),
                           {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                    FROM {table}
                    {join_art}
                    WHERE {emp_col} = %s AND {year_expr} = %s AND {art_col} IS NOT NULL
                    GROUP BY {art_col}
                """
                params_art = [empresa, ejercicio, now, empresa, empresa, ejercicio]
                cur.execute(sql_art, params_art)

            try:
                cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_cod_postal WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
                sql_cp = """
                    INSERT INTO metrics_totales_empresa_ejercicio_cod_postal
                    (empresa, ejercicio, cod_postal, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                    SELECT
                        %s, %s, dc.cod_postal,
                        COALESCE(SUM(m.importe_neto_total), 0),
                        COALESCE(SUM(m.importe_con_iva_total), 0),
                        COALESCE(SUM(m.importe_coste_total), 0),
                        COALESCE(SUM(m.albaranes_count), 0),
                        %s
                    FROM metrics_totales_empresa_ejercicio_cliente m
                    JOIN datia_cliente dc
                      ON dc.empresa = %s AND dc.cliente = m.cliente
                    WHERE m.empresa = %s AND m.ejercicio = %s
                      AND dc.cod_postal IS NOT NULL AND BTRIM(dc.cod_postal) <> ''
                    GROUP BY dc.cod_postal
                """
                cur.execute(sql_cp, [empresa, ejercicio, now, empresa, empresa, ejercicio])
            except Exception:
                pass
            return

        table = 'datiadb_cabeceraalbarancliente' if 'datiadb_cabeceraalbarancliente' in tables else tables[0]
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])
        cols = [r[0] for r in cur.fetchall()]
        s = set(cols)
        def pick(cands):
            for c in cands:
                if c in s:
                    return c
            return None
        emp_col = pick(['codigoempresa','empresa','empresacodigo'])
        year_col = pick(['ejercicioalbaran','ejercicio','year'])
        date_col = pick(['fechaalbaran','fecha','fechapedido'])
        cli_col = pick(['id_cliente','codigocliente','cliente'])
        num_col = pick(['numeroalbaran','numeropedido','numero'])
        net_col = pick(['importeneto','importeliquido','baseimponible','importebruto'])
        coniva_col = pick(['importefactura','importetotal','importeconiva','totalconiva'])
        if not emp_col or (not year_col and not date_col) or not net_col:
            return
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        net_expr = f"COALESCE(SUM({net_col}), 0)"
        coniva_expr = f"COALESCE(SUM({coniva_col}), 0)" if coniva_col else "0"
        cost_col = pick(['importecoste', 'importecosdte', 'importecostetotal', 'importe_coste', 'costetotal', 'importetotalcoste', 'importecostelineas'])
        cost_expr = f"COALESCE(SUM({cost_col}), 0)" if cost_col else "0"
        count_expr = f"COUNT(DISTINCT {num_col})" if num_col else "COUNT(*)"
        year_expr = year_col if year_col else f"CAST(EXTRACT(YEAR FROM {date_col}) AS INTEGER)"
        sql_global = f"""
            INSERT INTO metrics_totales_empresa_ejercicio
            (empresa, ejercicio, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
            SELECT %s, %s, {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
            FROM {table}
            WHERE {emp_col} = %s AND {year_expr} = %s
        """
        cur.execute(sql_global, [empresa, ejercicio, now, empresa, ejercicio])
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_mes WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        if date_col:
            sql_mes = f"""
                INSERT INTO metrics_totales_empresa_ejercicio_mes
                (empresa, ejercicio, mes, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, CAST(EXTRACT(MONTH FROM {date_col}) AS INTEGER), {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                FROM {table}
                WHERE {emp_col} = %s AND {year_expr} = %s AND {date_col} IS NOT NULL
                GROUP BY EXTRACT(MONTH FROM {date_col})
            """
            cur.execute(sql_mes, [empresa, ejercicio, now, empresa, ejercicio])
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_cliente WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        if cli_col:
            sql_cli = f"""
                INSERT INTO metrics_totales_empresa_ejercicio_cliente
                (empresa, ejercicio, cliente, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, {cli_col}, COALESCE(MAX(dc.nombre), CAST({cli_col} AS TEXT)), {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                FROM {table}
                LEFT JOIN datia_cliente dc ON dc.empresa = %s AND dc.cliente = {cli_col}
                WHERE {emp_col} = %s AND {year_expr} = %s AND {cli_col} IS NOT NULL
                GROUP BY {cli_col}
            """
            cur.execute(sql_cli, [empresa, ejercicio, now, empresa, empresa, ejercicio])
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_cliente_mes WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        if cli_col and date_col:
            sql_cli_mes = f"""
                INSERT INTO metrics_totales_empresa_ejercicio_cliente_mes
                (empresa, ejercicio, cliente, mes, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, {cli_col}, CAST(EXTRACT(MONTH FROM {date_col}) AS INTEGER), COALESCE(MAX(dc.nombre), CAST({cli_col} AS TEXT)), {net_expr}, {coniva_expr}, {cost_expr}, {count_expr}, %s
                FROM {table}
                LEFT JOIN datia_cliente dc ON dc.empresa = %s AND dc.cliente = {cli_col}
                WHERE {emp_col} = %s AND {year_expr} = %s AND {cli_col} IS NOT NULL AND {date_col} IS NOT NULL
                GROUP BY {cli_col}, EXTRACT(MONTH FROM {date_col})
            """
            cur.execute(sql_cli_mes, [empresa, ejercicio, now, empresa, empresa, ejercicio])

        try:
            cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_cod_postal WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            sql_cp = """
                INSERT INTO metrics_totales_empresa_ejercicio_cod_postal
                (empresa, ejercicio, cod_postal, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT
                    %s, %s, dc.cod_postal,
                    COALESCE(SUM(m.importe_neto_total), 0),
                    COALESCE(SUM(m.importe_con_iva_total), 0),
                    COALESCE(SUM(m.importe_coste_total), 0),
                    COALESCE(SUM(m.albaranes_count), 0),
                    %s
                FROM metrics_totales_empresa_ejercicio_cliente m
                JOIN datia_cliente dc
                  ON dc.empresa = %s AND dc.cliente = m.cliente
                WHERE m.empresa = %s AND m.ejercicio = %s
                  AND dc.cod_postal IS NOT NULL AND BTRIM(dc.cod_postal) <> ''
                GROUP BY dc.cod_postal
            """
            cur.execute(sql_cp, [empresa, ejercicio, now, empresa, empresa, ejercicio])
        except Exception:
            pass

    def _importe_con_datos(self, cur, table, pick, candidatos, emp_col, empresa, periodo_col, ejercicio, periodo_es_anio):
        existentes = [col for col in candidatos if pick([col])]
        if not existentes or not emp_col or not periodo_col:
            return existentes[0] if existentes else None
        if periodo_es_anio:
            filtro = f"{periodo_col} = %s"
        else:
            filtro = f"CAST(EXTRACT(YEAR FROM {periodo_col}) AS INTEGER) = %s"
        for col in existentes:
            cur.execute(
                f"SELECT COALESCE(SUM({col}), 0) FROM {table} WHERE {emp_col} = %s AND {filtro}",
                [empresa, ejercicio],
            )
            total = cur.fetchone()[0]
            try:
                if float(total or 0) != 0:
                    return col
            except (TypeError, ValueError):
                continue
        return existentes[0]

    def aggregate_from_datiadb_purchases(self, empresa, ejercicio):
        from django.db import connections
        from django.utils import timezone
        cur = connections['analytics'].cursor()
        now = timezone.now()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name IN ('datiadb_cabeceraalbaranproveedor')")
        rows = cur.fetchall()
        if not rows:
            return
        table = 'datiadb_cabeceraalbaranproveedor'
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])
        cols = [r[0] for r in cur.fetchall()]
        s = set(cols)
        def pick(cands):
            for c in cands:
                if c in s:
                    return c
            return None
        emp_col = pick(['codigoempresa','empresa','empresacodigo'])
        year_col = pick(['ejercicioalbaran','ejercicio','year'])
        date_col = pick(['fechaalbaran','fecha'])
        prov_col = pick(['codigoproveedor','proveedor','id_proveedor'])
        num_col = pick(['numeroalbaran','numero'])
        net_col = self._importe_con_datos(
            cur, table, pick,
            ['importeliquido', 'importeneto', 'baseimponible', 'importebruto'],
            emp_col, empresa, year_col or date_col, ejercicio, year_col is not None,
        )
        coniva_col = pick(['importetotal','importeconiva','totalconiva'])
        if not emp_col or (not year_col and not date_col) or not net_col:
            return
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_compra WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        net_expr = f"COALESCE(SUM({net_col}), 0)"
        coniva_expr = f"COALESCE(SUM({coniva_col}), 0)" if coniva_col else "0"
        count_expr = f"COUNT(DISTINCT {num_col})" if num_col else "COUNT(*)"
        year_expr = year_col if year_col else f"CAST(EXTRACT(YEAR FROM {date_col}) AS INTEGER)"
        sql_global = f"""
            INSERT INTO metrics_totales_empresa_ejercicio_compra
            (empresa, ejercicio, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
            SELECT %s, %s, {net_expr}, {coniva_expr}, 0, {count_expr}, %s
            FROM {table}
            WHERE {emp_col} = %s AND {year_expr} = %s
        """
        cur.execute(sql_global, [empresa, ejercicio, now, empresa, ejercicio])
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_compra_mes WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        if date_col:
            sql_mes = f"""
                INSERT INTO metrics_totales_empresa_ejercicio_compra_mes
                (empresa, ejercicio, mes, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, CAST(EXTRACT(MONTH FROM {date_col}) AS INTEGER), {net_expr}, {coniva_expr}, 0, {count_expr}, %s
                FROM {table}
                WHERE {emp_col} = %s AND {year_expr} = %s AND {date_col} IS NOT NULL
                GROUP BY EXTRACT(MONTH FROM {date_col})
            """
            cur.execute(sql_mes, [empresa, ejercicio, now, empresa, ejercicio])
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_proveedor WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        if prov_col:
            sql_prov = f"""
                INSERT INTO metrics_totales_empresa_ejercicio_proveedor
                (empresa, ejercicio, proveedor, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, {prov_col}, COALESCE(MAX(dp.nombre), CAST({prov_col} AS TEXT)), {net_expr}, {coniva_expr}, 0, {count_expr}, %s
                FROM {table}
                LEFT JOIN datia_proveedores dp ON dp.empresa = %s AND dp.proveedor = {prov_col}
                WHERE {emp_col} = %s AND {year_expr} = %s AND {prov_col} IS NOT NULL
                GROUP BY {prov_col}
            """
            cur.execute(sql_prov, [empresa, ejercicio, now, empresa, empresa, ejercicio])
        cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_proveedor_mes WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
        if prov_col and date_col:
            sql_prov_mes = f"""
                INSERT INTO metrics_totales_empresa_ejercicio_proveedor_mes
                (empresa, ejercicio, proveedor, mes, nombre, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                SELECT %s, %s, {prov_col}, CAST(EXTRACT(MONTH FROM {date_col}) AS INTEGER), COALESCE(MAX(dp.nombre), CAST({prov_col} AS TEXT)), {net_expr}, {coniva_expr}, 0, {count_expr}, %s
                FROM {table}
                LEFT JOIN datia_proveedores dp ON dp.empresa = %s AND dp.proveedor = {prov_col}
                WHERE {emp_col} = %s AND {year_expr} = %s AND {prov_col} IS NOT NULL AND {date_col} IS NOT NULL
                GROUP BY {prov_col}, EXTRACT(MONTH FROM {date_col})
            """
            cur.execute(sql_prov_mes, [empresa, ejercicio, now, empresa, empresa, ejercicio])

        try:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'datiadb_lineasalbaranproveedor'")
            if cur.fetchone():
                l_table = 'datiadb_lineasalbaranproveedor'
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [l_table])
                l_cols = [r[0] for r in cur.fetchall()]
                ls = set(l_cols)
                def l_pick(cands):
                    for c in cands:
                        if c in ls:
                            return c
                    return None
                l_emp = l_pick(['codigoempresa','empresa','empresacodigo'])
                l_year = l_pick(['ejercicioalbaran','ejercicio','year'])
                l_date = l_pick(['fechaalbaran','fecha'])
                l_art = l_pick(['codigoarticulo','articulo'])
                l_num = l_pick(['numeroalbaran','numero'])
                l_net = self._importe_con_datos(
                    cur, l_table, l_pick,
                    ['importeneto', 'importeliquido', 'baseimponible', 'importebruto'],
                    l_emp, empresa, l_year or l_date, ejercicio, l_year is not None,
                )
                l_coniva = l_pick(['importefactura','importetotal','importeconiva','totalconiva'])
                if l_emp and (l_year or l_date) and l_art and l_net:
                    cur.execute("DELETE FROM metrics_totales_empresa_ejercicio_articulo_compra WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
                    l_year_expr = l_year if l_year else f"CAST(EXTRACT(YEAR FROM {l_date}) AS INTEGER)"
                    l_net_expr = f"COALESCE(SUM({l_net}), 0)"
                    l_coniva_expr = f"COALESCE(SUM({l_coniva}), 0)" if l_coniva else "0"
                    l_count_expr = f"COUNT(DISTINCT {l_num})" if l_num else "COUNT(*)"
                    sql_art = f"""
                        INSERT INTO metrics_totales_empresa_ejercicio_articulo_compra
                        (empresa, ejercicio, articulo, descripcion, importe_neto_total, importe_con_iva_total, importe_coste_total, albaranes_count, calculado_at)
                        SELECT
                            %s, %s, {l_art},
                            COALESCE(MAX(da.descripcion), CAST({l_art} AS TEXT)),
                            {l_net_expr}, {l_coniva_expr}, 0, {l_count_expr}, %s
                        FROM {l_table} L
                        LEFT JOIN datia_articulos da ON da.empresa = %s AND da.articulo = L.{l_art}
                        WHERE L.{l_emp} = %s AND {l_year_expr} = %s AND L.{l_art} IS NOT NULL
                        GROUP BY {l_art}
                    """
                    cur.execute(sql_art, [empresa, ejercicio, now, empresa, empresa, ejercicio])
        except Exception:
            pass

    def aggregate_from_local(self, empresa, ejercicio):
        raise RuntimeError("aggregate_from_local está obsoleto; usa aggregate_from_datiadb_sales.")

    def aggregate_purchases_from_local(self, empresa, ejercicio):
        raise RuntimeError("aggregate_purchases_from_local está obsoleto; usa aggregate_from_datiadb_purchases.")
