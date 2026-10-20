from ninja import Router
from typing import List, Dict, Any
from datia.factories import RepositoryFactory, ServiceFactory
from django.shortcuts import get_object_or_404
import threading
import uuid
import time
import json
from datia.services.ai.handlers.snapshot_handler import SnapshotHandler
import logging
import re
from datia.services.system_monitor import SystemMonitorService
from django.http import HttpResponse
from django.db import connections

# Simple in-memory job store for MVP
SYNC_JOBS = {}

def sync_worker(job_id, empresa, ejercicio):
    def update_progress(count):
        if job_id in SYNC_JOBS:
            SYNC_JOBS[job_id]['progress'] = count
            SYNC_JOBS[job_id]['last_updated'] = time.time()
            
    try:
        svc = ServiceFactory.get_etl_service()
        # Fast initialization first
        svc.sync_structure() 
        # Deep sync
        svc.sync_mssql_sales(empresa, ejercicio, progress_callback=update_progress)
        
        if job_id in SYNC_JOBS:
            SYNC_JOBS[job_id]['status'] = 'completed'
            SYNC_JOBS[job_id]['progress'] = 100 # conceptual 100% or just high count
    except Exception as e:
        logging.getLogger('datia.etl').error("Sync Job Failed: %s", e)
        if job_id in SYNC_JOBS:
            SYNC_JOBS[job_id]['status'] = 'error'
            SYNC_JOBS[job_id]['error'] = str(e)

router = Router()

@router.get("/filters")
def get_filters(request):
    from datia.models import MetricsTotalesEmpresaEjercicio, Empresa, UserEmpresaPermission
    from django.db.utils import ProgrammingError, OperationalError
    schema_status = SystemMonitorService.get_database_schema_status()
    if not schema_status.get("ok", True):
        return {
            "empresas": [],
            "ejercicios": [],
            "error": {
                "code": "MISSING_CORE_TABLE",
                "details": schema_status,
            },
        }
    authorized_ids = None
    if request.user.is_authenticated:
        try:
            user_permissions = UserEmpresaPermission.objects.filter(user=request.user)
            if user_permissions.exists():
                authorized_ids = set(user_permissions.values_list("empresa_id", flat=True))
        except (ProgrammingError, OperationalError):
            authorized_ids = None
    empresas_qs = Empresa.objects.all()
    empresas_list = []
    for e in empresas_qs:
        try:
            code_int = int(str(e.codigo).strip())
            if authorized_ids is not None and code_int not in authorized_ids:
                continue
            empresas_list.append({"code": code_int, "name": e.nombre})
        except Exception:
            continue
    qs = MetricsTotalesEmpresaEjercicio.objects.values("ejercicio").distinct()
    ejercicios = sorted(list(set(q["ejercicio"] for q in qs)), reverse=True)
    if not ejercicios:
        ejercicios = []
    return {
        "empresas": empresas_list,
        "ejercicios": ejercicios,
    }

@router.get("/widgets/snapshot")
def get_snapshot(request, empresa: int, ejercicio: int, kind: str = 'sales'):
    handler = SnapshotHandler()
    return {"data": handler.get_snapshot_metrics(empresa, ejercicio, kind=kind)}

@router.get("/widgets/{key}")
def get_widget_data(request, key: str, empresa: int = 1, ejercicio: int = 2025, limit: int = 5):
    """
    Generic Widget Data Endpoint.
    Routes to specific logic based on key.
    Enforces RBAC via WidgetConfig (Placeholder).
    """
    # Logic Map (Strategy Pattern)
    strategies = {
        'ventas_resumen': _get_ventas_resumen,
        'top_clientes': _get_top_clientes,
        'top_articulos': _get_top_articulos,
        'actividad_mensual': _get_actividad_mensual,
        'mapa_ventas': _get_mapa_ventas,
    }
    
    
    # [NEW] Strategies for Purchases (NF-023)
    strategies.update({
        'compras_resumen': _get_compras_resumen,
        'top_proveedores': _get_top_proveedores,
        'top_articulos_compra': _get_top_articulos_compra,
        'actividad_mensual_compra': _get_actividad_mensual_compra,
        'mapa_compras': _get_top_zonas_compra,
    })

    if key not in strategies:
        return {"error": "Widget not found", "data": {}}
    
    # Pass limit only to those who need it, or update all signatures. 
    # For simplicity, we check key or update signatures to accept **kwargs
    if key in ['top_clientes', 'top_articulos', 'top_proveedores', 'top_articulos_compra']:
         try:
             limit = int(limit)
         except:
             limit = 5
         return strategies[key](empresa, ejercicio, limit=limit)
         
    return strategies[key](empresa, ejercicio)

def _has_dashboard_permission(user, scope: str) -> bool:
    """
    Simple RBAC helper for entity dashboards.
    - Superusers and staff siempre permitidos.
    - Si el usuario no tiene grupos asignados, se permite acceso por compatibilidad.
    - En caso contrario, se comprueban grupos específicos por ámbito.
    """
    try:
        if not user or not getattr(user, "is_authenticated", False):
            return True
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        required_map = {
            "clientes": ["ROLE_DASHBOARD_CLIENTES", "ROLE_DASHBOARD_GLOBAL"],
            "proveedores": ["ROLE_DASHBOARD_PROVEEDORES", "ROLE_DASHBOARD_GLOBAL"],
            "articulos": ["ROLE_DASHBOARD_ARTICULOS", "ROLE_DASHBOARD_GLOBAL"],
        }
        required = required_map.get(scope, [])
        groups_qs = getattr(user, "groups", None)
        if not groups_qs:
            return True
        names = list(groups_qs.values_list("name", flat=True))
        if not names:
            return True
        return any(name in required for name in names)
    except Exception:
        return True


@router.get("/dashboard/clientes/overview")
def get_clientes_dashboard_overview(request, empresa: int, ejercicio: int, q: str = None, limit: int = 100):
    """
    Resumen interactivo de clientes: KPIs, tendencias y ranking.
    Usa tablas métricas preagregadas para mantener latencia baja.
    """
    if not _has_dashboard_permission(getattr(request, "user", None), "clientes"):
        return HttpResponse(status=403)

    from django.db.models import Sum, Count
    from datia.models import (
        MetricsTotalesEmpresaEjercicioCliente,
        MetricsTotalesEmpresaEjercicioClienteMes,
        MetricsTotalesEmpresaEjercicioMes,
    )

    base_qs = MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=ejercicio)
    if q:
        q_str = str(q).strip()
        if q_str:
            from django.db.models import Q as _Q
            if q_str.isdigit():
                base_qs = base_qs.filter(cliente__icontains=q_str)
            else:
                codes_from_master = []
                try:
                    alias = "analytics" if "analytics" in connections.databases else "default"
                    from django.db import connection as _default_conn

                    conn = connections[alias] if alias in connections.databases else _default_conn
                    like = f"%{q_str}%"
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT cliente
                            FROM datia_cliente
                            WHERE empresa=%s AND (cliente ILIKE %s OR nombre ILIKE %s)
                            """,
                            [empresa, like, like],
                        )
                        codes_from_master = [str(r[0]) for r in cur.fetchall() if r and r[0]]
                except Exception:
                    codes_from_master = []

                if codes_from_master:
                    base_qs = base_qs.filter(cliente__in=codes_from_master)
                else:
                    base_qs = base_qs.filter(_Q(cliente__icontains=q_str) | _Q(nombre__icontains=q_str))

    agg = base_qs.aggregate(
        total_clientes=Count("cliente"),
        ventas_total=Sum("importe_neto_total"),
        albaranes_total=Sum("albaranes_count"),
    )
    total_clientes = int(agg.get("total_clientes") or 0)
    ventas_total = float(agg.get("ventas_total") or 0.0)
    albaranes_total = int(agg.get("albaranes_total") or 0)
    ticket_medio = float(ventas_total / albaranes_total) if albaranes_total > 0 else 0.0

    actividad_qs = MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=ejercicio).order_by("mes")
    data_map = {m: {"neto": 0.0} for m in range(1, 13)}
    for row in actividad_qs:
        data_map[row.mes]["neto"] = float(row.importe_neto_total or 0.0)
    labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    ventas_mensuales = [data_map[m]["neto"] for m in range(1, 13)]

    names_map = {}
    try:
        alias = "analytics" if "analytics" in connections.databases else "default"
        codes = list(base_qs.values_list("cliente", flat=True).distinct())
        codes = [str(c or "") for c in codes if c]
        if codes:
            from django.db import connection as _default_conn
            conn = connections[alias] if alias in connections.databases else _default_conn
            placeholders = ",".join(["%s"] * len(codes))
            params = [empresa] + codes
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT empresa, cliente, nombre
                    FROM datia_cliente
                    WHERE empresa=%s AND cliente IN ({placeholders})
                    """,
                    params,
                )
                for row in cur.fetchall():
                    names_map[str(row[1])] = row[2] or row[1]
    except Exception:
        names_map = {}

    top_qs = base_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 200))]
    top_clientes = []
    for x in top_qs:
        cod = x.cliente
        nom = x.nombre or names_map.get(str(cod)) or cod
        top_clientes.append(
            {
                "codigo": cod,
                "nombre": nom,
                "ventas": float(x.importe_neto_total or 0.0),
                "albaranes": int(x.albaranes_count or 0),
            }
        )

    freq_buckets = {"1": 0, "2-5": 0, "6-10": 0, "11+": 0}
    for x in base_qs:
        ops = int(x.albaranes_count or 0)
        if ops <= 1:
            freq_buckets["1"] += 1
        elif ops <= 5:
            freq_buckets["2-5"] += 1
        elif ops <= 10:
            freq_buckets["6-10"] += 1
        else:
            freq_buckets["11+"] += 1

    tabla_rows = []
    for x in base_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 500))]:
        cod = x.cliente
        nom = x.nombre or names_map.get(str(cod)) or cod
        tabla_rows.append(
            {
                "codigo": cod,
                "nombre": nom,
                "ventas": float(x.importe_neto_total or 0.0),
                "albaranes": int(x.albaranes_count or 0),
                "ticket_medio": float((x.importe_neto_total or 0.0) / x.albaranes_count)
                if x.albaranes_count
                else 0.0,
            }
        )

    return {
        "kpi": {
            "total_clientes": total_clientes,
            "ventas_totales": ventas_total,
            "ticket_medio": ticket_medio,
            "operaciones_totales": albaranes_total,
        },
        "charts": {
            "ventas_mensuales": {"labels": labels, "ventas": ventas_mensuales},
            "top_clientes": {"data": top_clientes},
            "frecuencia": {
                "labels": list(freq_buckets.keys()),
                "clientes": [freq_buckets[k] for k in ["1", "2-5", "6-10", "11+"]],
            },
        },
        "table": {"rows": tabla_rows},
    }


