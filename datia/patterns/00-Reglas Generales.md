# 00-Reglas Generales y Protocolos

Este documento define las leyes inmutables del proyecto Datia. Su cumplimiento es obligatorio para cualquier intervención.

## 1. Entorno y Arquitectura
*   **Sistema Operativo**: Windows.
*   **Base de Datos**: PostgreSQL (ÚNICA base de datos del sistema).
    *   Admin de Django → PostgreSQL
    *   Datos materializados (`datiadb_*`) → PostgreSQL
    *   Embeddings y contexto semántico → PostgreSQL
*   **Datos Origen (ERP)**: MSSQL (Acceso exclusivo a modo lectura/consulta).
*   **SQLite**: **PROHIBIDO**. No se usa para nada en esta aplicación.

## 2. Protocolo de Intervención (NNP & 666)
*   **Regla de Oro**: Nunca desarrollar sin un **Plan**, una **Explicación** y el código de confirmación **`666`**.
    *   *Excepción*: Si el prompt inicia con **`NNP`** (No Necesita Plan), se puede proceder directamente a la ejecución.
    *   *Excepción*: Si se indica **`PROBLEMA [código] + 666`**, se permite la corrección directa (Hotfix) sin plan previo.
*   **Control del Browser**: No iniciar la app ni tomar control del navegador a menos que se indique expresamente.
*   **Modificaciones**: Consultar siempre el patrón correspondiente antes de tocar nada. Si no existe patrón o no se encuentra, **DETENERSE**. No improvisar sin patrón (salvo NNP explícito).

## 3. Gestión de Patrones
*   **Lectura [NEW]**: Atender a la sección `NEW` seguida de un número para desarrollar nuevas funcionalidades. Siempre requiere Plan.
*   **Lectura [REVIEW]**: Atender a la sección `REVIEW` seguida de un número/nombre para revisar desarrollos existentes. Siempre requiere Plan.
    *   Al indicar `REVIEW` + nombre del patrón (ej: "REVIEW Auto Entreno"), se debe auditar el código para asegurar que cumple estrictamente las instrucciones de dicho patrón.

## 4. Gestión de Funcionalidades (NF) y Problemas
*   **Nuevas Funcionalidades (NF)**:
    *   Al recibir "NF" + número, preparar plan.
    *   Al finalizar, crear el patrón correspondiente (si es una feature compleja) o actualizar el catálogo.
*   **Problemas (ZERO TOLERANCE)**:
    > [!CRITICAL]
    > **PROTOCOLO OBLIGATORIO**: Cualquier mención de "PROBLEMA" activa el workflow `.agent/workflows/incident_protocol.md`.
    *   **Paso 1**: Registrar la incidencia en `issues.json` **ANTES, REPITO, ANTES** de escribir una sola línea de código de solución o plan. **VIOLAR ESTA REGLA ES INADMISIBLE.**
    *   **Paso 2**: Notificar al usuario "He registrado el problema ISS-XXX".
    *   **Excepción 666**: Si se indica `PROBLEMA` + `666`, se registra PRIMERO, se soluciona DESPUÉS y se cierra en el mismo ciclo. **EL REGISTRO PREVIO ES OBLIGATORIO SIEMPRE.**

## 5. Cierre de Sesión
*   **"Fin sesion"**:
    *   Actualizar el catálogo (`features.json`, `issues.json`).
    *   Actualizar `catalog.html` si hubo cambios en endpoints o lógica frontend.
    *   Asegurar que el estado del proyecto es consistente.

## 6. Experiencia de Usuario (UX/UI) [REGLA DE ORO]
*   **Modales y Alertas**:
    > [!IMPORTANT]
    > **PROHIBIDO** el uso de alertas nativas del navegador (`alert()`, `confirm()`, `prompt()`).
    *   Siempre se deben utilizar **modales personalizados** con diseño acorde a la aplicación (Glassmorphism, Dark UI).
    *   Esto aplica tanto a mensajes de error, confirmaciones de acción o notificaciones de éxito.

## 7. Internacionalización (i18n)
*   **Principio**: Datia es una plataforma multi-idioma nativa (ES, EN, FR, CA).
*   **Backend**: Uso estricto de `gettext` (`_()`) en Python y tags `{% trans %}` en templates.
*   **Frontend**: Inyección explícita del contexto de idioma (`APP_LANG`) para formateadores de fecha y números en JS (`Intl`). NO confiar en el idioma del navegador por defecto.
*   **Fecha**: Jamás hardcodear formatos o strings de fecha. Usar `toLocaleDateString` con el idioma inyectado.

## 8. Gestión de Visibilidad (Pestañas y Sub-pestañas)
*   **Regla de Oro**: Toda nueva (sub)pestaña **DEBE** ser controlable desde:
    1.  **Configuración / Opciones Implantador**: Añadir el checkbox correspondiente en el modal de ajustes (`dashboard.html`).
    2.  **Admin / Gestión Pestañas**: Añadir el ID de la pestaña a la lista `TAB_IDS` en la vista `tab_visibility_view` (`views.py`).
*   **Persistencia**: El sistema debe detectar automáticamente si una pestaña está oculta globalmente (vía `GlobalConfig`) o por usuario (vía `UserPreference`) y ocultarla del DOM en el arranque.
