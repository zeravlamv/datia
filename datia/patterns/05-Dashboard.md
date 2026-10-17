Patron de funcionamiento de Dashboard (Framework)
==================================================
Este patrón define la arquitectura base de la aplicación (SPA), la gestión de estado global y el panel de configuración (Propiedades).

1. Arquitectura SPA (`core.js`)
-------------------------------
Aunque Django sirve el HTML inicial (`views.py`), la aplicación se comporta como una Single Page Application.
- **Router**: Navegación por pestañas controlada por `switchTab()`. Gestiona clases `.active` y visibilidad sin recarga.
- **Gestión de Estado**:
  - `currEmpresa` y `currEjercicio` son variables globales.
  - Persistencia mixta: URL Params > LocalStorage > Default.
  - `applyFilters()`: Recarga la página completa para refrescar todos los contextos (backend driven reload para seguridad).

2. Interfaz y Layout (`dashboard.html`)
---------------------------------------
- **Sticky Header**: Contiene selectores globales (Empresa, Ejercicio) y acceso a Configuración.
- **Modales**:
  - `settings-modal`: Configuración de usuario y desarrollador.
  - `sync-modal`: Feedback visual de procesos largos (ETL).

3. Sistema de Propiedades (Configuración)
-----------------------------------------
Gestionado integralmente en el cliente (`localStorage`) para persistencia inmediata.

### 3.1 Personalización (Usuario)
- **Logos**:
  - `datia-selected-logo`: Selección entre presets de diseño (Datia Original, Datia AI, Black Edition).
  - `datia-client-logo`: Carga de imagen personalizada (Base64) que reemplaza el logo en cabecera.
- **Temas**:
  - Soporte para tema `Verde` (Green) y `Violeta` (Violet/Default).
  - Inyecta clases CSS en `<body>` (`.theme-green`).

### 3.2 Modo Desarrollador
- **Switch "Show SQL"**: Habilita bloques de depuración en respuestas de AI (`datia-show-sql`).
- **Switch "Training Mode"**: Habilita botones de feedback y re-entrenamiento (`datia-training-mode`).
- **Switch "Auto Load"**: Controla si los widgets cargan al inicio o bajo demanda.

4. Sincronización (Sync)
------------------------
- **Trigger**: Botón en `dashboard.html` o vía API.
- **Feedback**: `openSyncModal()` consume un stream de eventos (`Server-Sent Events` simulado) desde el backend.
- **Endpoint**: `POST /api/sync/trigger` retorna texto en chunks para actualizar la barra de progreso en tiempo real.

5. Estándares de Código
-----------------------
- **Formateadores**: `fmtMoney` y `fmtNum` (Intl) deben usarse para todo valor numérico.
- **Errores**: Uso de `showToast()` para notificaciones no intrusivas.
- **Logos**: Todos los componentes usan `id` únicos para ser actualizados dinámicamente por `selectDatiaLogo()`.

## 6. Referencia Técnica: `core.js`

Este archivo actúa como el **Kernel del Frontend**, orquestando la inicialización, configuración y estado global.

### A. Inicialización y Ciclo de Vida
*   **`init()`**:
    *   **Propósito**: Punto de entrada (`DOMContentLoaded`).
    *   **Flujo**:
        1.  Detecta parámetros `empresa` y `ejercicio` (URL > LocalStorage).
        2.  Llama a `updateSystemDate()`, `initTheme()`, `initSettings()`, `loadFilters()`.
        3.  Inicializa pestañas con `initTabs()`.
        4.  Carga módulos perezosos: `loadDashboard`, `loadSnapshot`, `loadHistory`.

*   **`updateSystemDate()`**:
    *   **Propósito**: Muestra la fecha actual en la cabecera.
    *   **Formato**: "Lunes, 16 de diciembre de 2025" (Capitalizado).
    *   **Localización**: Usa `APP_LANG` (inyectado por Django) para garantizar que `toLocaleDateString` coincida con el idioma de la sesión.

### B. Gestión de Configuración (Settings)
*   **`initSettings()`**:
    *   **Propósito**: Restaura preferencias guardadas al cargar la página.
    *   **Detalle**: Aplica el logo seleccionado (`datia-selected-logo`), el logo de cliente (`datia-client-logo`) y el tema.

