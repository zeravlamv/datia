## Sesión iniciada: 2026-01-16 10:33
*   **Deep Analysis & Reporting (NF-027, NF-028)**:
    *   **AnalysisService**: Implementación de motor de análisis estadístico con `numpy`.
        *   **Detección de Anomalías**: Algoritmo Z-Score para identificar meses atípicos en series temporales.
        *   **Tendencias**: Regresión lineal simple para determinar la dirección y pendiente de las ventas.
        *   **Segmentación**: Lógica Pareto (ABC) para clasificación estratégica de clientes y productos.
    *   **ReportHandler**: Integración de "Análisis Estratégico Avanzado" en los Dossiers Ejecutivos generados por IA. Ahora incluye secciones de Anomalías, Tendencias y Recomendaciones automáticas basadas en datos.
    *   **Financial Dashboard**: Integración de "Análisis Estratégico (IA)" directamente en la pestaña Financiera. Visualización en tiempo real de anomalías, tendencias y recomendaciones sin necesidad de generar informes completos.

**Actualización de sesión (11/01/2026)**
*   **Frontend (core.js)**: Silenciamiento ampliado de consola (log/debug/info/warn) y control opcional para errores mediante `datia-silent-errors`.
*   **Financiera (UI)**: Botón “i” visible con mayor contraste y clic garantizado; `pointer-events: none` en gauges ECharts para permitir interacción del widget.
*   **Flip-Card**: Paridad con Ventas; giro 3D uniforme y contenido back detallado (fórmula, significado, análisis y recomendaciones).
*   **Favoritos**: Sin parpadeo inicial de Ventas; sub-pestañas inician ocultas y se restaura la favorita de forma temprana.
*   **P&L**: Formato sin decimales en gráfica y etiquetas; coherencia con `Intl` y estándares del patrón 05-Dashboard.
*   **Balance de Situación (Financiera)**: Eliminados gráficos y tarjetas de ratios en la sección de Balance; se incorpora tabla plana con columnas YoY (Importe Año Anterior y Var %). Los títulos del resumen (Activo/Pasivo/Patrimonio) son clicables para cargar el detalle correspondiente. Nuevo endpoint utilizado en frontend: `/api/financial/balance/table`.

**Actualización de sesión (12/01/2026)**
*   **Financiera – Análisis Estratégico (IA)**: Revisión visual y de contenido del widget.
    *   Diseño: mayor separación y jerarquía visual; tarjetas con títulos, subtítulos y métricas etiquetadas.
    *   Formato: todos los valores sin decimales (€, %) usando `Intl.NumberFormat` con `maximumFractionDigits: 0`.
    *   Contenido: incorpora “Intensidad de tendencia” (Alta/Media/Baja), “Severidad máx (Z)” y “Impacto acumulado” en anomalías, y recomendaciones saneadas y concisas.
*   **Frontend (CSS/JS)**: nuevas clases reutilizables para el grid y tarjetas del análisis, y refactor del renderizado frontal/dorso sin mezclar responsabilidades HTML/CSS/JS.

**Actualización de sesión (13/01/2026)**
*   **Actualidad Móvil (Compras/Financiera)**:
    *   Corrección de carga de Compras en móvil: se sustituye la llamada `loadComprasSnapshot()` por `loadSnapshotCompras()` en `mobile_manager.js` para inicializar correctamente los datos de compras en runtime.
    *   Asegurada la disponibilidad de datos financieros en móvil: fallback de fetch a `/api/financial/snapshot` cuando no existe `window.cachedFinancialData`.
*   **Separación CSS/JS/HTML (Patrón 00-Reglas Generales)**:
    *   Extracción del bloque `<style>` del builder móvil a un nuevo fichero `static/css/mobile_builder.css`.
    *   Enlace del CSS desde `tab_actualidad_movil.html` para mantener separación y facilitar mantenimiento.
*   **Compatibilidad móvil y renderizado**:
    *   Verificada detección robusta de móvil (ancho, touch y user‑agent) y alternancia entre vista estándar/móvil según modo.
    *   Revisión de mapeos de widgets de Compras y Financieros en drag & drop y runtime.
*   **Permisos y acceso**:
    *   Confirmada persistencia de configuración móvil por empresa mediante `GET/POST /api/mobile/config` (modelo `MobileConfig`).
*   **Pruebas**:
    *   Matriz de pruebas definida para iOS Safari, Android Chrome y navegadores móviles habituales, con verificación de widgets (Compras y Financieros), gráficos y caché local.

