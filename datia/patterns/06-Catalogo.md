Patron de funcionamiento del Catalogo del Sistema
=================================================
Este patrón define la estructura y mantenimiento de la documentación viva del sistema, centralizada en el Catálogo.

1. Arquitectura
---------------
El catálogo es una vista accesible vía web (`/catalog/`) que centraliza toda la información técnica y de negocio.
- **Frontend**: `datia/templates/datia/catalog.html` (Single Page Interface).
- **Backend**: Renderizado directo vía Django Template.
- **Fuente de Verdad**: Los archivos `.md` en `datia/patterns/`.

2. Reglas de Funcionamiento
---------------------------
1. **Punto de Entrada**: La URL `/catalog/` debe ser accesible para desarrolladores y administradores.
2. **Sincronización**: 
   - El archivo HTML (`catalog.html`) es la representación visual.
   - Los archivos Markdown (`patterns/*.md`) son la fuente canónica.
   - Cualquier cambio estructural en el código debe reflejarse primero en su patrón correspondiente.

4. Gestión de Nuevas Funcionalidades
------------------------------------
Se ha habilitado una sección para gestionar la hoja de ruta del producto.
- **Identificador**: `NF-XXX` (Auto-incremental).
- **Flujo**:
    1. El usuario crea una petición en la pestaña "Nuevas Funcionalidades".
    2. Se asigna un patrón existente o se propone uno nuevo.
    3. Cuando se implementa, se marca como Done.
- **Almacenamiento**: `datia/patterns/features.json`.

3. Protocolo "Fin Sesion"
-------------------------
**REGLA CRITICA**: Cuando el usuario indique el comando "Fin sesion":
1. El Agente debe repasar los cambios realizados durante la sesión.
2. Verificar si algún patrón existente ha sido modificado o si se ha creado uno nuevo.
3. Actualizar los archivos `.md` correspondientes.
4. Editar `catalog.html` para reflejar:
   - Nuevos endpoints API.
   - Nuevos modelos de datos.
   - Cambios en la arquitectura.
   - Nuevos patrones añadidos.

NEW: Puntos pendientes
----------------------
1. ~~Implementar carga dinámica de patrones leyendo directamente el directorio `.md`~~ ✅ **IMPLEMENTADO** (función `loadPatternsList()` en `catalog.html` carga desde `/api/patterns/`).
2. ~~Añadir buscador en tiempo real sobre el contenido de los patrones~~ ✅ **IMPLEMENTADO** (función `searchPatterns()` filtra patrones por nombre en tiempo real).

47→REVIEW: Mantenimiento
48→---------------------
49→1. Revisar que todos los endpoints en `urls.py` estén listados en la sección API.
50→2. Última revisión completa: 2026-01-15 - ✅ Catálogo actualizado (añadido `StandardField` y endpoints relacionados).
51→3. Mejoras implementadas: Buscador de patrones, corrección de issues.json, documentación de política de semilla (`fix_type=True` en altas de Campos Estándar).
52→4. Referencia Técnica: `catalog.html` (Frontend)
53→-----------------------------------------------

La lógica del catálogo reside en un script monolítico dentro de `catalog.html`, dividido en 4 módulos lógicos:

### A. Gestión de Navegación (`showSection`)
*   **`showSection(sectionId, btn)`**:
    *   **Propósito**: Alterna la visibilidad de las secciones (`.section`).
    *   **Lazy Loading**: Si la sección requiere datos (Patrones, Issues, Features), invoca su función de carga (`load...`) automáticamente al abrirse.

*   **`searchCatalog()`**:
    *   **Propósito**: Filtra tarjetas en tiempo real (`endpoint-card`, `service-card`, `model-card`) basándose en el input de búsqueda.

### B. Gestión de Patrones (`Logic Patterns`)
*   **`loadPatternsList()`**:
    *   **Propósito**: Obtiene la lista de archivos `.md` desde `/api/patterns/`.
    *   **Efecto Lateral**: Llama a `updatePatternDropdowns` para poblar los selectores en las secciones de Issues y Features.

*   **`loadPatternContent(filename)`**:
    *   **Propósito**: Carga el contenido de un patrón específico en el editor (`textarea`).
    *   **UI**: Deshabilita el botón guardar hasta que la carga finaliza.

*   **`saveCurrentPattern()`**:
    *   **Propósito**: Envía el contenido modificado a `/api/patterns/save`.

### C. Gestión de Problemas (`Logic Issues`)
*   **`loadIssuesData()` y `renderIssues()`**:
    *   **Propósito**: Carga problemas de `/api/issues/` y renderiza el DOM.
    *   **Filtros**: Permite alternar entre vista `open` (pendientes) y `resolved` (histórico).

*   **`addIssue()` y `editIssue(index)`**:
    *   **Propósito**: Gestiona el CRUD local del array `allIssues`.
    *   **Validación**: Requiere ID único y Título.

*   **`saveAllIssues()`**:
    *   **Propósito**: Persiste todo el array de issues en el backend (`issues.json`).
    *   **Modo**: "Silent" para guardar cambios de estado sin notificar, o con Toast para confirmación explícita.

### D. Gestión de Funcionalidades (`Logic Features`)
*   **`loadFeaturesData()` y `renderFeatures()`**:
    *   **Propósito**: Carga y visualiza el Roadmap desde `/api/features/`.
    *   **UI**: Muestra badges de modo de ejecución (`✨ REFINAR` vs `⚡ CERO`).

*   **`addFeature()` y `editFeature(index)`**:
    *   **Propósito**: CRUD de funcionalidades.
    *   **Lógica Especial en Edit**: Asegura que el selector de patrón (`featurePattern`) mantenga su valor usando `data-value` para evitar condiciones de carrera con la carga asíncrona de patrones.

*   **`completeFeature(index)`**:
    *   **Acción**: Marca estado `done`, asigna timestamp `completed_at` y guarda.

*   **`resetFeature(index)`**:
    *   **Acción**: Devuelve estado a `pending`, limpia timestamp y guarda. Util para reiniciar trabajos.

### E. Utilidades
*   **`showToast(message, isError)`**: Sistema de notificaciones nativo del catálogo, independiente de `core.js`.
*   **`updatePatternDropdowns(files)`**: Función auxiliar crítica que sincroniza los dropdowns `<select>` de Issues y Features cada vez que se recargan los patrones, manteniendo la selección previa si existe.