*   **`openSettings()` / `closeSettings()`**:
    *   **Propósito**: Abre/Cierra el modal de ajustes (`#settings-modal-overlay`).
    *   **Acción**: `openSettings` relanza `initSettings` para asegurar consistencia visual.

*   **`selectDatiaLogo(btn, src)`**:
    *   **Params**: `btn` (elemento clickeado), `src` (ruta imagen).
    *   **Uso**: Cambia el logo oficial de Datia en toda la app (Header, Tab IA, Modales, Favicon) y persiste en `localStorage`.

*   **`uploadClientLogo(input)`**:
    *   **Uso**: Procesa la subida de imagen local (Max 2MB).
    *   **Lógica**: Convierte a **Base64** con `FileReader` y guarda en `localStorage` asociado a la empresa actual.

*   **`removeClientLogo()`**:
    *   **Uso**: Elimina el logo de cliente y restaura la visibilidad por defecto.

*   **`renderClientLogo(src)`**:
    *   **Propósito**: Renderiza el logo de cliente en el Header y la previsualización de ajustes.

### C. Navegación y Pestañas
*   **`switchTab(tabId)`**:
    *   **Propósito**: Cambia la vista activa.
    *   **Lógica**: Gestiona clases `.active` en paneles (`.tab-panel`) y botones (`.tab-btn`).

*   **`initTabs()`**:
    *   **Propósito**: Configura comportamientos avanzados de pestañas.
    *   **Funciones**:
        *   **Header Favorites**: Doble Click en pestaña principal guarda preferencia (`datia-fav-main-tab`). Indicador visual CSS (`.is-favorite`).
        *   **Sub-Tab Favorites**: Click en icono estrella (★) guarda sub-pestaña específica por sección (e.g., `datia-fav-auto-tab`).
        *   **Auto-Start**: Carga la pestaña favorita guardada o `tab-actualidad` por defecto.

*   **`setFavoriteTab(tabId)`**:
    *   **Uso**: Guarda/Borra referencia en `localStorage` y notifica con `showToast`.
    *   **Clave**: Favorito principal del header en `datia-fav-main-tab`. Se migra automáticamente desde `datia-fav-tab` si existía.

*   **`updateFavoriteUI(favTabId)`**:
    *   **Propósito**: Aplica clase `.is-favorite` (Header) o color amarillo en estrella (Sub-tabs).

### D. Estado y Datos
*   **`loadFilters()`**:
    *   **Propósito**: Carga listas de Empresas y Ejercicios desde `/api/filters`.
    *   **Manejo de Error**: Inyecta mensaje de error en el selector y en el chat de IA si falla.

*   **`applyFilters()`**:
    *   **Uso**: Invocado al cambiar selectores del Header.
    *   **Acción**: Guarda selección en `localStorage` y **recarga la página** (`window.location.href`) para refrescar todo el contexto (backend-driven).

### E. Sincronización (ETL)
*   **`openSyncModal()`**:
    *   **Propósito**: Trigger de la sincronización manual.
    *   **Lógica**:
        1.  Muestra barra de progreso en 0%.
        2.  POST a `/api/sync/trigger`.
        3.  Lee **Stream (Chunks)** de la respuesta para actualizar progreso y mensajes en tiempo real.
        4.  Al llegar a "Done" (100%), recarga la página.

*   **`closeModal()`**: Cierra el modal de sincronización.

### F. Utilidades Visuales
*   **`fmtMoney.format(value)`**:
    *   **Retorno**: String formateado `X.XXX,XX €`.
    *   **Detalle**: Maneja `null`/`NaN` retornando `0,00 €`. Usa punto para miles, coma para decimales.

*   **`showToast(msg)`**:
    *   **Uso**: Notificaciones efímeras (2.5s) flotantes.
    *   **Implementación**: Crea `div` dinámico con animación CSS inyectada.

*   **`initTheme()`**:
    *   **Propósito**: Gestión del modo Verde/Violeta.
    *   **Lógica**: Toggle de clase `.theme-green` en `<body>`.