**Actualización de sesión (15/01/2026)**
*   **Campos Estándar (NF‑011)**:
    *   Política de semilla/patrón aplicada: todas las altas desde UI se crean con `fix_type=True` y aparecen marcadas como “System”. Impacta en protección de edición/borrado (requiere `force=true`).
    *   Enriquecimiento de mapeo intacto: se inyectan `business_name`, `description` y rol sugerido desde StandardField.
*   **Catálogo (Landing)**:
    *   Añadidas tarjetas en `catalog.html` para el modelo `StandardField` y endpoints relacionados:
      *   `GET /api/semantic/standard-fields` (lista con `fix_type`).
      *   `POST /api/semantic/standard-fields/save` (altas como semilla).
      *   `POST /api/semantic/standard-fields/delete` (requiere `force=true` si es “System”).
*   **Limpieza de sesión**:
    *   Eliminados archivos auxiliares no esenciales: `AI_ANALYSIS.md`, `AI_SYSTEM_AUDIT.md`, `DATIA_prompt.md`, `check_db_content.py`, `datia.log`. Se preserva `PROJECT_CONTEXT.md`.
**Actualización de sesión (16/01/2026)**
*   **Visualización de Evolución (Gastos/Ingresos)**: 
    *   **Script de Generación**: `scripts/gastos_ingresos_visualizacion.py` adaptado para Sage 200/Murano usando `AcumuladosConta`. Genera comparativa mensual (últimos 24 meses) progresiva.
    *   **Animación**: Implementado fallback automático a GIF animado ante la ausencia de `ffmpeg` en el entorno, garantizando la experiencia visual solicitada.
    *   **Frontend**: Nueva sub-pestaña **"Evolución"** en la sección Actualidad. Plantilla `tab_actualidad_evolucion.html` con soporte dinámico para video y GIF.
*   **Limpieza de sesión**:
    *   Eliminados archivos de depuración: `debug_columns.py`, `debug_script.py`, y otros auxiliares.
    *   Actualizado `walkthrough.md` con los detalles técnicos de la resolución.
*   **Gestión de Visibilidad (Regla 8)**:
    *   **Política de Sistema**: Implementada la Regla 8 en `00-Reglas Generales.md`. Toda nueva pestaña debe ser gestionable.
    *   **Integración Evolución**: La sub-pestaña `sub-evolucion` ya es controlable desde el Modal de Configuración (Implantador) y el Admin de Usuarios (TAB_IDS).
    *   **Sincronización**: Lógica de persistencia en `dashboard.html` actualizada para incluir la nueva sub-pestaña en el arranque.
**Actualización de sesión (17/01/2026)**
*   **Gestión de Visibilidad (Admin)**:
    *   **Backend (views.py)**: Suavizada la lógica de filtrado global (ahora `not False`) para permitir que pestañas nuevas aparezcan por defecto en el panel de administración.
    *   **IDs de Pestañas**: Ampliada la lista `TAB_IDS` en el backend para incluir todas las sub-pestañas de Auto Entreno (`subtab-*`).
*   **Estetización Compras (Pixel Perfect)**: Corregidos estilos de fuentes y alineación.
*   **Fix Crítico Compras (Renderizado Simple)**:
    *   **Problema**: Widgets de Compras (1D, 7D, KPIs anuales) invisibles/undefined al cargar la pestaña oculta. Causa raíz: ECharts falla al dimensionar en contenedores `display:none`.
    *   **Solución (Lección Aprendida)**: Implementada función `renderWidgetSimple` que inyecta HTML/CSS plano.
    *   **REGLA DE ORO TÉCNICA**: Para KPIs o datos numéricos simples que no requieren gráficos complejos, **EVITAR LIBRERÍAS DE CHARTING** (ECharts). Usar renderizado DOM directo (texto plano + CSS) para evitar problemas de ciclo de vida y visibilidad. Menos dependencia = Mayor robustez.

**Actualización de sesión (17/01/2026) - Continuación**
*   **Corrección Vista Móvil**:
    *   **Filtrado de Empresas (Seguridad)**: Implementada lógica en `views.py` (`mobile_dashboard_view`) para restringir el acceso solo a empresas autorizadas en `UserEmpresaPermission`. Se corrigió el filtrado para priorizar estas restricciones incluso sobre permisos de Superusuario, garantizando que el usuario "admin" solo vea lo que tiene explícitamente asignado.
    *   **Sintaxis Plantilla**: Solucionado error crítico `TemplateSyntaxError` en `mobile_dashboard.html` forzando la escritura de espacios alrededor del operador `==` en las etiquetas `{% if %}`, superando problemas de escritura automática.
    *   **Acceso Externo (Ngrok)**: Configurado `SECURE_PROXY_SSL_HEADER` y `USE_X_FORWARDED_*` en `settings.py` para resolver errores CSRF (403 Forbidden) al acceder via túneles https.
    *   **Identidad Visual**: Sincronizado el logo por defecto en móvil (`logo_analytics.png`) para coincidir con la versión de escritorio.

