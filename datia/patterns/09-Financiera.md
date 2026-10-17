# 09 - Financiera

## Propósito
- Establecer el patrón funcional y técnico del módulo “Financiera” para la visualización ejecutiva y analítica de KPIs contables (ingresos, gastos, EBITDA, margen), comparativas trimestrales y desglose mensual.
- Garantizar consistencia visual, separación HTML/JS/CSS, cumplimiento i18n, y rendimiento óptimo en entorno Windows con administración Django.

## Alcance
- Resumen Ejecutivo con KPIs principales y gráfico mensual combinado.
- Ratios clave con tarjetas flip y detalle trasero.
- Gráfica P&L y tabla de detalle mensual por niveles.
- Informe Trimestral con comparativa YoY y exportación.
- Sincronización de datos (consulta MSSQL) y cálculos en servicios.

## Arquitectura de Datos
- Origen: MSSQL (solo lectura) para acumulados y plan de cuentas.
- Inteligencia/Entrenamiento: PostgreSQL (IA, embeddings, sincronización).
- Tablas clave: `DatiaAcumuladosConta`, `DatiaPlanCuentas` (finanzas), métricas agregadas para evoluciones mensuales.

## Endpoints
- Snapshot (KPIs): [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L10-L16)
- P&L Report: [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L18-L24)
- Análisis Avanzado (IA): [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L26-L32)
- Detalle Mensual P&L: [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L34-L40)
- Informe Trimestral: [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L42-L48)
- Departamentos (filtro): [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L50-L56)
- Export Trimestral (CSV/PDF): [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L58-L107)
- KPIs Mensuales ejecutivos: [financial_endpoints.py](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/api/financial_endpoints.py#L45-L54)

## Servicios
- Snapshot y ratios: [financial_service.py:get_snapshot](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/services/financial_service.py#L17-L88)
- P&L detalle mensual: [financial_service.py:get_pl_detail](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/services/financial_service.py#L90-L182)
- P&L agregado: [financial_service.py:get_pl_report](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/services/financial_service.py#L184-L218)
- Análisis avanzado: [financial_service.py:get_advanced_analysis](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/services/financial_service.py#L220-L259)
- KPIs mensuales ejecutivos: [financial_service.py:get_monthly_kpis](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/services/financial_service.py#L260-L287)

## Frontend (HTML)
- Secciones principales: [tab_actualidad_financiera.html](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html)
  - Resumen Ejecutivo (KPIs): [tab_actualidad_financiera.html:L25-L54](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L25-L54)
  - Contenedor gráfico ejecutivo debajo: [tab_actualidad_financiera.html:L50-L54](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L50-L54)
  - Ratios Clave: [tab_actualidad_financiera.html:L56-L133](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L56-L133)
  - Gráfica P&L: [tab_actualidad_financiera.html:L135-L144](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L135-L144)
  - Detalle mensual: [tab_actualidad_financiera.html:L146-L179](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L146-L179)
  - Informe Trimestral: [tab_actualidad_financiera.html:L181-L200](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L181-L200)

## Frontend (JS)
- Carga principal: [actualidad_financiera.js](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js)
  - Llamada y render del snapshot: [actualidad_financiera.js:L10-L18](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js#L10-L18)
  - Gráfica P&L: [actualidad_financiera.js:renderPLChart](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js#L807)
  - Gráfico ejecutivo mensual: [actualidad_financiera.js:loadExecutiveChart](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js#L56-L69), [actualidad_financiera.js:renderExecutiveChart](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js#L71-L123)
  - Informe trimestral (chart y cards): [actualidad_financiera.js:renderQuarterlyChart](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js#L615)
  - Detalle mensual (tabla): [actualidad_financiera.js:renderPLDetailTable](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/js/dashboard/actualidad_financiera.js#L764-L788)
  - Tesorería – Desglose máximo automático: al expandir un grupo de nivel 3 (ej. 430), se carga automáticamente el desglose máximo disponible de todas las cuentas hijas y se renderiza en una sola vista (endpoint breakdown_flat).

## Frontend (CSS)
- Estilos generales y KPI row (inline en plantilla): [tab_actualidad_financiera.html:L240-L412](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/templates/datia/components/tab_actualidad_financiera.html#L240-L412)
- Quarterly y variaciones: [dashboard.css:L344-L400](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/css/dashboard.css#L344-L400)
- Contenedor gráfico ejecutivo: [dashboard.css:L506-L511](file:///c:/Users/miguel%20vergara/Desktop/datia/datia/static/css/dashboard.css#L506-L511)

## NEW
1. Desglose máximo automático en Tesorería (implementado): al expandir 43x de nivel 3, el sistema usa breakdown_flat para mostrar todas las subcuentas en una sola carga. Validado con prueba de regresión <1s.

## Gráfico Ejecutivo Mensual (Especificación)
- Formato combinado: barras para Ingresos y Gastos; línea para EBITDA; línea porcentual para Margen EBITDA % (eje derecho).
- Ejes:
  - X: meses del ejercicio (Ene–Dic).
  - Y izquierda: escala monetaria en euros (formateo con Intl.NumberFormat).
  - Y derecha: 0–100%, etiqueta “%”.
- Tooltips: valores exactos con “€” para barras y “%” para margen.
- Leyenda y título: nombres claros, título “Ingresos, Gastos y EBITDA mensual”.
- Colores: azul (#3b82f6) Ingresos; rojo (#ef4444) Gastos; verde (#10b981) EBITDA; amarillo (#fbbf24) Margen %.
- Responsivo e impresión: renderer SVG + `attachResizeObserver`.

## Ratios Clave (Flip Cards)
- Componente flip con frente KPI y dorso de metadatos, siguiendo el patrón de giro 3D.
- Botón de información en esquina superior derecha y botón “Volver” en dorso cuando aplique.
- El botón “Análisis Experto” abre un modal de detalle del ratio con:
  - Listado completo de cuentas que forman el numerador y el denominador.
  - Checkbox por cuenta para incluirla o excluirla del cálculo, manteniendo siempre visible todo el listado.
  - Recalculo del ratio en tiempo real basado solo en las cuentas seleccionadas, mostrando el valor original y el valor con la selección actual.
  - Persistencia de la selección durante la sesión actual (empresa+ejercicio+ratio) mediante almacenamiento en sesión del navegador.
  - Validación para impedir dejar sin cuentas el numerador o el denominador y para evitar denominadores nulos.

## Informe Trimestral
- Cards por Q1–Q4 con métricas (ingresos, gastos, beneficio neto, margen operativo, ticket medio, operaciones, margen negocio).
- Comparativa YoY con variaciones y dif. de margen en puntos.
- Exportación CSV/PDF desde toolbar.

## Reglas y Estándares
- Separación HTML/JS/CSS estricta y código < 500 líneas por bloque.
- i18n con `gettext` para textos en interfaz.
- No iniciar la app ni controlar el navegador sin instrucción explícita.
- Entorno Windows, administración via Django.
- MSSQL solo consulta; IA y entrenamiento en tablas PostgreSQL.

## Performance y Accesibilidad
- Objetivo de carga < 2s para secciones financieras.
- Renderer SVG para calidad en impresión.
- Tipografías y contraste siguiendo tema “Financial Analyst Pro”.

## NEW
1. Gráfico mensual combinado debajo del Resumen Ejecutivo.
2. Informe Trimestral con comparativa interanual y exportación.
3. Tooltips numéricos exactos y leyenda clara.

## REVIEW
1. 00-Reglas Generales (consistencia, separación, límites de tamaño).
2. 12-Arquitectura de Plantillas (estructura y estilos en componentes).
3. 05-Dashboard (layout, drag & drop, preferencias).

## Seguridad
- No exponer ni loguear secretos.
- Validar parámetros en endpoints.

## Verificación
- Revisión visual en tamaños desktop/móvil.
- Validación de datos (12 meses, series completas).
- Sin errores en consola ni referencias rotas.
