# Patrón: Auto Entreno (Data Intelligence & Sync)

Este patrón define el flujo de "Auto Entreno", que permite a Datia conectar, mapear, enriquecer y sincronizar datos desde MSSQL (SAGE, etc.) hacia PostgreSQL para su explotación mediante IA.

## 1. Contexto de Negocio Global
**Objetivo**: Dotar a la IA de conocimiento general sobre la empresa.
*   **Almacenamiento**: Tabla `datia_businesscontext` en PostgreSQL.
*   **Funcionalidad**: El usuario introduce una descripción detallada de la empresa (hasta 10k caracteres) que ayuda a la IA a entender la terminología y procesos específicos.

## 2. Selección y Mapeo de Fuentes de Datos (Data Mapping)
**Objetivo**: Seleccionar tablas de origen (MSSQL) y definir su semántica.
1.  **Conexión**: Se listan las tablas disponibles en la conexión MSSQL configurada.
2.  **Contexto de Tabla**: El usuario define qué contiene la tabla (ej: "Cabeceras de facturas de venta").
3.  **Definición de Campos (`DataField`)**:
    *   **Nombre de Negocio**: Nombre legible para la IA (ej: "Importe Total" en lugar de `TOTAL_DOC`).
    *   **Rol del Campo**:
        *   `Dimension`: Datos descriptivos (Cliente, Vendedor).
        *   `Metric`: Datos numéricos operables (Importe, Cantidad).
        *   `Date`: Fechas para análisis temporal e inteligencia de series.
        *   `Ignore`: Campos técnicos o irrelevantes (GUIDs internos, checksums). **Estos campos NO se sincronizan**.
    *   **Semántica**: Descripción automática o manual del campo para el Prompt de la IA.
    *   **Es Clave (`is_key`)**: Indica si el campo forma parte de la clave única para evitar duplicados (ej: `NumeroPedido` + `Serie`).

## 3. Sincronización ETL (MSSQL -> PostgreSQL)
**Objetivo**: Mover datos relevantes a un almacenamiento optimizado para vectores y consultas IA.
*   **Destino**: Tablas en PostgreSQL con prefijo `datiadb_` (ej: `datiadb_CabeceraPedido`).
*   **Alcance Multi-Ejercicio**: La sincronización procesa **TODOS** los ejercicios/empresas vinculados, no solo el activo.
*   **Lógica Incremental**:
    *   Se utiliza la combinación de campos marcados como `is_key`.
    *   **No Duplicados**: Si un registro ya existe (basado en clave), se omite o actualiza (según configuración de inmutabilidad).
    *   **Persistencia**: Se respetan los tipos de datos originales (Texto, Numérico, Fecha) para garantizar la integridad en las consultas SQL generadas por la IA.
    *   **Feedback Visual**: Es obligatorio mostrar el **Total de Registros** a procesar vs **Procesados** (ej: "1500 / 5000") durante la sincronización para dar certeza al usuario.

## 4. Integración con el Catálogo
*   Cada vez que se modifica la estructura del Auto Entreno o se completa una funcionalidad relacionada, se debe verificar la actualización del archivo `catalog.html`.

## REVIEW
*   **Alcance de Sincronización**: La sincronización solo se debe hacer de la **tabla seleccionada**, para **todas las empresas** y **todos los ejercicios** disponibles. No se debe intentar sincronizar tablas no mapeadas o todo el ERP de golpe.

## 5. Generación Semántica (Resiliencia)
*   **Fallos Parciales**: Si el motor de IA no devuelve una descripción para un campo específico, la interfaz debe **limpiar el estado de carga** ("Pensando...") y permitir la entrada manual. No bloquear nunca la UI por un fallo de generación.
*   **Procesamiento por Lotes**: Para tablas grandes, la generación se realiza en bloques (batches) para evitar timeouts del servidor.

## 6. Control de Re-Entreno (Smart Training)
*   **Detección de Cambios**: El sistema compara automáticamente la fecha de modificación de los metadatos (`DataField.updated_at`) con la fecha del último entrenamiento (`MetricsEmbeddings.updated_at`).
*   **Lógica de Actualización**:
    *   Si `LastFieldUpdate > LastTraining`: Se fuerza el re-entreno (borrado de embeddings anteriores y regeneración).
    *   Si no hay cambios: Se salta el proceso para optimizar tiempo.
*   **Forzado Manual**: Se permite forzar el re-entreno mediante el parámetro `?force=true`.

---
**Notas Técnicas**:
*   Backend: `api/auto_training.py` (Lógica ETL), `models.py` (DataSource, DataField).
*   Frontend: `tab_auto.html` (Interfaz de usuario).

## 7. Navegación y Persistencia (Sub-Tabs)
*   **Gestor**: `tab_auto_core.js`.
*   **Sub-Tabs Disponibles**:
    1.  **Dashboard**: Entrada principal (default).
    2.  **Contexto Negocio**: `datia_businesscontext`.
    3.  **Campos de Datos**: Definición de metadatos (`DataField`).
    4.  **Relaciones**: Definición de Foreign Keys (`DataRelation`).
*   **Favoritos**:
    *   Soporta marcar una sub-pestaña específica como inicio (click en estrella ★).
    *   **Importante**: Usa clave local `datia-fav-auto-tab` para evitar conflictos con la navegación global.
    *   Persistencia en LocalStorage.