**Actualización de sesión (19/01/2026)**
*   **Actualización Global del Catálogo (Código 999)**:
    *   **Automatización**: Implementados scripts `scripts/generate_catalog_data.py` y `scripts/update_catalog_html.py` para analizar el código fuente (AST Parsing) y regenerar la documentación técnica.
    *   **Cobertura**:
        *   **API Endpoints**: Documentación exhaustiva extraída de `datia/api/*.py`, incluyendo nuevos endpoints de `mobile_endpoints.py`, `endpoints_evolucion.py`, etc.
        *   **Servicios**: Lista actualizada de todos los servicios backend (`datia/services/*.py`).
        *   **Modelos**: Inventario completo de modelos de datos (`datia/models/*.py`).
    *   **Frontend y Patrones**: Se mantienen las secciones manuales y dinámicas, preservando la documentación rica del motor frontend.
*   **Limpieza**: Eliminados scripts de depuración (`debug_balance.py`, `scripts/debug_stocks_error.py`) y archivos temporales.

**Actualización de sesión (21/01/2026)**
*   **Servidor dual (runserver)**:
    *   Se sobrescribe el comando `runserver` para arrancar simultáneamente 8000 (config.settings) y 8001 (config.settings_mobile).
    *   Fallback “single” mediante `DATIA_RUNSERVER_SINGLE=1` o ejecución directa con `--settings=config.settings_mobile`.
    *   Se mantiene el comando alternativo `manage.py serveboth` como opción explícita para dual.
*   **Móvil / Salud**:
    *   `ROOT_URLCONF=config.urls_mobile` con endpoint `/health` estable (OK-MOBILE).
    *   Configuración CSRF/SSL para túneles (Ngrok/Cloudflare) activa en `settings.py`.
*   **Catálogo (Landing)**:
    *   Añadidas tarjetas informativas en `catalog.html` para documentar el arranque dual y el comando `serveboth`.
*   **Limpieza de sesión**:
    *   Eliminados archivos no esenciales de depuración/verificación (debug_*, verify_*, audit_* y ficheros temporales .txt). Se preserva `PROJECT_CONTEXT.md`.

**Actualización de sesión (22/01/2026)**
*   **Corrección Servicio IA (Robustez y Typos)**:
    *   **Normalización de Texto**: Implementado `QueryBuilder._normalize_tokens` para corregir errores ortográficos comunes ("venetes" -> "ventas") antes del análisis de intención.
    *   **Validación de Esquema SQL**: Modificado `QueryBuilder` para no usar nombres de columnas hardcodeados ("CodigoEmpresa"). Ahora resuelve dinámicamente el casing correcto ("codigoempresa") consultando el esquema de la BD, evitando errores `ProgrammingError` en Postgres.
    *   **Manejo de Errores Críticos**: Actualizado `BaseHandler` para propagar excepciones SQL críticas en lugar de silenciarlas como "Sin datos", facilitando el diagnóstico.
    *   **Detector de Intenciones**: Ampliado el diccionario de sinónimos en `IntentDetector`.
*   **Corrección Feedack (Network Error)**:
    *   **Refactor Endpoints**: Modificados `/ai/feedback` y `/ai/learn` para aceptar **JSON Body** en lugar de parámetros URL. Esto soluciona el error "Failed to fetch" al guardar consultas largas o con caracteres especiales.
    *   **Frontend**: Actualizado `ia.js` para enviar payloads JSON.
*   **Corrección Bug Crítico (Backend)**:
    *   **Endpoints**: Solucionado error `name 'ejercicio' is not defined` en `learn_query` añadiendo la variable faltante.
*   **Política UX (Alerts)**:
    *   **Frontend (`ia.js`)**: Eliminados todos los `window.alert()` prohibidos, reemplazándolos con `showToast()` para notificaciones no intrusivas.
*   **Mejora de Historial**:
    *   **Endpoints**: Vinculado `learn_query` con `MetricsSavedQuery` para que las consultas aprendidas ("Manita Arriba") se guarden automáticamente en el Historial del usuario.
*   **Verificación**: Script de prueba confirma que queries con typos generan SQL válido y ejecutable.
*   **Limpieza**: Eliminados scripts de verificación temporal.

**Actualización de sesión (22/01/2026) - Parte 2**
*   **Corrección Tesorería**:
    *   **Visibilidad**: Solucionado el problema de la doble ocultación (`display:none` forzado en template interno) que dejaba la pestaña vacía.
    *   **Datos**: Activado el cálculo cliente del *Ratio de Liquidez* y eliminados placeholders estáticos.
    *   **Layout Refinado**: Implementada rejilla CSS (`grid-template-columns: repeat(4, 1fr)`) para mostrar los 8 KPIs en formato 4x2, optimizando el espacio y respondiendo a la solicitud de diseño.
    *   **Verificación**: Script de backend confirmó la integridad de los datos en `DatiaCarteraEfectos`.