@router.get("/dashboard/clientes/detail")
def get_cliente_dashboard_detail(request, empresa: int, ejercicio: int, codigo: str):
    """
    Detalle de un cliente concreto basado en métricas agregadas.
    Incluye evolución mensual y ranking de artículos vendidos.
    """
    if not _has_dashboard_permission(getattr(request, "user", None), "clientes"):
        return HttpResponse(status=403)

    from django.db.models import Sum, Min, Max, Count
    from datia.models import (
        MetricsTotalesEmpresaEjercicioCliente,
        MetricsTotalesEmpresaEjercicioClienteMes,
        MetricsTotalesEmpresaEjercicioArticulo,
    )

    codigo_raw = str(codigo or "").strip()
    codigo = codigo_raw
    if not codigo_raw:
        return {"error": "codigo requerido"}
    cliente_codigo = codigo_raw
    cliente_codigo_analytics = codigo_raw

    base_qs = MetricsTotalesEmpresaEjercicioCliente.objects.filter(
        empresa=empresa, cliente=codigo
    )
    base = base_qs.filter(ejercicio=ejercicio).first()

    alias = "analytics" if "analytics" in connections.databases else "default"
    nombre_cli = None
    nombre_fiscal = None
    cif_nif = None
    fecha_alta = None
    activo = None
    cod_postal = None
    try:
        with connections[alias].cursor() as cur:
            cur.execute(
                """
                SELECT cliente, nombre, nombre_fiscal, cif_nif, fecha_alta, activo, cod_postal
                FROM datia_cliente
                WHERE empresa=%s AND cliente=%s
                LIMIT 1
                """,
                [empresa, codigo],
            )
            row = cur.fetchone()
            if row:
                cliente_codigo_analytics = str(row[0] or cliente_codigo_analytics)
                nombre_cli = row[1] or row[0] or codigo
                nombre_fiscal = row[2]
                cif_nif = row[3]
                fecha_alta = row[4]
                activo = row[5]
                cod_postal = row[6]
    except Exception:
        nombre_cli = None

    from_year = max(int(ejercicio) - 3, 0)
    evol_qs = MetricsTotalesEmpresaEjercicioClienteMes.objects.filter(
        empresa=empresa, cliente=codigo, ejercicio__gte=from_year, ejercicio__lte=ejercicio
    ).order_by("ejercicio", "mes")
    labels = []
    ventas_mensuales = []
    for row in evol_qs:
        labels.append(f"{row.ejercicio}-{row.mes:02d}")
        ventas_mensuales.append(float(row.importe_neto_total or 0.0))

    top_articulos = []

    agg_hist = base_qs.aggregate(
        ventas_hist=Sum("importe_neto_total"),
        coste_hist=Sum("importe_coste_total"),
        ops_hist=Sum("albaranes_count"),
        min_ej=Min("ejercicio"),
        max_ej=Max("ejercicio"),
    )
    ventas_hist = float(agg_hist.get("ventas_hist") or 0.0)
    coste_hist = float(agg_hist.get("coste_hist") or 0.0)
    ops_hist = int(agg_hist.get("ops_hist") or 0)
    total_ventas = ventas_hist
    total_ops = ops_hist
    ticket_medio = float(total_ventas / total_ops) if total_ops > 0 else 0.0
    margen_pct = float(((ventas_hist - coste_hist) / ventas_hist) * 100.0) if ventas_hist > 0 else 0.0

    summary = {
        "total_pedidos": total_ops,
        "ventas_totales": total_ventas,
        "margen_pct": round(margen_pct, 2),
        "antiguedad_dias": None,
        "ultima_compra": None,
    }
    orders_rows = []
    deliveries_rows = []
    frequency = {
        "dias_promedio_entre_pedidos": None,
        "pedidos_12m": 0,
        "serie_mensual": {"labels": [], "pedidos": []},
    }

    hist_mes_qs = MetricsTotalesEmpresaEjercicioClienteMes.objects.filter(
        empresa=empresa, cliente=codigo
    ).order_by("ejercicio", "mes")
    if hist_mes_qs.exists():
        first_row = hist_mes_qs.first()
        last_row = hist_mes_qs.last()
        try:
            from datetime import date, timedelta

            first_date = date(first_row.ejercicio, first_row.mes or 1, 1)
            last_date = date(last_row.ejercicio, last_row.mes or 1, 1)
            summary["antiguedad_dias"] = max((last_date - first_date).days, 0)
            summary["ultima_compra"] = last_date.strftime("%d-%m-%Y")

            start_12m = last_date - timedelta(days=365)
            freq_map = {}
            for row in hist_mes_qs:
                try:
                    d = date(row.ejercicio, row.mes or 1, 1)
                except Exception:
                    continue
                if d < start_12m or d > last_date:
                    continue
                key = f"{row.ejercicio}-{row.mes:02d}"
                freq_map[key] = freq_map.get(key, 0) + int(row.albaranes_count or 0)
            freq_labels = sorted(freq_map.keys())
            freq_values = [freq_map[k] for k in freq_labels]
            frequency["serie_mensual"] = {"labels": freq_labels, "pedidos": freq_values}
            frequency["pedidos_12m"] = sum(freq_values)
            if len(freq_values) >= 2:
                avg_gap = 365.0 / max(len(freq_values), 1)
                frequency["dias_promedio_entre_pedidos"] = round(avg_gap, 1)
        except Exception:
            pass

    # Pedidos y albaranes del cliente
    try:
        # Cabecera de pedidos: solo datos de documento y dimensiones, sin artículos
        with connections[alias].cursor() as cur_schema:
            cur_schema.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'datiadb_cabecerapedidocliente'
                """
            )
            cab_cols = {row[0].lower() for row in cur_schema.fetchall()}
        with connections[alias].cursor() as cur_schema:
            cur_schema.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'datiadb_lineaspedidocliente'
                """
            )
            lin_cols = {row[0].lower() for row in cur_schema.fetchall()}

        def _cab_has(col_name: str) -> bool:
            return col_name.lower() in cab_cols

        def _lin_has(col_name: str) -> bool:
            return col_name.lower() in lin_cols

        cli_col_hdr = "id_cliente" if _cab_has("id_cliente") else ("codigocliente" if _cab_has("codigocliente") else ("cliente" if _cab_has("cliente") else None))
        if not cli_col_hdr:
            raise RuntimeError("No se encontró columna de cliente en cabecera de pedidos")

        select_parts = [
            "H.numeropedido AS numero",
            "H.seriepedido AS serie",
            "H.fechapedido AS fecha",
        ]
        if _cab_has("fechaentrega"):
            select_parts.append("H.fechaentrega AS fecha_entrega")
        else:
            select_parts.append("NULL AS fecha_entrega")

        dim_cols = [
            ("codigoproyecto", "proyecto"),
            ("codigoseccion", "seccion"),
            ("codigodelegacion", "delegacion"),
            ("codigocanal", "canal"),
            ("codigodepartamento", "departamento"),
        ]
        for src, alias_name in dim_cols:
            if _cab_has(src):
                select_parts.append(f"H.{src} AS {alias_name}")
            else:
                select_parts.append(f"NULL AS {alias_name}")

        select_parts.append("COALESCE(H.importeneto, 0) AS importe")

        cab_sql = f"""
            SELECT
                {", ".join(select_parts)}
            FROM datiadb_cabecerapedidocliente H
            WHERE H.codigoempresa = %s
              AND EXTRACT(YEAR FROM H.fechapedido) = %s
              AND H.{cli_col_hdr} = %s
            ORDER BY H.fechapedido DESC, H.numeropedido DESC
            LIMIT 100
        """

        header_rows = []
        with connections[alias].cursor() as cur:
            cur.execute(cab_sql, [empresa, ejercicio, cliente_codigo_analytics])
            if not header_rows:
                cur.execute(
                    f"""
                    SELECT
                        {", ".join(select_parts)}
                    FROM datiadb_cabecerapedidocliente H
                    WHERE H.codigoempresa = %s
                      AND H.{cli_col_hdr} = %s
                    ORDER BY H.fechapedido DESC, H.numeropedido DESC
                    LIMIT 100
                    """,
                    [empresa, cliente_codigo_analytics],
                )
                header_rows = cur.fetchall()

        orders_rows = []
        order_numbers = []
        for row in header_rows:
            numero = row[0]
            serie = row[1]
            fecha = row[2]
            fecha_entrega = row[3]
            proyecto = row[4]
            seccion = row[5]
            delegacion = row[6]
            canal = row[7]
            departamento = row[8]
            importe_val = row[9]
            order_numbers.append(numero)
            documento = f"{serie}-{numero}" if serie else str(numero)
            orders_rows.append(
                {
                    "numero": numero,
                    "documento": documento,
                    "fecha": fecha.strftime("%d-%m-%Y") if hasattr(fecha, "strftime") and fecha is not None else None,
                    "fecha_entrega": fecha_entrega.strftime("%d-%m-%Y") if hasattr(fecha_entrega, "strftime") and fecha_entrega is not None else None,
                    "proyecto": proyecto,
                    "seccion": seccion,
                    "delegacion": delegacion,
                    "canal": canal,
                    "departamento": departamento,
                    "importe": float(importe_val or 0.0),
                    "lineas": [],
                }
            )

        # Líneas de pedido: detalle por artículo, agrupado por número de pedido
        lines_by_order = {}
        fallback_lines_by_order = {}
        if order_numbers:
            try:
                uni_col = "unidades" if _lin_has("unidades") else ("unidadespedidas" if _lin_has("unidadespedidas") else ("cantidad" if _lin_has("cantidad") else None))
                if not uni_col:
                    uni_col = "0"
                orden_col = "orden" if _lin_has("orden") else ("partida" if _lin_has("partida") else None)
                unidades_expr = f'COALESCE(L.{uni_col}, 0)' if uni_col != "0" else "0"
                where_cli = f'H.{cli_col_hdr} = %s'
                with connections[alias].cursor() as cur3:
                    lines_sql = f"""
                        SELECT
                            L.numeropedido AS numero,
                            H.seriepedido AS serie,
                            COALESCE(L.codigoarticulo, '') AS articulo,
                            COALESCE(da.descripcion, CAST(L.codigoarticulo AS TEXT), '') AS descripcion,
                            {unidades_expr} AS unidades,
                            COALESCE(L.precio, 0) AS precio_unitario,
                            COALESCE(L.importeneto, 0) AS importe,
                            COALESCE(L.importecoste, 0) AS coste
                        FROM datiadb_lineaspedidocliente L
                        JOIN datiadb_cabecerapedidocliente H
                          ON L.codigoempresa = H.codigoempresa
                         AND L.seriepedido = H.seriepedido
                         AND L.numeropedido = H.numeropedido
                        LEFT JOIN datia_articulos da
                          ON da.empresa = L.codigoempresa AND da.articulo = L.codigoarticulo
                        WHERE H.codigoempresa = %s
                          AND EXTRACT(YEAR FROM H.fechapedido) = %s
                          AND {where_cli}
                        ORDER BY H.fechapedido DESC, H.numeropedido DESC
                    """
                    cur3.execute(lines_sql, [empresa, ejercicio, cliente_codigo_analytics])
                    line_rows = cur3.fetchall()

                for ln in line_rows:
                    num = ln[0]
                    serie = ln[1]
                    key = f"{serie}-{num}" if serie else str(num)
                    lines_by_order.setdefault(key, []).append(
                        {
                            "articulo": ln[2],
                            "descripcion": ln[3],
                            "unidades": float(ln[4] or 0.0),
                            "precio_unitario": float(ln[5] or 0.0),
                            "importe": float(ln[6] or 0.0),
                            "coste": float(ln[7] or 0.0),
                        }
                    )
            except Exception as e:
                import logging

                logging.getLogger("datia.etl").error("Error loading cliente order lines: %s", e)

        # Albaranes: cabecera + líneas (árbol) y fallback para líneas de pedido
        with connections[alias].cursor() as cur2:
            cur2.execute(
                """
                WITH hdr AS (
                    SELECT
                        H.seriealbaran AS serie,
                        H.numeroalbaran AS numero,
                        H.fechaalbaran AS fecha
                    FROM datiadb_cabeceraalbarancliente H
                    WHERE H.codigoempresa = %s
                      AND H.ejercicioalbaran = %s
                      AND H.codigocliente = %s
                    ORDER BY H.fechaalbaran DESC, H.seriealbaran DESC, H.numeroalbaran DESC
                    LIMIT 60
                )
                SELECT
                    hdr.numero AS numero,
                    hdr.serie AS serie,
                    hdr.fecha AS fecha,
                    COALESCE(L.codigoarticulo, '') AS articulo,
                    COALESCE(da.descripcion, CAST(L.codigoarticulo AS TEXT), '') AS descripcion,
                    CASE
                      WHEN COALESCE(L.precio, 0) <> 0 THEN (COALESCE(L.importeneto, 0) / NULLIF(L.precio, 0))
                      ELSE 0
                    END AS unidades,
                    COALESCE(L.precio, 0) AS precio_unitario,
                    COALESCE(L.importeneto, 0) AS importe,
                    COALESCE(L.importecoste, 0) AS coste,
                    L.seriepedido AS serie_pedido,
                    L.numeropedido AS numero_pedido
                FROM hdr
                LEFT JOIN datiadb_lineasalbarancliente L
                  ON L.codigoempresa = %s
                 AND L.ejercicioalbaran = %s
                 AND L.seriealbaran = hdr.serie
                 AND L.numeroalbaran = hdr.numero
                LEFT JOIN datia_articulos da
                  ON da.empresa = L.codigoempresa AND da.articulo = L.codigoarticulo
                ORDER BY hdr.fecha DESC, hdr.serie DESC, hdr.numero DESC
                """,
                [empresa, ejercicio, cliente_codigo_analytics, empresa, ejercicio],
            )
            deliveries_map = {}
            deliveries_order = []
            for row in cur2.fetchall():
                numero_alb = row[0]
                serie_alb = row[1]
                fecha_alb = row[2]
                articulo = row[3]
                descripcion = row[4]
                unidades = float(row[5] or 0.0)
                precio_unitario = float(row[6] or 0.0)
                importe = float(row[7] or 0.0)
                coste = float(row[8] or 0.0)
                margen = float(importe - coste)
                margen_pct = float((margen / importe) * 100.0) if float(importe or 0.0) != 0.0 else 0.0
                serie_pedido_ref = row[9]
                numero_pedido_ref = row[10]

                documento = f"{serie_alb}-{numero_alb}" if serie_alb else str(numero_alb)
                key_alb = documento
                if key_alb not in deliveries_map:
                    deliveries_map[key_alb] = {
                        "numero": numero_alb,
                        "documento": documento,
                        "fecha": fecha_alb.strftime("%d-%m-%Y") if hasattr(fecha_alb, "strftime") and fecha_alb is not None else None,
                        "importe_total": 0.0,
                        "coste_total": 0.0,
                        "margen_total": 0.0,
                        "margen_total_pct": 0.0,
                        "lineas_count": 0,
                        "lineas": [],
                    }
                    deliveries_order.append(key_alb)

                if articulo is not None and str(articulo).strip() != "":
                    deliveries_map[key_alb]["lineas"].append(
                        {
                            "articulo": articulo,
                            "descripcion": descripcion,
                            "unidades": unidades,
                            "precio_unitario": precio_unitario,
                            "importe": importe,
                            "coste": coste,
                            "margen": margen,
                            "margen_pct": margen_pct,
                        }
                    )
                    deliveries_map[key_alb]["importe_total"] += float(importe or 0.0)
                    deliveries_map[key_alb]["coste_total"] += float(coste or 0.0)
                    deliveries_map[key_alb]["margen_total"] = float(deliveries_map[key_alb]["importe_total"] - deliveries_map[key_alb]["coste_total"])
                    deliveries_map[key_alb]["margen_total_pct"] = float((deliveries_map[key_alb]["margen_total"] / deliveries_map[key_alb]["importe_total"]) * 100.0) if float(deliveries_map[key_alb]["importe_total"] or 0.0) != 0.0 else 0.0
                    deliveries_map[key_alb]["lineas_count"] += 1

                    if numero_pedido_ref is not None:
                        key = f"{serie_pedido_ref}-{numero_pedido_ref}" if serie_pedido_ref else str(numero_pedido_ref)
                        fallback_lines_by_order.setdefault(key, []).append(
                            {
                                "articulo": articulo,
                                "descripcion": descripcion,
                                "unidades": unidades,
                                "precio_unitario": precio_unitario,
                                "importe": importe,
                                "coste": coste,
                            }
                        )

            deliveries_rows = [deliveries_map[k] for k in deliveries_order]

        if not orders_rows:
            try:
                with connections[alias].cursor() as cur4:
                    cur4.execute(
                        """
                        SELECT
                            L.seriepedido AS serie,
                            L.numeropedido AS numero,
                            MIN(H.fechaalbaran) AS fecha,
                            MAX(H.codigoproyecto) AS proyecto,
                            MAX(H.codigoseccion) AS seccion,
                            NULL AS delegacion,
                            MAX(H.codigocanal) AS canal,
                            MAX(H.codigodepartamento) AS departamento,
                            COALESCE(SUM(L.importeneto), 0) AS importe
                        FROM datiadb_lineasalbarancliente L
                        JOIN datiadb_cabeceraalbarancliente H
                          ON L.codigoempresa = H.codigoempresa
                         AND L.ejercicioalbaran = H.ejercicioalbaran
                         AND L.seriealbaran = H.seriealbaran
                         AND L.numeroalbaran = H.numeroalbaran
                        WHERE H.codigoempresa = %s
                          AND H.ejercicioalbaran = %s
                          AND H.codigocliente = %s
                          AND L.numeropedido IS NOT NULL
                        GROUP BY L.seriepedido, L.numeropedido
                        ORDER BY fecha DESC, numero DESC
                        LIMIT 100
                        """,
                        [empresa, ejercicio, cliente_codigo_analytics],
                    )
                    derived = cur4.fetchall()
                for r in derived:
                    serie, numero, fecha, proyecto, seccion, delegacion, canal, departamento, importe_val = r
                    documento = f"{serie}-{numero}" if serie else str(numero)
                    orders_rows.append(
                        {
                            "numero": numero,
                            "documento": documento,
                            "fecha": fecha.strftime("%d-%m-%Y") if hasattr(fecha, "strftime") and fecha is not None else None,
                            "fecha_entrega": None,
                            "proyecto": proyecto,
                            "seccion": seccion,
                            "delegacion": delegacion,
                            "canal": canal,
                            "departamento": departamento,
                            "importe": float(importe_val or 0.0),
                            "lineas": [],
                        }
                    )
            except Exception as e:
                import logging

                logging.getLogger("datia.etl").error("Error deriving cliente orders from deliveries: %s", e)

        # Aplicar líneas a cada pedido: primero líneas propias, luego fallback por albaranes
        for o in orders_rows:
            key = o.get("documento") or str(o.get("numero") or "")
            lines = lines_by_order.get(key) if lines_by_order else []
            if not lines:
                lines = fallback_lines_by_order.get(key, [])
            o["lineas"] = lines
    except Exception as e:
        import logging

        logging.getLogger("datia.etl").error("Error loading cliente docs (orders/deliveries): %s", e)
        orders_rows = []
        deliveries_rows = []

    # Top artículos por cliente usando líneas de albarán (independiente de si hay error en pedidos)
    try:
        with connections[alias].cursor() as cur3:
            cur3.execute(
                """
                SELECT
                      L.codigoarticulo,
                      COALESCE(MAX(da.descripcion), CAST(L.codigoarticulo AS TEXT), '') AS descripcion,
                      SUM(L.importeneto) AS ventas
                FROM datiadb_lineasalbarancliente L
                JOIN datiadb_cabeceraalbarancliente H
                  ON L.codigoempresa = H.codigoempresa
                 AND L.ejercicioalbaran = H.ejercicioalbaran
                 AND L.seriealbaran = H.seriealbaran
                 AND L.numeroalbaran = H.numeroalbaran
                LEFT JOIN datia_articulos da
                  ON da.empresa = L.codigoempresa AND da.articulo = L.codigoarticulo
                WHERE H.codigoempresa = %s
                  AND H.ejercicioalbaran = %s
                  AND H.codigocliente = %s
                GROUP BY L.codigoarticulo
                ORDER BY ventas DESC
                LIMIT 20
                """,
                [empresa, ejercicio, cliente_codigo_analytics],
            )
            top_articulos = [
                {
                    "codigo": row[0],
                    "descripcion": row[1],
                    "ventas": float(row[2] or 0.0),
                }
                for row in cur3.fetchall()
            ]
    except Exception as e:
        import logging

        logging.getLogger("datia.etl").error("Error loading cliente top articles: %s", e)
        top_articulos = []

    cliente_nombre = None
    if base and base.nombre:
        cliente_nombre = base.nombre
    elif nombre_cli:
        cliente_nombre = nombre_cli
    if not cliente_nombre:
        cliente_nombre = base.cliente if base else codigo
    cliente_codigo = base.cliente if base else codigo

    comparison_heatmap = None
    comparison_scatter = None
    try:
        all_qs = MetricsTotalesEmpresaEjercicioCliente.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        )
        comp_rows = all_qs.values("cliente", "nombre").annotate(
            ventas=Sum("importe_neto_total"),
            coste=Sum("importe_coste_total"),
            ops=Sum("albaranes_count"),
        )
        metrics = ["ventas", "ticket_medio", "margen_pct", "operaciones"]
        cliente_vals = [0.0, 0.0, 0.0, 0.0]
        resto_vals = [0.0, 0.0, 0.0, 0.0]
        ventas_list = []
        ops_list = []
        margen_list = []
        for r in comp_rows:
            v = float(r["ventas"] or 0.0)
            c = float(r["coste"] or 0.0)
            o = int(r["ops"] or 0)
            ticket = float(v / o) if o > 0 else 0.0
            margen_pct_loc = float(((v - c) / v) * 100.0) if v > 0 else 0.0
            is_cli = str(r["cliente"]) == str(cliente_codigo)
            if is_cli:
                cliente_vals = [v, ticket, margen_pct_loc, float(o)]
            else:
                resto_vals[0] += v
                resto_vals[1] += ticket
                resto_vals[2] += margen_pct_loc
                resto_vals[3] += float(o)
            ventas_list.append(
                {
                    "codigo": r["cliente"],
                    "nombre": r["nombre"] or r["cliente"],
                    "ventas": v,
                    "operaciones": float(o),
                    "margen_pct": margen_pct_loc,
                    "is_selected": is_cli,
                }
            )
        count_others = max(len(ventas_list) - 1, 1)
        if count_others > 0:
            resto_vals = [
                resto_vals[0],
                resto_vals[1] / count_others,
                resto_vals[2] / count_others,
                resto_vals[3] / count_others,
            ]
        max_vals = [
            max(cliente_vals[0], resto_vals[0], 1.0),
            max(cliente_vals[1], resto_vals[1], 1.0),
            100.0,
            max(cliente_vals[3], resto_vals[3], 1.0),
        ]
        norm_cli = [round(cliente_vals[i] / max_vals[i], 4) for i in range(4)]
        norm_rest = [round(resto_vals[i] / max_vals[i], 4) for i in range(4)]
        comparison_heatmap = {
            "metrics": metrics,
            "cliente": norm_cli,
            "resto": norm_rest,
            "raw": {
                "cliente": cliente_vals,
                "resto": resto_vals,
            },
        }
        comparison_scatter = {
            "ventas_vs_operaciones": ventas_list,
            "ventas_vs_margen": ventas_list,
        }
    except Exception:
        comparison_heatmap = None
        comparison_scatter = None

    risk_data = None
    try:
        from datia.services.financial_service import FinancialService

        fsvc = FinancialService()
        risk_res = fsvc.get_cartera_importe_codes(empresa, ejercicio, [cliente_codigo])
        risk_map = risk_res.get("map", {}) if isinstance(risk_res, dict) else {}
        pendiente = float(risk_map.get(str(cliente_codigo), 0.0) or 0.0)
        risk_data = {"pendiente_cobro": pendiente}
    except Exception:
        risk_data = {"pendiente_cobro": None}

    identity = {
        "codigo": cliente_codigo,
        "nombre": cliente_nombre or "",
        "nombre_fiscal": nombre_fiscal or "",
        "cif_nif": cif_nif or "",
        "fecha_alta": fecha_alta.strftime("%d-%m-%Y") if hasattr(fecha_alta, "strftime") and fecha_alta else None,
        "activo": bool(activo) if activo is not None else None,
        "cod_postal": cod_postal or "",
    }

    return {
        "cliente": {
            "codigo": cliente_codigo,
            "nombre": cliente_nombre or "",
            "ventas_totales": summary["ventas_totales"],
            "operaciones": summary["total_pedidos"],
            "ticket_medio": ticket_medio,
        },
        "identity": identity,
        "risk": risk_data,
        "summary": summary,
        "orders": {"rows": orders_rows},
        "deliveries": {"rows": deliveries_rows},
        "frequency": frequency,
        "charts": {
            "ventas_mensuales": {"labels": labels, "ventas": ventas_mensuales},
            "top_articulos": {"data": top_articulos},
        },
        "comparison": {
            "heatmap": comparison_heatmap,
            "scatter": comparison_scatter,
        },
    }


