# 15 — Patrón de Sincronización Incremental (ETL MSSQL → Postgres)

## Objetivo
- Definir un proceso incremental que copie solo los documentos modificados en un período definido (por defecto 7 días) desde MSSQL (solo lectura) a Postgres (analytics), y actualice las métricas derivadas optimizando rendimiento.

## Alcance
- Ventas (Albaranes de Cliente): cabeceras y líneas.
- Compras (Albaranes de Proveedor): cabeceras y líneas.
- Financiera (Plan y Acumulados).

## 1. Tablas involucradas
- Origen (MSSQL):
  - Ventas: CabeceraAlbaranCliente, LineasAlbaranCliente, Clientes, Articulos.
  - Compras: CabeceraAlbaranProveedor, LineasAlbaranProveedor, Proveedores, Articulos.
  - Financiera: PlanCuentas, Acumulados.
- Destino (Postgres/analytics):
  - Raw Ventas: datia_raw_cabecera, datia_raw_lineas.
  - Raw Compras: datia_raw_cabecera_compra, datia_raw_lineas_compra.
  - Financiera: datia_financial_plan, datia_financial_acumulados.
  - Métricas Ventas: metrics_totales_empresa_ejercicio, metrics_totales_empresa_ejercicio_mes, metrics_totales_empresa_ejercicio_cliente, metrics_totales_empresa_ejercicio_articulo, metrics_totales_empresa_ejercicio_cliente_mes.
  - Métricas Compras: metrics_totales_empresa_ejercicio_compra, metrics_totales_empresa_ejercicio_compra_mes, metrics_totales_empresa_ejercicio_proveedor, metrics_totales_empresa_ejercicio_articulo_compra, metrics_totales_empresa_ejercicio_proveedor_mes.
- Control/Checkpoint:
  - datia_sync_checkpoints: empresa, ejercicio, tipo (‘ventas’, ‘compras’, ‘financiera’), last_fecha, last_serie, last_numero, updated_at.

## 2. Mecanismo de sincronización incremental
- Ventana por defecto: 7 días. Si no existe checkpoint, cutoff = NOW() − 7 días; si existe, cutoff = last_fecha.
- Campo de control:
  - Fecha de cabecera (C.fecha) en MSSQL como cursor incremental. Si existe un campo “last_update” fiable en origen, puede preferirse; por defecto se usa C.fecha.
- Identificación de cambios:
  - Seleccionar cabeceras donde empresa numérica = ? y ejercicio = ? y fecha ≥ cutoff.
  - Para cada cabecera cambiada, eliminar líneas locales del documento y copiarlas de MSSQL (DELETE + COPY).
- Persistencia de cambios:
  - Cabeceras: INSERT … ON CONFLICT (empresa, ejercicio, serie, numero) DO UPDATE SET ….
  - Líneas: DELETE por documento, y COPY CSV para insertar las líneas actualizadas.
- Métricas:
  - Ventas: agregación desde raw (cabecera+líneas) a metrics_* por niveles: global, mes, cliente, artículo, cliente/mes.
  - Compras: agregación desde raw (cabecera_compra+líneas_compra) a metrics_* compras: global, mes, proveedor, artículo compra, proveedor/mes.
- Checkpoint:
  - Al finalizar, se fija last_fecha = MAX(fecha) de cabeceras procesadas en esta ejecución; updated_at = NOW().

## 3. Flujo del proceso
1) Cargar configuración y leer checkpoint:
   - get_checkpoint(empresa, ejercicio, tipo) → cutoff (last_fecha o NOW() − 7 días).
2) Detectar cabeceras modificadas en MSSQL:
   - SELECT C.* FROM Cabecera… WHERE empresa = ? AND ejercicio = ? AND C.fecha ≥ cutoff.
3) Upsert de cabeceras en Postgres:
   - INSERT … ON CONFLICT (empresa, ejercicio, serie, numero) DO UPDATE SET campos dependientes.
