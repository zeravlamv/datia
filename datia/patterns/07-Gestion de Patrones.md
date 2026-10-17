# Patron: Gestión de Patrones

Este documento explica cómo utilizar, mantener y estructurar la documentación técnica del proyecto (Patrones).

## 1. Concepto
Los "Patrones" son la fuente de verdad técnica de Datia. Sirven para:
- Documentar arquitectura por áreas (Dashboard, AI, ETL).
- Guiar al Agente AI en modificaciones futuras.
- Mantener el contexto del proyecto entre sesiones.

## 2. Ubicación
- **Directorio**: `datia/patterns/`
- **Formato**: Markdown (`.md`).

## 3. Estructura Estándar
Un archivo de patrón debe contener:

### Encabezado
Título descriptivo del módulo o área.

### Descripción / Arquitectura
Explicación de alto nivel de qué hace el módulo y qué archivos lo componen (Frontend, Backend, Modelos).

### Flujo de Datos
Diagramas o explicaciones de cómo viaja la información (ej: MSSQL -> ETL -> Postgres -> API -> JS).

### NEW (Desarrollo)
Sección reservada para definir nuevas funcionalidades a implementar.
- Usar ítems numerados.
- El usuario indicará "NEW 1" para activar esa tarea.

### REVIEW (Mantenimiento)
Sección para anotar deuda técnica, refactorizaciones pendientes o mejoras.
- Usar ítems numerados.
- El usuario indicará "REVIEW 2" para solicitar esa revisión.

## 4. Mantenimiento Automático
- El Agente AI debe leer el patrón correspondiente antes de editar código crítico.
- Si se cambia la arquitectura, el Agente debe **actualizar** el archivo `.md` inmediatamente.

## 5. Catálogo
- El archivo `catalog.html` centraliza el acceso visual a estos patrones.
- Permite leerlos y editarlos (si se implementa edición en UI).