@router.get("/dashboard/proveedores/overview")
def get_proveedores_dashboard_overview(request, empresa: int, ejercicio: int, q: str = None, limit: int = 100):
    """
    Resumen de proveedores: volumen de compras, concentración y actividad.
    """
    if not _has_dashboard_permission(getattr(request, "user", None), "proveedores"):
        return HttpResponse(status=403)

    from django.db.models import Sum, Count
    from datia.models import (
        MetricsTotalesEmpresaEjercicioProveedor,
        MetricsTotalesEmpresaEjercicioProveedorMes,
        MetricsTotalesEmpresaEjercicioCompraMes,
    )

    base_qs = MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa=empresa, ejercicio=ejercicio)
    if q:
        q_str = str(q).strip()
        if q_str:
            from django.db.models import Q as _Q
            base_qs = base_qs.filter(_Q(proveedor__icontains=q_str) | _Q(nombre__icontains=q_str))

    agg = base_qs.aggregate(
        total_proveedores=Count("proveedor"),
        compras_total=Sum("importe_neto_total"),
        albaranes_total=Sum("albaranes_count"),
    )
    total_proveedores = int(agg.get("total_proveedores") or 0)
    compras_total = float(agg.get("compras_total") or 0.0)
    albaranes_total = int(agg.get("albaranes_total") or 0)

    actividad_qs = MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(
        empresa=empresa, ejercicio=ejercicio
    ).order_by("mes")
    data_map = {m: 0.0 for m in range(1, 13)}
    for row in actividad_qs:
        data_map[row.mes] = float(row.importe_neto_total or 0.0)
    labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    compras_mensuales = [data_map[m] for m in range(1, 13)]

    top_qs = base_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 200))]
    top_proveedores = [
        {
            "codigo": x.proveedor,
            "nombre": x.nombre or x.proveedor,
            "compras": float(x.importe_neto_total or 0.0),
            "albaranes": int(x.albaranes_count or 0),
        }
        for x in top_qs
    ]

    compras_top10 = sum(p["compras"] for p in top_proveedores[:10]) if top_proveedores else 0.0
    concentracion_top10 = float((compras_top10 / compras_total) * 100.0) if compras_total > 0 else 0.0

    tabla_rows = [
        {
            "codigo": x.proveedor,
            "nombre": x.nombre or x.proveedor,
            "compras": float(x.importe_neto_total or 0.0),
            "albaranes": int(x.albaranes_count or 0),
        }
        for x in base_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 500))]
    ]

    return {
        "kpi": {
            "total_proveedores": total_proveedores,
            "compras_totales": compras_total,
            "operaciones_totales": albaranes_total,
            "concentracion_top10": concentracion_top10,
        },
        "charts": {
            "compras_mensuales": {"labels": labels, "compras": compras_mensuales},
            "top_proveedores": {"data": top_proveedores},
        },
        "table": {"rows": tabla_rows},
    }