4) Actualizar líneas por documento:
   - DELETE líneas locales del documento.
   - SELECT líneas en MSSQL (JOIN opcional con Artículos para descripción) y COPY a Postgres.
5) Recalcular métricas:
   - Ventas: aggregate_from_local(empresa, ejercicio).
   - Compras: aggregate_purchases_from_local(empresa, ejercicio).
6) Actualizar checkpoint:
   - set_checkpoint(empresa, ejercicio, tipo, last_fecha = MAX(C.fecha)).
7) Manejo de errores:
   - Emisión de pasos de error en el stream de progreso; no bloquea otras empresas/ejericios.

## 4. Detalles técnicos
- Consultas MSSQL (formas simplificadas):
  - Cabeceras cambiadas (Compras):
    - SELECT C.serie, C.numero, C.fecha, C.proveedor, COALESCE(P.nombre, C.nombre_proveedor) AS nombre_proveedor, C.neto, C.con_iva, C.cod_postal
      FROM CabeceraAlbaranProveedor C LEFT JOIN Proveedores P
      ON C.empresa = P.empresa AND C.proveedor = P.proveedor
      WHERE C.empresa = ? AND C.ejercicio = ? AND C.fecha ≥ ?
  - Líneas por documento (Compras):
    - SELECT L.serie, L.numero, L.articulo, COALESCE(AR.descripcion, L.descripcion) AS descripcion,
      L.cantidad, L.neto AS importe_bruto, COALESCE(L.con_iva, 0) AS importe_con_iva, COALESCE(L.coste, 0) AS coste
      FROM LineasAlbaranProveedor L LEFT JOIN Articulos AR
      ON L.empresa = AR.empresa AND L.articulo = AR.articulo
      WHERE L.empresa = ? AND L.ejercicio = ? AND L.serie = ? AND L.numero = ?
- Upserts y COPY:
  - Cabeceras: INSERT … ON CONFLICT … DO UPDATE para sincronizar campos derivados.
  - Líneas: DELETE + COPY por documento para consistencia.
- Endpoints/API:
  - POST /api/etl/incremental/sales?empresa_id={e}&year={y}&days={d}
  - POST /api/etl/incremental/purchases?empresa_id={e}&year={y}&days={d}
  - POST /api/etl/incremental/financial?empresa_id={e}&year={y}
  - POST /api/etl/incremental/cartera?empresa_id={e}&year={y}&days={d}
  - POST /api/etl/incremental/stocks?empresa_id={e}&year={y}&periods={p}
- Comandos gestión:
  - Ventas: datia_sync_incremental.py
  - Compras: datia_sync_incremental_purchases.py
  - Financiera: datia_sync_incremental_financial.py
- Parámetros:
  - empresa (MSSQL numérico: 1, 2, 3, 100, 200).
  - ejercicio (año).
  - days_back (por defecto 7).
  - days (CarteraEfectos incremental, por defecto 90).
  - periods (Existencias incremental, por defecto 2; refresca últimos N periodos 1..12).
  - fast_bulk (optimiza COPY en bloques).
  - sync_type (all|trained|standard) en sincronizador global.

## 5. Garantías de actualización selectiva y rendimiento
- Solo se actualizan documentos con fecha ≥ cutoff (último checkpoint o ventana de 7 días).
- Las líneas se reescriben únicamente para los documentos detectados como cambiados.
- Las métricas se recalculan desde raw consistentes; puede optimizarse por meses afectados.
- El checkpoint asegura idempotencia y evita reprocesos innecesarios en ejecuciones diarias.

## 6. Recomendaciones operativas
- Programar el incremental diario vía job (Windows Task Scheduler/cron Windows) usando los management commands con days_back=7 para el ejercicio actual.
- Registrar logs de progreso en debug_api.txt cuando perf_cfg.log_etl_progress=true.
- Mantener empresa numérica en MSSQL; en Postgres se conserva como texto en las tablas analíticas y de métricas.