**Actualización de sesión (22/01/2026) - Parte 3**
*   **Reportes Estratégicos IA (Ventas)**:
    *   **Backend**: Implementado `VentasContextBuilder` para agregación de datos (KPIs, Top Clientes, Top Artículos, Tendencias). Nuevo servicio `generate_strategic_report` en `IAService` integrando Ollama local.
    *   **Integración**: Botón "Análisis IA" añadido a la barra de estado de la pestaña Ventas.

**Actualización de sesión (23/01/2026)**
*   **Análisis Integral (Documentación)**:
    *   **Reescritura Completa**: Actualizado `docs/analisis_datia.txt` para reflejar fielmente el estado "AI-First" y la arquitectura híbrida actual.
    *   **Cobertura**:
        *   **Arquitectura Dual**: Documentada la separación de puertos 8000 (Escritorio) y 8001 (Móvil).
        *   **Frontend**: Detalles sobre el enfoque "No-Framework" y renderizado mixto.
        *   **Nuevos Módulos**: Inclusión de Dashboards Financieros, Tesorería y análisis predictivo "Senior".
        *   **Reglas de Oro**: Explicita los principios técnicos de desarrollo y mantenimiento.



**Actualización de sesión (24/01/2026)**
*   **Presupuestos - Comparativa y Refinamiento (Refundación)**:
    *   **Tablas (Comparativa)**: Reescritura total del renderizado (CSS Grid/Flex) para eliminar scroll horizontal y alinear perfectamente columnas de cuenta, descripción, valores y variación (con flechas y colores).
    *   **Carga por defecto**: Forzada la vista de "Comparativa" al entrar en Presupuestos (vía `core.js`).
*   **Interfaz (Global)**:
    *   **Filtros en Barra de Estado**: Movidos los selectores de "Empresa" y "Ejercicio" del header principal a la barra inferior (`info-bar`), limpiando la cabecera.
*   **Corrección de Bugs (Save Hang)**:
    *   **Problema**: El botón "Guardar Cambios" se quedaba bloqueado ("Guardando...") si no se detectaban cambios numéricos en la rejilla, impidiendo guardar Notas o controles Checkbox aislados.
    *   **Solución**: Refactorizado `saveBudgetGrid` en `presupuestos.js` para:
        1.  Detectar correctamente cambios en `dirtyControls` y `dirtyNotes`.
        2.  Garantizar el reset del botón en todos los flujos de retorno (incluyendo "Sin cambios").

**Actualización de sesión (25/01/2026)**
*   **Financiera - Análisis Estratégico AI (NF-002)**:
    *   **Backend**: Implementación de `FinancialContextBuilder` para la recopilación de KPIs, P&L, Balance y Ratios. Extensión de `IAService` para soportar informes de tipo "financiera" con prompts especializados para CFO.
    *   **Frontend**: Inserción del botón "Análisis IA" en la barra de herramientas de la pestaña Financiera, replicando la UX de Ventas (Overlay + Carrusel de Estado).

**Actualización de sesión (25/01/2026) - Controller IA Mejorado**:
*   **Deep Financial Logic**:
    *   **Backend**: `FinancialContextBuilder` ahora inyecta Presupuestos, Tesorería (Forecast 3M) y Ratios detallados en el contexto del LLM.
    *   **Model Optimization**: `IAService` configura dinámicamente el modelo `qwen2.5:7b` (si está disponible) para razonamiento experto.
*   **Persistencia y Exportación**:
    *   **PDF**: Implementado `PDFService` con `xhtml2pdf` y endpoint `/api/ai/report/export/pdf`.
    *   **Auto-Save**: Los informes se guardan automáticamente como `MetricsSavedQuery` al generarse.
    *   **UX**: Botón "Descargar PDF" integrado en el resultado del análisis y en el histórico.

**Actualización de sesión (26/01/2026)**
*   **Infraestructura IA (DeepSeek)**:
    *   **Almacenamiento**: Migración del repositorio de modelos Ollama a `F:\ollama_models` mediante variable de entorno `OLLAMA_MODELS` (User Scope).
    *   **Modelo**: Descarga e instalación de `deepseek-r1:14b` como nuevo motor de inferencia disponible.
    *   **Consistencia**: Se detuvieron los servicios previos para liberar locks y asegurar la transición limpia. Los modelos antiguos en C: permanecen intactos pero inactivos.