@router.get("/dashboard/proveedores/detail")
def get_proveedor_dashboard_detail(request, empresa: int, ejercicio: int, codigo: str):
    """
    Detalle de un proveedor: volumen anual y evolución mensual.
    """
    if not _has_dashboard_permission(getattr(request, "user", None), "proveedores"):
        return HttpResponse(status=403)

    from datia.models import MetricsTotalesEmpresaEjercicioProveedor, MetricsTotalesEmpresaEjercicioProveedorMes

    codigo = str(codigo or "").strip()
    if not codigo:
        return {"error": "codigo requerido"}

    base = MetricsTotalesEmpresaEjercicioProveedor.objects.filter(
        empresa=empresa, ejercicio=ejercicio, proveedor=codigo
    ).first()
    if not base:
        return {"error": "proveedor no encontrado"}

    evol_qs = MetricsTotalesEmpresaEjercicioProveedorMes.objects.filter(
        empresa=empresa, ejercicio=ejercicio, proveedor=codigo
    ).order_by("mes")
    data_map = {m: 0.0 for m in range(1, 13)}
    for row in evol_qs:
        data_map[row.mes] = float(row.importe_neto_total or 0.0)
    labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    compras_mensuales = [data_map[m] for m in range(1, 13)]

    return {
        "proveedor": {
            "codigo": base.proveedor,
            "nombre": base.nombre or base.proveedor,
            "compras_totales": float(base.importe_neto_total or 0.0),
            "operaciones": int(base.albaranes_count or 0),
        },
        "charts": {
            "compras_mensuales": {"labels": labels, "compras": compras_mensuales},
        },
    }


@router.get("/dashboard/articulos/overview")
def get_articulos_dashboard_overview(request, empresa: int, ejercicio: int, q: str = None, limit: int = 100):
    """
    Resumen de artículos: ventas, unidades (aprox. por operaciones) y rotación básica.
    """
    if not _has_dashboard_permission(getattr(request, "user", None), "articulos"):
        return HttpResponse(status=403)

    from django.db.models import Sum, Count
    from datia.models import MetricsTotalesEmpresaEjercicioArticulo, MetricsTotalesEmpresaEjercicioArticuloCompra

    base_qs = MetricsTotalesEmpresaEjercicioArticulo.objects.filter(empresa=empresa, ejercicio=ejercicio)
    if q:
        q_str = str(q).strip()
        if q_str:
            from django.db.models import Q as _Q
            base_qs = base_qs.filter(_Q(articulo__icontains=q_str) | _Q(descripcion__icontains=q_str))

    agg = base_qs.aggregate(
        total_articulos=Count("articulo"),
        ventas_total=Sum("importe_neto_total"),
        albaranes_total=Sum("albaranes_count"),
    )
    total_articulos = int(agg.get("total_articulos") or 0)
    ventas_total = float(agg.get("ventas_total") or 0.0)
    albaranes_total = int(agg.get("albaranes_total") or 0)

    compras_qs = MetricsTotalesEmpresaEjercicioArticuloCompra.objects.filter(
        empresa=empresa, ejercicio=ejercicio
    )
    compras_total = float(compras_qs.aggregate(ct=Sum("importe_neto_total")).get("ct") or 0.0)

    top_ventas_qs = base_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 200))]
    top_ventas = [
        {
            "codigo": a.articulo,
            "descripcion": a.descripcion or a.articulo,
            "ventas": float(a.importe_neto_total or 0.0),
        }
        for a in top_ventas_qs
    ]

    top_compra_qs = compras_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 200))]
    top_compras = [
        {
            "codigo": a.articulo,
            "descripcion": a.descripcion or a.articulo,
            "compras": float(a.importe_neto_total or 0.0),
        }
        for a in top_compra_qs
    ]

    tabla_rows = [
        {
            "codigo": a.articulo,
            "descripcion": a.descripcion or a.articulo,
            "ventas": float(a.importe_neto_total or 0.0),
            "operaciones": int(a.albaranes_count or 0),
        }
        for a in base_qs.order_by("-importe_neto_total")[: max(1, min(int(limit or 100), 500))]
    ]

    return {
        "kpi": {
            "total_articulos": total_articulos,
            "ventas_totales": ventas_total,
            "compras_totales": compras_total,
            "operaciones_totales": albaranes_total,
        },
        "charts": {
            "top_ventas": {"data": top_ventas},
            "top_compras": {"data": top_compras},
        },
        "table": {"rows": tabla_rows},
    }


@router.get("/dashboard/articulos/detail")
def get_articulo_dashboard_detail(request, empresa: int, ejercicio: int, codigo: str):
    """
    Detalle de un artículo: ventas y compras agregadas.
    """
    if not _has_dashboard_permission(getattr(request, "user", None), "articulos"):
        return HttpResponse(status=403)

    from django.db.models import Sum
    from datia.models import MetricsTotalesEmpresaEjercicioArticulo, MetricsTotalesEmpresaEjercicioArticuloCompra

    codigo = str(codigo or "").strip()
    if not codigo:
        return {"error": "codigo requerido"}

    venta = MetricsTotalesEmpresaEjercicioArticulo.objects.filter(
        empresa=empresa, ejercicio=ejercicio, articulo=codigo
    ).first()
    compra = MetricsTotalesEmpresaEjercicioArticuloCompra.objects.filter(
        empresa=empresa, ejercicio=ejercicio, articulo=codigo
    ).first()

    if not venta and not compra:
        return {"error": "articulo no encontrado"}

    ventas_totales = float(venta.importe_neto_total or 0.0) if venta else 0.0
    compras_totales = float(compra.importe_neto_total or 0.0) if compra else 0.0
    ops_venta = int(venta.albaranes_count or 0) if venta else 0
    ops_compra = int(compra.albaranes_count or 0) if compra else 0

    return {
        "articulo": {
            "codigo": venta.articulo if venta else compra.articulo,
            "descripcion": (venta.descripcion if venta else compra.descripcion) or (codigo or ""),
        },
        "ventas": {
            "importe": ventas_totales,
            "operaciones": ops_venta,
        },
        "compras": {
            "importe": compras_totales,
            "operaciones": ops_compra,
        },
    }


