Patron de funcionamiento de Actualidad (Analytics)
===================================================
Este patrón define la lógica de la pestaña "Actualidad", encargada de mostrar el estado del negocio en tiempo real.

1. Flujo de Datos
-----------------
MSSQL (ERP) -> ETL -> Postgres (MetricsTotales) -> API (Endpoints) -> Frontend (Widgets)

2. Arquitectura Backend (Cálculo)
---------------------------------
### 2.1 Agregación (`totals_service.py`)
Para garantizar latencia < 200ms en el dashboard, **nunca** se consulta el Raw Data en tiempo real.
Se usan tablas pre-calculadas que se actualizan durante la sincronización (`ETLService`).

- `MetricsTotalesEmpresaEjercicio`: Totales anuales (Neto, Coste, Margen).
- `MetricsTotalesEmpresaEjercicioMes`: Evolución mensual para gráficos.
- `MetricsTotalesEmpresaEjercicioCliente`: Ranking de mejores clientes.
- `MetricsTotalesEmpresaEjercicioMesCodigoPostal`: Mapa de calor de ventas.

### 2.2 Endpoints de Visualización (`endpoints.py`)
La API expone endpoints específicos para cada widget, desacoplados entre sí para carga paralela.

- `GET /api/datia/widgets/snapshot`:
  - Retorna los "Big Numbers" del encabezado (Día, Semana, Mes).
  - Compara con periodos anteriores para mostrar tendencias (YoY).

- `GET /api/datia/widgets/actividad_mensual`:
  - Retorna 2 series: Ventas (Barras) y Margen (Línea).
  - Eje X: Meses del año.

- `GET /api/datia/widgets/top_clientes`:
  - Retorna lista ordenada por importe neto descendente.
  - Soporta parámetro `limit` (default 5).

3. Arquitectura Frontend (Renderizado)
--------------------------------------
Gestionado por `datia/static/js/dashboard/actualidad.js`.

### 3.1 Carga del Dashboard (`loadDashboard`)
Función maestra que orquesta la carga de todos los widgets.
- **Loader**: Muestra una animación de carga "Procesando Inteligencia" hasta que los datos críticos (Snapshot) están listos.
- **Auto-Load**: Configurable desde Propiedades. Si está desactivado, muestra un botón "Cargar Datos".

### 3.2 Matriz 3x3 (`load3x3Grid`)
Renderiza la cuadrícula comparativa de Ventas, Ticket Medio y Margen.
- **Periodos**: 1 Día, 7 Días, 30 Días.
- **Comparativa**: Calcula la variación porcentual respecto al periodo anterior.
- **Interacción**: Soporta "Flip" (Giro 3D) para ver el origen del dato.

### 3.3 Gráficos (`charts.js`)
Usa `ApexCharts` para la visualización.
- **Configuración**: Tema oscuro (`dark`), animaciones suaves (`dynamicAnimation`).
- **Paleta**: Usa variables CSS (`--accent`, `#34d399`) para consistencia con el tema.

4. Reglas de Negocio
--------------------
- **Margen**: Se calcula siempre como `(Neto - Coste) / Neto * 100`.
- **Ejercicio**: Todos los widgets filtran estrictamente por `empresa_id` y `ejercicio` seleccionados en el header.
- **Fallback**: Si no hay datos para el ejercicio actual, los widgets muestran 0,00€ (no error).

5. Estándares Visuales (Card V2)
--------------------------------
El patrón visual actual para las tarjetas de KPI es:
- **Borde**: Sólido y grueso (`3px solid var(--accent)`).
- **Sombra**: Sutil, solo en el elemento activo (evitar doble sombra en wrappers).
- **Layout**: Diseño flexible que se adapta al contenido, sin alturas fijas que rompan el giro.

6. Funcionalidad: Origen del Dato (Card Flip)
---------------------------------------------
Las tarjetas de la primera fila (Ventas) implementan un giro 3D para transparencia del dato.

### 6.1 Estructura HTML
```html
<div class="flip-card">
  <div class="flip-card-inner">
    <div class="flip-card-front">...KPI...</div>
    <div class="flip-card-back">...Metadata...</div>
  </div>
</div>
```

### 6.2 Comportamiento
- **Trigger**: Botón de información (icono) en la esquina superior derecha.
- **CSS**: Usa `transform: rotateY(180deg)` y `backface-visibility: hidden`.
- **Contenido Trasero**:
  - **Tabla**: Nombre técnico de la tabla origen (ej. `CabeceraPedidos`).
  - **Campo**: Nombre del campo sumado (ej. `ImporteNeto`).
  - **SQL**: Snippet de la consulta realizada.
  - **Tiempo**: Momento de la última actualización.

7. Funcionalidad: Visualización Móvil (Mobile Experience)
-------------------------------------------------------
Implementa una experiencia móvil adaptativa y configurable.

### 7.1 Arquitectura
- **Modelo**: `MobileConfig` almacena el layout y modo (Standard/Custom) por empresa.
- **API**: `/api/mobile/config` para persistencia.
- **Manager**: `mobile_manager.js` gestiona la lógica de Drag & Drop y el renderizado runtime.

### 7.2 Modos de Operación
- **Estándar**: Renderiza la vista web responsive normal (Grids colapsados).
- **Especializado (Custom)**: 
  - Oculta la vista de escritorio en dispositivos < 768px.
  - Renderiza un contenedor exclusivo (`#actualidad-mobile-view`) con los widgets seleccionados.
  - **Optimización**: Carga solo los datos necesarios para los widgets activos.

### 7.3 Builder (Configurador)
- Accesible desde la sub-pestaña "Móvil" (activable desde Ajustes > Implantador).
- Interfaz Drag & Drop HTML5 nativa.
- Sincronización automática de cambios al backend.

IMPORTANTE: Al añadir un nuevo widget, debe crearse su tabla agregada correspondiente en Postgres.

8. Navegación Secundaria (Sub-Tabs)
------------------------------------
Actualidad utiliza un sistema de sub-pestañas para organizar la información:
1. **Dashboard** (Default): Visión general (KPIs + Gráficos).
2. **Financiera**: Desglose financiero detallado.
3. **Compras**: Dashboard espejo para métricas de compra (`loadComprasDashboard`).
4. **Móvil**: Editor de experiencia móvil (Configurable).

**Persistencia**:
- Cada sub-pestaña cuenta con un icono de **estrella (★)**.
- Al activarse, guarda `datia-fav-act-tab` en LocalStorage.
- Al cargar la sección Actualidad, restaura automáticamente la sub-pestaña marcada como favorita.