@router.get("/dashboard/{entity}/export")
def export_entity_dashboard(request, entity: str, empresa: int, ejercicio: int, format: str = "csv"):
    """
    Exporta los datos agregados del dashboard de entidad a CSV (Excel) o HTML imprimible (PDF vía navegador).
    """
    entity = (entity or "").lower()
    scope_map = {
        "clientes": "clientes",
        "proveedores": "proveedores",
        "articulos": "articulos",
    }
    if entity not in scope_map:
        return {"status": "error", "message": "Entidad no soportada"}
    if not _has_dashboard_permission(getattr(request, "user", None), scope_map[entity]):
        return HttpResponse(status=403)

    q = request.GET.get("q", "")
    limit_param = request.GET.get("limit")
    try:
        limit = int(limit_param) if limit_param else 1000
    except Exception:
        limit = 1000

    if entity == "clientes":
        payload = get_clientes_dashboard_overview(request, empresa, ejercicio, q=q, limit=limit)
    elif entity == "proveedores":
        payload = get_proveedores_dashboard_overview(request, empresa, ejercicio, q=q, limit=limit)
    else:
        payload = get_articulos_dashboard_overview(request, empresa, ejercicio, q=q, limit=limit)

    if isinstance(payload, HttpResponse):
        return payload
    if not isinstance(payload, dict):
        return {"status": "error", "message": "Export payload inválido"}

    table = payload.get("table", {}) or {}
    rows = table.get("rows", []) or []

    fmt = (format or "csv").lower()
    if fmt in ("csv", "excel", "xlsx"):
        import io, csv as _csv

        buffer = io.StringIO()
        writer = _csv.writer(buffer)
        if entity == "clientes":
            writer.writerow(["Codigo", "Nombre", "Ventas", "Operaciones", "TicketMedio"])
            for r in rows:
                writer.writerow([
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    f"{float(r.get('ventas', 0.0)):.2f}",
                    int(r.get("albaranes", 0) or 0),
                    f"{float(r.get('ticket_medio', 0.0)):.2f}",
                ])
        elif entity == "proveedores":
            writer.writerow(["Codigo", "Nombre", "Compras", "Operaciones"])
            for r in rows:
                writer.writerow([
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    f"{float(r.get('compras', 0.0)):.2f}",
                    int(r.get("albaranes", 0) or 0),
                ])
        else:
            writer.writerow(["Codigo", "Descripcion", "Ventas", "Operaciones"])
            for r in rows:
                writer.writerow([
                    r.get("codigo", ""),
                    r.get("descripcion", ""),
                    f"{float(r.get('ventas', 0.0)):.2f}",
                    int(r.get("operaciones", 0) or 0),
                ])

        resp = HttpResponse(buffer.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{entity}_dashboard_{empresa}_{ejercicio}.csv"'
        return resp

    if fmt == "pdf":
        header_cells = []
        if entity == "clientes":
            header_cells = ["Codigo", "Nombre", "Ventas", "Operaciones", "TicketMedio"]
        elif entity == "proveedores":
            header_cells = ["Codigo", "Nombre", "Compras", "Operaciones"]
        else:
            header_cells = ["Codigo", "Descripcion", "Ventas", "Operaciones"]

        def esc(val):
            return (str(val) or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        body_rows = []
        for r in rows:
            if entity == "clientes":
                vals = [
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    f"{float(r.get('ventas', 0.0)):.2f}",
                    int(r.get("albaranes", 0) or 0),
                    f"{float(r.get('ticket_medio', 0.0)):.2f}",
                ]
            elif entity == "proveedores":
                vals = [
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    f"{float(r.get('compras', 0.0)):.2f}",
                    int(r.get("albaranes", 0) or 0),
                ]
            else:
                vals = [
                    r.get("codigo", ""),
                    r.get("descripcion", ""),
                    f"{float(r.get('ventas', 0.0)):.2f}",
                    int(r.get("operaciones", 0) or 0),
                ]
            tds = "".join(f"<td>{esc(v)}</td>" for v in vals)
            body_rows.append(f"<tr>{tds}</tr>")

        head_html = "".join(f"<th>{esc(h)}</th>" for h in header_cells)
        body_html = "".join(body_rows)
        title = f"Dashboard {entity.capitalize()} {empresa} {ejercicio}"
        html = f"""
        <h3>{esc(title)}</h3>
        <table border="1" cellpadding="6" cellspacing="0">
        <thead><tr>{head_html}</tr></thead>
        <tbody>{body_html}</tbody>
        </table>
        """
        try:
            from datia.services.pdf_service import PDFService

            pdf_bytes = PDFService.generate_pdf_from_html_fpdf(
                html_content=html,
                title=title,
                empresa_id=empresa,
                ejercicio=ejercicio,
            )
            if pdf_bytes:
                resp = HttpResponse(pdf_bytes, content_type="application/pdf")
                resp["Content-Disposition"] = f'attachment; filename="{entity}_dashboard_{empresa}_{ejercicio}.pdf"'
                return resp
        except Exception as e:
            import logging

            logging.getLogger("datia.pdf").error("Error exportando dashboard %s a PDF: %s", entity, e)

        return HttpResponse(html, content_type="text/html")

    return {"status": "error", "message": "Formato no soportado"}

# ... (Existing Functions) ...

def _get_top_zonas_compra(empresa, ejercicio, limit=5):
    """
    Top Zonas de compras, calculado directamente desde datiadb_cabeceraalbaranproveedor
    y datia_proveedores, agregando por código postal del proveedor.
    """
    from django.db import connections
    conn = connections["analytics"]
    cur = conn.cursor()
    sql = """
        SELECT p.cod_postal, COALESCE(p.nombre, ''), SUM(c.importeliquido) AS neto
        FROM datiadb_cabeceraalbaranproveedor c
        JOIN datia_proveedores p
          ON p.empresa = c.codigoempresa
         AND p.proveedor = c.id_proveedor
        WHERE c.codigoempresa = %s
          AND c.ejercicio = %s
          AND p.cod_postal IS NOT NULL
        GROUP BY p.cod_postal, p.nombre
        ORDER BY neto DESC
        LIMIT %s
    """
    cur.execute(sql, [empresa, ejercicio, limit])
    rows = cur.fetchall()
    data = [
        {
            "nombre": (r[0] or "").strip() or (r[1] or ""),
            "neto": float(r[2] or 0.0),
            "code": r[0],
        }
        for r in rows
    ]
    return {"title": "Top Zonas Compras (Provincias)", "data": {"data": data}}

def _get_ventas_resumen(empresa, ejercicio):
    repo = RepositoryFactory.get_totals_repository()
    obj = repo.get_by_empresa_ejercicio(empresa, ejercicio)
    
    if not obj:
        return {
            "title": "Ventas Resumen", 
            "data": {
                "neto": 0,
                "coste": 0,
                "margen": 0,
                "albaranes": 0
            }
        }
        
    neto = float(obj.importe_neto_total)
    coste = float(obj.importe_coste_total)
    margen = ((neto - coste) / neto * 100) if neto > 0 else 0
    albaranes = obj.albaranes_count or 0
    
    return {
        "title": "Ventas Resumen",
        "data": {
            "neto": neto,
            "coste": coste,
            "margen": round(float(margen), 2),
            "albaranes": albaranes
        }
    }

def _get_compras_resumen(empresa, ejercicio):
    from datia.models import MetricsTotalesEmpresaEjercicioCompra
    obj = MetricsTotalesEmpresaEjercicioCompra.objects.filter(empresa=empresa, ejercicio=ejercicio).first()
    
    if not obj:
        return {
            "title": "Compras Resumen", 
            "data": {"neto": 0, "coste": 0, "margen": 0, "albaranes": 0}
        }
        
    # In Purchases: "Neto" is what we pay (Cost for company). 
    # Usually we don't calculate margin here unless against standard cost.
    # We will just return the totals.
    neto = float(obj.importe_neto_total)
    albaranes = obj.albaranes_count or 0
    
    return {
        "title": "Compras Resumen",
        "data": {
            "neto": neto,
            "coste": 0, # Not applicable in simple purchase view
            "margen": 0,
            "albaranes": albaranes
        }
    }

def _get_top_clientes(empresa, ejercicio, limit=5):
    from datia.models import MetricsTotalesEmpresaEjercicioCliente
    qs = MetricsTotalesEmpresaEjercicioCliente.objects.filter(empresa=empresa, ejercicio=ejercicio).order_by('-importe_neto_total')[:limit]
    
    data = [
        {"nombre": x.nombre or x.cliente, "neto": float(x.importe_neto_total), "code": x.cliente} 
        for x in qs
    ]
    return {"title": "Top Clientes", "data": {"data": data}}

def _get_top_proveedores(empresa, ejercicio, limit=5):
    from datia.models import MetricsTotalesEmpresaEjercicioProveedor
    from django.db import connections
    qs = MetricsTotalesEmpresaEjercicioProveedor.objects.filter(
        empresa=empresa, ejercicio=ejercicio
    ).order_by('-importe_neto_total')[:limit]
    data = [
        {
            "nombre": x.nombre or x.proveedor,
            "neto": float(x.importe_neto_total),
            "code": x.proveedor,
        }
        for x in qs
    ]
    if not data:
        conn = connections["analytics"]
        cur = conn.cursor()
        sql = """
            SELECT p.proveedor, COALESCE(p.nombre, ''), SUM(c.importeliquido) AS neto
            FROM datiadb_cabeceraalbaranproveedor c
            JOIN datia_proveedores p
              ON p.empresa = c.codigoempresa
             AND p.proveedor = c.id_proveedor
            WHERE c.codigoempresa = %s
              AND c.ejercicio = %s
            GROUP BY p.proveedor, p.nombre
            ORDER BY neto DESC
            LIMIT %s
        """
        cur.execute(sql, [empresa, ejercicio, limit])
        rows = cur.fetchall()
        data = [
            {
                "nombre": (r[1] or "").strip() or r[0],
                "neto": float(r[2] or 0.0),
                "code": r[0],
            }
            for r in rows
        ]
    return {"title": "Top Proveedores", "data": {"data": data}}

def _get_top_articulos(empresa, ejercicio, limit=5):
    from datia.models import MetricsTotalesEmpresaEjercicioArticulo
    qs = MetricsTotalesEmpresaEjercicioArticulo.objects.filter(empresa=empresa, ejercicio=ejercicio).order_by('-importe_neto_total')[:limit]
    
    data = [
        {"nombre": x.descripcion or x.articulo, "neto": float(x.importe_neto_total), "code": x.articulo} 
        for x in qs
    ]
    return {"title": "Top Artículos", "data": {"data": data}}

def _get_top_articulos_compra(empresa, ejercicio, limit=5):
    from datia.models import MetricsTotalesEmpresaEjercicioArticuloCompra
    from django.db import connections
    qs = MetricsTotalesEmpresaEjercicioArticuloCompra.objects.filter(
        empresa=empresa, ejercicio=ejercicio
    ).order_by('-importe_neto_total')[:limit]

    data = [
        {
            "nombre": x.descripcion or x.articulo,
            "neto": float(x.importe_neto_total),
            "code": x.articulo,
        }
        for x in qs
    ]
    if not data:
        conn = connections["analytics"]
        cur = conn.cursor()
        sql = """
            SELECT l.codigoarticulo,
                   '' AS descripcion,
                   SUM(l.importeneto) AS neto
            FROM datiadb_lineasalbaranproveedor l
            WHERE l.codigoempresa = %s
              AND l.ejercicioalbaran = %s
            GROUP BY l.codigoarticulo
            ORDER BY neto DESC
            LIMIT %s
        """
        cur.execute(sql, [empresa, ejercicio, limit])
        rows = cur.fetchall()
        data = [
            {
                "nombre": r[0] or "Desconocido",
                "neto": float(r[2] or 0.0),
                "code": r[0],
            }
            for r in rows
        ]
    return {"title": "Top Artículos (Compra)", "data": {"data": data}}

def _get_actividad_mensual(empresa, ejercicio):
    from datia.models import MetricsTotalesEmpresaEjercicioMes
    qs = MetricsTotalesEmpresaEjercicioMes.objects.filter(empresa=empresa, ejercicio=ejercicio).order_by('mes')
    
    # Pre-fill all months to ensure X-axis continuity
    data_map = {m: {'neto': 0, 'coste': 0} for m in range(1, 13)}
    for x in qs:
        data_map[x.mes]['neto'] = float(x.importe_neto_total)
        data_map[x.mes]['coste'] = float(x.importe_coste_total)

    # Spanish Short Month Names
    month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    labels = month_names
    neto_vals = []
    margen_vals = []
    
    for m in range(1, 13):
        n = data_map[m]['neto']
        c = data_map[m]['coste']
        mg = ((n - c) / n * 100) if n > 0 else 0
        
        neto_vals.append(n)
        margen_vals.append(round(mg, 2))
    
    return {
        "title": "Actividad Mensual", 
        "data": {
            "labels": labels, 
            "neto": neto_vals,
            "margen": margen_vals
        }
    }

def _get_actividad_mensual_compra(empresa, ejercicio):
    from datia.models import MetricsTotalesEmpresaEjercicioCompraMes
    qs = MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa=empresa, ejercicio=ejercicio).order_by('mes')
    
    # Pre-fill all months
    data_map = {m: {'neto': 0} for m in range(1, 13)}
    for x in qs:
        data_map[x.mes]['neto'] = float(x.importe_neto_total)

    month_names = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    
    labels = month_names
    neto_vals = []
    
    for m in range(1, 13):
        n = data_map[m]['neto']
        neto_vals.append(n)
    
    return {
        "title": "Actividad Mensual Compras", 
        "data": {
            "labels": labels, 
            "neto": neto_vals
        }
    }

def _get_mapa_ventas(empresa, ejercicio):
    from datia.models import MetricsTotalesEmpresaEjercicioCodigoPostal
    from django.db.utils import ProgrammingError, OperationalError
    try:
        qs_list = list(MetricsTotalesEmpresaEjercicioCodigoPostal.objects.filter(empresa=empresa, ejercicio=ejercicio))
    except (ProgrammingError, OperationalError):
        return {"title": "Top Zonas (Provincias)", "data": {"data": []}}
    
    # Aggregation by Province (First 2 digits)
    provincias = {}
    # Simple map (expand if needed)
    prov_map = {
        '28': 'Madrid', '08': 'Barcelona', '46': 'Valencia', '41': 'Sevilla', 
        '50': 'Zaragoza', '29': 'Málaga', '30': 'Murcia', '07': 'Baleares',
        '48': 'Bizkaia', '03': 'Alicante', '15': 'Coruña', '36': 'Pontevedra'
    }
    
    for item in qs_list:
        cp = str(item.cod_postal).strip()
        if len(cp) >= 2:
            prefix = cp[:2]
            name = prov_map.get(prefix, f"Prov. {prefix}")
            
            if name not in provincias:
                provincias[name] = 0.0
            provincias[name] += float(item.importe_neto_total)
            
    # Sort and Top 10
    sorted_provs = sorted(provincias.items(), key=lambda x: x[1], reverse=True)[:10]
    
    data = [
        {"nombre": k, "neto": v} for k, v in sorted_provs
    ]
    
    return {"title": "Top Zonas (Provincias)", "data": {"data": data}}



@router.get("/ai/models")
def list_ai_models(request):
    """
    Returns available Ollama models.
    """
    from datia.services.ollama_service import OllamaService
    try:
        svc = OllamaService()
        models = svc.list_models()
        return {"models": models}
    except Exception as e:
        return {"error": str(e), "models": []}

# --- NF-002: Knowledge Repository CRUD ---

@router.get("/knowledge")
def list_knowledge(request):
    """
    Lists all AI Knowledge templates.
    """
    from datia.models import MetricsEmbeddings
    import json
    
    # Filter templates (manual) and learned queries (qa)
    from django.db.models import Q
    qs = MetricsEmbeddings.objects.filter(Q(kind='template') | Q(kind='qa')).order_by('-updated_at')
    
    data = []
    for item in qs:
        meta = item.metadata if isinstance(item.metadata, dict) else {}
        if isinstance(item.metadata, str):
            try:
                meta = json.loads(item.metadata)
            except: 
                meta = {}
                
        data.append({
            "id": item.id,
            "kind": item.kind, # [NEW] Pass kind to frontend
            "key": item.key,
            "text": item.text, # Description
            "sql": meta.get('sql') or meta.get('sql_template') or item.key, # Fallback to key only if both missing
            "scope": meta.get('scope', 'global'),
            "label": meta.get('label', ''),
            "updated_at": item.updated_at
        })
    return data

from ninja import Schema

class KnowledgeInput(Schema):
    id: int = None
    text: str
    sql: str
    scope: str = "global"
    label: str = ""

@router.post("/knowledge/save")
def save_knowledge(request, payload: KnowledgeInput):
    """
    Creates or Updates a Knowledge Item using JSON Body.
    """
    from datia.models import MetricsEmbeddings
    from datia.factories import ServiceFactory
    import uuid
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        svc = ServiceFactory.get_embedding_service()
        
        # 1. Generate Vector
        vector = svc.embed_text(payload.text)
        
        # 2. Metadata
        metadata = {
            "sql": payload.sql,
            "scope": payload.scope,
            "label": payload.label or payload.text[:30]
        }
        
        if payload.id:
            # Update
            item = get_object_or_404(MetricsEmbeddings, id=payload.id)
            item.text = payload.text
            item.vector = vector
            item.metadata = metadata
            item.save()
            return {"status": "updated", "id": item.id}
        else:
            # Create
            key = f"manual_{uuid.uuid4().hex[:8]}"
            MetricsEmbeddings.objects.create(
                kind='template',
                key=key,
                text=payload.text,
                vector=vector,
                metadata=metadata
            )
            return {"status": "created"}
            
    except Exception as e:
        logger.error(f"Error saving knowledge: {e}")
        return {"error": str(e)}

@router.delete("/knowledge/{id}")
def delete_knowledge(request, id: int):
    from datia.models import MetricsEmbeddings
    try:
        MetricsEmbeddings.objects.filter(id=id).delete()
        return {"status": "deleted"}
    except Exception as e:
        return {"error": str(e)}

from django.http import HttpResponse
from django.conf import settings

@router.post("/qa")
def qa_query(request, response: HttpResponse, question: str, empresa: int = 1, ejercicio: int = 2025, training_enabled: bool = False, model: str = None, profundizar: bool = False):
    try:
        svc = ServiceFactory.get_ai_service()
        # --- Context/Memory Logic ---
        # [DISABLED BY USER REQUEST]
        # Each query is treated independently. No dialogue history.
        effective_question = question
        last_query = None
        is_short = False
        
        # Call the AI Service
        # SAFEGUARD: Ensure boolean if Ninja didn't cast it (paranoia check)
        if isinstance(training_enabled, str):
            training_enabled = training_enabled.lower() == 'true'
        
        # [FIX] ISS-035: Increase timeout or catch it specifically
        # Currently the service handles it, but let's be explicit if possible.
        # The AI Service (datia.services.ai_service.py) does the heavy lifting.
        svc_response = svc.generate_answer(effective_question, empresa, ejercicio, training_enabled=training_enabled, model=model, request=request, profundizar=profundizar)
        
        # [NEW] Force Language Cookie if changed
        if svc_response.get('lang') and svc_response.get('action') == 'RELOAD':
             response.set_cookie(settings.LANGUAGE_COOKIE_NAME, svc_response['lang'])

        
        # --- Fallback Logic: Auto-retry previous year if empty ---
        # Enhanced to detect "Zero Data" even if structurally valid (e.g. Card with 0.00€)
        has_real_data = False
        
        # Check Structured Data
        if svc_response.get('data'):
            if isinstance(svc_response['data'], list) and len(svc_response['data']) > 0:
                has_real_data = True
            elif isinstance(svc_response['data'], dict):
                # Check for Card data where valid values > 0
                vals = [float(v) for k,v in svc_response['data'].items() if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit()]
                if any(v > 0 for v in vals):
                    has_real_data = True
                    
        # Check KPIs: un indicador a cero no cuenta como dato del ejercicio
        if svc_response.get('kpis'):
            for kpi in svc_response['kpis']:
                try:
                    if float((kpi or {}).get('value') or 0) > 0:
                        has_real_data = True
                except (TypeError, ValueError):
                    continue


        # Check raw text for "No hay datos" explicit message
        text_implies_empty = 'no hay datos' in svc_response.get('text', '').lower()
        
        fallback_msg = ""
        question_names_year = bool(re.search(r'\b20\d{2}\b', question or ''))
        if ((not has_real_data) or text_implies_empty) and not question_names_year and not svc_response.get('profundizado'):
            prev_year = ejercicio - 1
            response_prev = svc.generate_answer(
                effective_question,
                empresa,
                prev_year,
                training_enabled=training_enabled,
                model=model,
                request=request,
            )
            
            # Use prev year ONLY if it actually has something > 0
            prev_has_data = False
            if response_prev.get('data'):
                 if isinstance(response_prev['data'], list) and len(response_prev['data']) > 0: prev_has_data = True
                 elif isinstance(response_prev['data'], dict):
                      vals = [float(v) for k,v in response_prev['data'].items() if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit()]
                      if any(v > 0 for v in vals): prev_has_data = True
            
            if prev_has_data:
                svc_response = response_prev
                fallback_msg = f" (Mostrando datos de {prev_year} por falta de datos en {ejercicio})"
                svc_response['text'] += fallback_msg

        # Update Memory if successful (and not an error response)

        # Update Memory if successful (and not an error response)
        # We classify partial success as success.
        if svc_response.get('sql'):
            # [DISABLED] Do not save context
            pass 
            # request.session['ai_last_query'] = effective_question
        
        return {
            "answer": svc_response.get('answer') or svc_response.get('text'),
            "sql": svc_response.get('sql'),
            "type": svc_response.get('type', 'text'),
            "suggestions": svc_response.get('suggestions') or [],
            "details": svc_response.get('details'),
            "chart_config": svc_response.get('chart_config'),
            "chart_pareto": svc_response.get('chart_pareto'), # Pass Pareto Chart
            "chart_pareto_clients": svc_response.get('chart_pareto_clients'),
            "chart_pareto_products": svc_response.get('chart_pareto_products'),
            "chart_concentration": svc_response.get('chart_concentration'),
            "chart_concentration_clients": svc_response.get('chart_concentration_clients'),
            "chart_concentration_products": svc_response.get('chart_concentration_products'),
            "table": svc_response.get('table'),
            "data": svc_response.get('data'),
            "kpis": svc_response.get('kpis'), # Critical: Needed for report rendering
            "top_clients": svc_response.get('top_clients'),
            "top_products": svc_response.get('top_products'),
            "action": svc_response.get('action'), # [FIX] Pass action for frontend logic
            "key": svc_response.get('key'), # New RLHF Field
            "profundizado": bool(svc_response.get('profundizado')),
            "query": effective_question, # New RLHF Field
            "source": svc_response.get('source'), # AI Flag for UI Badge
            "debug_context": f"Context used: {last_query}" if is_short else "New context"
        }

    except Exception as e:
        return {"error": str(e)}


class FeedbackInput(Schema):
    query: str
    vote: int
    key: str
    empresa: int = 1
    ejercicio: int = 2025
    answer: str = ""
    sql: str = ""

@router.post("/ai/feedback")
def submit_feedback(request, payload: FeedbackInput):
    """
    Handles RLHF with JSON Body.
    vote: 1 (Good), -1 (Bad).
    """
    from datia.models import MetricsFeedback, MetricsSavedQuery
    from datia.factories import ServiceFactory
    try:
        from datia.services.etl_service import ETLService
        ETLService().ensure_ai_tables()
    except Exception:
        pass
    
    query = payload.query
    vote = payload.vote
    key = payload.key
    empresa = payload.empresa
    ejercicio = payload.ejercicio
    
    # 1. Record Feedback
    if vote == -1:
        MetricsFeedback.objects.create(query=query, rejected_key=key)
        
        # 2. If negative, try to regenerate result excluding this key
        svc = ServiceFactory.get_ai_service()
        try:
             # Force regeneration. The AI Service uses EmbeddingService which now respects the Feedback table.
             # Use VERY LOW threshold to ensure we find an alternative even if weak.
             response = svc.generate_answer(query, empresa, ejercicio, threshold=0.1)
             
             return {
                "status": "retry",
                "new_answer": {
                    "answer": response['text'],
                    "sql": response['sql'],
                    "type": response.get('type', 'text'),
                    "chart_config": response.get('chart_config'),
                    "chart_pareto_clients": response.get('chart_pareto_clients'),
                    "chart_pareto_products": response.get('chart_pareto_products'),
                    "chart_concentration": response.get('chart_concentration'),
                    "kpis": response.get('kpis'),
                    "data": response.get('data'),
                    "query": query,
                    "key": response.get('key'),
                    "lang": response.get('lang', 'es')
                }
             }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    elif vote == 1:
        try:
            MetricsFeedback.objects.create(query=query, rejected_key=key, is_positive=True)
            existing = MetricsSavedQuery.objects.filter(empresa=empresa, ejercicio=ejercicio, query=query).first()
            if not existing:
                MetricsSavedQuery.objects.create(
                    empresa=empresa,
                    ejercicio=ejercicio,
                    query=query,
                    last_answer={
                        "text": payload.answer or "Consulta marcada como correcta.",
                        "sql": payload.sql or "",
                        "key": key,
                        "source": "feedback",
                    }
                )
                return {"status": "saved", "message": "Query saved to history"}
            return {"status": "already_saved", "message": "Query already in history"}
        except Exception as e:
            msg = str(e)
            if "metrics_saved_queries" in msg or "UndefinedTable" in msg:
                return {"status": "error", "message": "No existe la tabla metrics_saved_queries en Postgres. Ejecuta migraciones (manage.py migrate)."}
            return {"status": "error", "message": f"Failed to save: {msg}"}

    return {"status": "ok"}


def _parameterize_sql(sql: str, empresa: int, ejercicio: int) -> str:
    text = sql or ''
    if empresa is not None:
        text = re.sub(rf'(?<!\d){int(empresa)}(?!\d)', '{empresa}', text)
    if ejercicio is not None:
        text = re.sub(rf'(?<!\d){int(ejercicio)}(?!\d)', '{ejercicio}', text)
    return text


class LearnInput(Schema):
    question: str
    sql: str
    analysis: str = ""
    type: str = "table"
    empresa: int = 1
    ejercicio: int = 2025

@router.post("/ai/learn")
def learn_query(request, payload: LearnInput):
    """
    Explicitly saves a learned query to the Vector DB via JSON Body.
    """
    from datia.factories import ServiceFactory
    try:
        try:
            from datia.services.etl_service import ETLService
            ETLService().ensure_ai_tables()
        except Exception:
            pass
        svc = ServiceFactory.get_embedding_service()
        
        question = payload.question
        sql = payload.sql
        analysis = payload.analysis
        type = payload.type
        empresa = payload.empresa
        ejercicio = payload.ejercicio
        
        learned_sql = _parameterize_sql(sql, empresa, ejercicio)
        
        svc.learn_template(
            text=question,
            sql=learned_sql,
            type=type,
            label="Aprendido: " + (analysis[:50] + "..." if analysis else question),
            empresa=empresa,
            ejercicio=ejercicio,
            scope='learned',
        )
        
        # [NEW] Also save to History (MetricsSavedQuery)
        from datia.models import MetricsSavedQuery
        
        # Create a dummy response object for the history
        # We don't have the full data here, but we have the SQL and Intent.
        last_answer = {
            "text": analysis or "Consulta aprendida y guardada.",
            "sql": sql,
            "type": type,
            "source": "glearn"
        }
        
        MetricsSavedQuery.objects.create(
            empresa=empresa,
            ejercicio=ejercicio,
            query=question,
            last_answer=last_answer
        )
        
        return {"status": "learned", "message": "Query saved to Brain and History"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/ai/history")
def get_history(request, empresa: int = 0, ejercicio: int = 2025, scope: str = 'mine'):
    """
    Returns saved queries for the current empresa/ejercicio.
    """
    from datia.models import MetricsSavedQuery
    from django.db.utils import ProgrammingError, OperationalError
    from django.utils import timezone
    from datetime import datetime
    import json
    try:
        from datia.services.etl_service import ETLService
        ETLService().ensure_ai_tables()
    except Exception:
        pass
    
    try:
        queries = list(MetricsSavedQuery.objects.filter(empresa=empresa, ejercicio=ejercicio).order_by('-updated_at'))
    except (ProgrammingError, OperationalError):
        queries = []
    
    result = []
    for q in queries:
        # Ensure last_answer is properly serialized
        last_answer = q.last_answer
        if isinstance(last_answer, str):
            try:
                last_answer = json.loads(last_answer)
            except:
                last_answer = {}
        elif last_answer is None:
            last_answer = {}
        # Visibility filtering based on owner/sharing metadata
        try:
            owner = last_answer.get('owner')
            sharing = last_answer.get('sharing') or {}
            is_public = bool(sharing.get('is_public', False))
            shared_users = sharing.get('users') or []
        except Exception:
            owner = None
            is_public = False
            shared_users = []
        current_user = request.user.username if getattr(request, 'user', None) and request.user.is_authenticated else None
        visible = True
        if scope == 'mine':
            # Legacy items without owner remain visible
            visible = (owner is None) or (current_user and owner == current_user)
        elif scope == 'shared':
            visible = (current_user in shared_users) or (is_public and owner != current_user)
        elif scope == 'public':
            visible = is_public
        elif scope == 'all':
            visible = True if (getattr(request, 'user', None) and request.user.is_staff) else False
        else:
            # Default to mine behavior
            visible = (owner is None) or (current_user and owner == current_user)
        if not visible:
            continue
        result.append({
            "id": q.id,
            "query": q.query,
            "last_answer": last_answer,
            "created_at": q.created_at.isoformat(),
            "updated_at": q.updated_at.isoformat()
        })
    
    return {"history": result}

@router.delete("/ai/history/{query_id}")
def delete_history(request, query_id: int):
    """
    Deletes a saved query from history.
    """
    from datia.models import MetricsSavedQuery
    import json
    
    try:
        query = MetricsSavedQuery.objects.get(id=query_id)
        # Permission: only owner can delete, unless staff
        last_answer = query.last_answer
        if isinstance(last_answer, str):
            try:
                last_answer = json.loads(last_answer)
            except:
                last_answer = {}
        owner = (last_answer or {}).get('owner')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            if user.is_staff or owner is None or owner == user.username:
                query.delete()
                return {"status": "deleted", "id": query_id}
            else:
                return {"status": "error", "message": "Not allowed"}
        # Anonymous – deny
        return {"status": "error", "message": "Authentication required"}
    except MetricsSavedQuery.DoesNotExist:
        return {"status": "error", "message": "Query not found"}


class ConversacionInput(Schema):
    empresa: int
    ejercicio: int
    pregunta: str
    respuesta: Dict[str, Any]
    conversacion_id: int = 0
    reemplazar: bool = False


def _usuario_chat(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return user


def _titulo_consulta(pregunta: str) -> str:
    texto = " ".join((pregunta or "").split())
    return (texto[:177] + "...") if len(texto) > 180 else (texto or "Consulta")


def _norma_pregunta(texto: str) -> str:
    return " ".join((texto or "").split()).casefold()


def _pregunta_guardada(fila) -> str:
    mensajes = fila.mensajes or []
    if mensajes and isinstance(mensajes[0], dict):
        return mensajes[0].get("pregunta") or fila.titulo or ""
    return fila.titulo or ""


def _copias_de_la_pregunta(modelo, user_id, empresa, ejercicio, pregunta):
    clave = _norma_pregunta(pregunta)
    if not clave:
        return []
    return [
        fila for fila in modelo.objects.filter(
            usuario_id=user_id,
            empresa=int(empresa),
            ejercicio=int(ejercicio),
        )
        if _norma_pregunta(_pregunta_guardada(fila)) == clave
    ]


def _dejar_una_copia(modelo, user_id, empresa, ejercicio, pregunta, conservar_id):
    sobran = [
        fila.id for fila in _copias_de_la_pregunta(modelo, user_id, empresa, ejercicio, pregunta)
        if fila.id != conservar_id
    ]
    if sobran:
        modelo.objects.filter(id__in=sobran, usuario_id=user_id).delete()


def _fusionar_consultas_iguales(modelo, user_id, empresa, ejercicio):
    grupos = {}
    for fila in modelo.objects.filter(usuario_id=user_id, empresa=int(empresa), ejercicio=int(ejercicio)):
        grupos.setdefault(_norma_pregunta(_pregunta_guardada(fila)), []).append(fila)
    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        grupo.sort(key=lambda fila: fila.actualizado_at, reverse=True)
        modelo.objects.filter(
            id__in=[fila.id for fila in grupo[1:]],
            usuario_id=user_id,
        ).delete()


@router.get("/ai/conversaciones")
def listar_conversaciones(request, empresa: int = 0, ejercicio: int = 0):
    from datia.models import ConsultaConversacion

    user = _usuario_chat(request)
    if not user:
        return {"conversaciones": []}
    _fusionar_consultas_iguales(ConsultaConversacion, user.id, empresa, ejercicio)
    filas = ConsultaConversacion.objects.filter(
        usuario_id=user.id,
        empresa=int(empresa),
        ejercicio=int(ejercicio),
    )
    return {
        "conversaciones": [
            {
                "id": fila.id,
                "titulo": fila.titulo,
                "actualizado_at": fila.actualizado_at.isoformat(),
                "mensajes": len(fila.mensajes or []),
            }
            for fila in filas
        ]
    }


@router.get("/ai/conversaciones/{conversacion_id}")
def abrir_conversacion(request, conversacion_id: int):
    from datia.models import ConsultaConversacion

    user = _usuario_chat(request)
    if not user:
        return {"status": "error", "message": "Authentication required"}
    try:
        fila = ConsultaConversacion.objects.get(id=conversacion_id, usuario_id=user.id)
    except ConsultaConversacion.DoesNotExist:
        return {"status": "error", "message": "No encontrada"}
    return {
        "id": fila.id,
        "titulo": fila.titulo,
        "empresa": fila.empresa,
        "ejercicio": fila.ejercicio,
        "mensajes": fila.mensajes or [],
    }


@router.post("/ai/conversaciones")
def guardar_conversacion(request, payload: ConversacionInput):
    from datia.models import ConsultaConversacion
    from django.utils import timezone

    user = _usuario_chat(request)
    if not user:
        return {"status": "error", "message": "Authentication required"}
    pregunta = (payload.pregunta or "").strip()
    if not pregunta:
        return {"status": "error", "message": "Consulta vacía"}
    mensaje = {
        "pregunta": pregunta,
        "respuesta": payload.respuesta or {},
        "ts": timezone.now().isoformat(),
    }
    empresa = int(payload.empresa)
    ejercicio = int(payload.ejercicio)
    iguales = _copias_de_la_pregunta(ConsultaConversacion, user.id, empresa, ejercicio, pregunta)
    fila = None
    if payload.conversacion_id:
        fila = ConsultaConversacion.objects.filter(
            id=payload.conversacion_id,
            usuario_id=user.id,
        ).first()
    if fila is None and iguales:
        fila = iguales[0]
    if fila is None:
        fila = ConsultaConversacion.objects.create(
            usuario_id=user.id,
            empresa=empresa,
            ejercicio=ejercicio,
            titulo=_titulo_consulta(pregunta),
            mensajes=[mensaje],
        )
    elif payload.reemplazar or iguales:
        fila.mensajes = [mensaje]
        fila.titulo = _titulo_consulta(pregunta)
        fila.empresa = empresa
        fila.ejercicio = ejercicio
        fila.save(update_fields=['mensajes', 'titulo', 'empresa', 'ejercicio', 'actualizado_at'])
    else:
        mensajes = list(fila.mensajes or [])
        mensajes.append(mensaje)
        fila.mensajes = mensajes[-40:]
        fila.save(update_fields=['mensajes', 'actualizado_at'])
    _dejar_una_copia(ConsultaConversacion, user.id, empresa, ejercicio, pregunta, fila.id)
    return {"status": "saved", "id": fila.id, "titulo": fila.titulo}


@router.delete("/ai/conversaciones/{conversacion_id}")
def borrar_conversacion(request, conversacion_id: int):
    from datia.models import ConsultaConversacion

    user = _usuario_chat(request)
    if not user:
        return {"status": "error", "message": "Authentication required"}
    borradas, _ = ConsultaConversacion.objects.filter(
        id=conversacion_id,
        usuario_id=user.id,
    ).delete()
    if not borradas:
        return {"status": "error", "message": "No encontrada"}
    return {"status": "deleted", "id": conversacion_id}


@router.post("/ai/history/{query_id}/refresh")
def refresh_history(request, query_id: int):
    """
    Recalculates a saved query with fresh data.
    """
    from datia.models import MetricsSavedQuery
    from datia.factories import ServiceFactory
    import json
    
    try:
        saved_query = MetricsSavedQuery.objects.get(id=query_id)
        svc = ServiceFactory.get_ai_service()
        
        # Detect AI Report vs QA saved query
        last_answer = saved_query.last_answer
        if isinstance(last_answer, str):
            try:
                last_answer = json.loads(last_answer)
            except:
                last_answer = {}
        
        is_ai_report = False
        try:
            if isinstance(saved_query.query, str) and saved_query.query.startswith("AI_REPORT:"):
                is_ai_report = True
            elif isinstance(last_answer, dict) and last_answer.get("type") == "ai_report":
                is_ai_report = True
        except:
            is_ai_report = False
        
        if is_ai_report:
            # Parse kind and origin from query if available
            kind = 'ventas'
            origin = None
            parts = saved_query.query.split(":") if isinstance(saved_query.query, str) else []
            if len(parts) >= 2 and parts[0] == "AI_REPORT":
                kind = parts[1] or (last_answer.get("kind") or "ventas")
                origin = parts[2] if len(parts) >= 3 else None
            
            if not origin:
                origin = last_answer.get("origin") or "ia-general"
            
            # Respect previously used model if not fallback
            model_used = last_answer.get("model_used")
            if model_used == "fallback":
                model_used = None
            
            result = svc.generate_strategic_report(
                empresa=saved_query.empresa,
                ejercicio=saved_query.ejercicio,
                kind=kind,
                model=model_used
            )
            
            # Update saved answer with structured ai_report payload
            saved_query.last_answer = {
                "type": "ai_report",
                "html": result.get("html"),
                "origin": origin,
                "kind": kind,
                "empresa": saved_query.empresa,
                "ejercicio": saved_query.ejercicio,
                "model_used": result.get("model_used"),
                "raw_data": result.get("raw_data") or {}
            }
            saved_query.save()
            return {"status": "refreshed", "type": "ai_report"}
        else:
            # Standard QA flow
            response = svc.generate_answer(
                saved_query.query,
                saved_query.empresa,
                saved_query.ejercicio
            )
            # Preserve owner if present
            try:
                prev = saved_query.last_answer if isinstance(saved_query.last_answer, dict) else json.loads(saved_query.last_answer or "{}")
                owner = prev.get('owner')
                if isinstance(response, dict) and owner and 'owner' not in response:
                    response['owner'] = owner
            except Exception:
                pass
            saved_query.last_answer = response
            saved_query.save()
            return {"status": "refreshed", "type": "qa"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/ai/history/{query_id}/share")
def share_history(request, query_id: int):
    """
    Updates sharing metadata (public/users) for a saved query.
    """
    from datia.models import MetricsSavedQuery
    import json
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        is_public = bool(payload.get('is_public', False))
        users = payload.get('users') or []
        users = [str(u).strip() for u in users if str(u).strip()]
        item = MetricsSavedQuery.objects.get(id=query_id)
        last = item.last_answer
        if isinstance(last, str):
            try:
                last = json.loads(last)
            except:
                last = {}
        owner = (last or {}).get('owner')
        # Only owner or staff can share
        if not (request.user and request.user.is_authenticated):
            return {"status": "error", "message": "Authentication required"}
        if not (request.user.is_staff or owner == request.user.username or owner is None):
            return {"status": "error", "message": "Not allowed"}
        # Update sharing metadata
        last = last or {}
        last['sharing'] = {'is_public': is_public, 'users': users}
        # Ensure owner set
        if not last.get('owner') and request.user and request.user.is_authenticated:
            last['owner'] = request.user.username
        item.last_answer = last
        item.save()
        return {"status": "shared", "id": item.id}
    except MetricsSavedQuery.DoesNotExist:
        return {"status": "error", "message": "Query not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Features Management (NF-003 UI Fix) ---

@router.get("/features/")
def list_features(request):
    """
    Lists all tracked features from features.json
    """
    import os, json
    from django.conf import settings
    
    path = os.path.join(settings.BASE_DIR, 'datia/patterns/features.json')
    if not os.path.exists(path):
        return []
        
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

@router.post("/features/save")
def save_features(request, payload: list[dict]):
    """
    Saves features list back to features.json
    """
    import os, json
    from django.conf import settings
    
    path = os.path.join(settings.BASE_DIR, 'datia/patterns/features.json')
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        return {"status": "saved"}
    except Exception as e:
        return {"error": str(e)}        


@router.post("/sync/trigger")
def trigger_sync(request, empresa: int, ejercicio: int):
    # Streaming Response for Real-time Progress
    # The frontend should use EventSource or fetch with body reader.
    from django.http import StreamingHttpResponse
    
    svc = ServiceFactory.get_etl_service()
    
    def event_stream():
        # Iterate over generator and yield bytes
        # FIX ISS-002: Use sync_all_years_for_empresa_generator to sync ALL exercises and Dynamic Tables
        for progress_msg in svc.sync_all_years_for_empresa_generator(empresa):
            yield progress_msg.encode('utf-8')
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    # Set headers to prevent buffering
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no' # For Nginx
    return response

@router.get("/sync/status")
def get_sync_status(request, job_id: str):
    # Deprecated but kept for compatibility
    return {"status": "completed"}

@router.post("/datasource/{datasource_id}/reindex")
def reindex_datasource(request, datasource_id: int):
    """
    Regenerates synthetic queries for a specific datasource.
    """
    from datia.models import DataSource
    from datia.services.synthetic_generator import SyntheticSQLGenerator
    
    try:
        ds = DataSource.objects.get(id=datasource_id)
        generator = SyntheticSQLGenerator()
        
        # Generate
        queries = generator.generate_batch(ds)
        
        # Save
        count = generator.save_batch(queries, ds)
        
        return {"status": "ok", "generated": len(queries), "saved": count}
    except DataSource.DoesNotExist:
        return {"error": "DataSource not found"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/orders/reindex")
def reindex_orders(request):
    """
    Specific endpoint to reindex 'Pedidos' table.
    """
    from datia.models import DataSource
    from datia.services.synthetic_generator import SyntheticSQLGenerator
    
    try:
        # Try to find 'Pedidos' or 'Orders'
        ds = DataSource.objects.filter(name__icontains='pedidos').first()
        if not ds:
            ds = DataSource.objects.filter(name__icontains='orders').first()
            
        if not ds:
            return {"error": "Table 'Pedidos' or 'Orders' not found"}
            
        generator = SyntheticSQLGenerator()
        queries = generator.generate_batch(ds)
        count = generator.save_batch(queries, ds)
        
        return {"status": "ok", "table": ds.name, "generated": len(queries), "saved": count}
    except Exception as e:
        return {"error": str(e)}
class ErpConfigSchema(Schema):
    name: str

@router.get("/config/erp")
def get_erp_config(request):
    """
    Returns the configured ERP name.
    """
    from datia.models import WidgetConfig
    from datia.models.master import GlobalConfig
    try:
        cfg = GlobalConfig.load()
        name = (cfg.erp_name or '').strip()
        if name:
            return {"name": name}
        conf = WidgetConfig.objects.filter(key="config.erp_name").first()
        return {"name": conf.title if conf else ""}
    except Exception as e:
        return {"error": str(e)}

@router.post("/config/erp")
def save_erp_config(request, payload: ErpConfigSchema):
    """
    Saves the ERP name.
    """
    from datia.models import WidgetConfig
    try:
        name = payload.name.strip()
        
        obj, created = WidgetConfig.objects.get_or_create(
            key="config.erp_name",
            defaults={"title": name, "description": "System ERP Integration Name"}
        )
        
        if not created:
            obj.title = name
            obj.save()
            
        return {"status": "saved", "name": name}
    except Exception as e:
        return {"error": str(e)}
