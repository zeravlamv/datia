# Patron: Gestión de Problemas

Este documento describe el sistema de seguimiento y resolución de incidencias (Issues) en Datia.

## 1. Arquitectura
- **Almacenamiento**: `datia/patterns/issues.json`.
- **API**: `datia/api/issues.py` (Endpoints: `/api/issues/list`, `/api/issues/save`).
- **Frontend**: Sección "Problemas Conocidos" en `catalog.html`.

## 2. Estructura de Datos (JSON)
Cada problema se registra con el siguiente esquema:
```json
{
    "id": "ISS-001",
    "title": "Descripción corta del error",
    "description": "Detalle técnico y contexto.",
    "pattern": "Archivo o módulo afectado (ej: api/endpoints.py)",
    "solution": "Propuesta o fix aplicado.",
    "created_at": "ISO-8601 Timestamp", // Fecha de reporte
    "status": "open",       // 'open' | 'resolved'
    "resolved_at": "ISO-8601 Timestamp" // Solo si status='resolved'
}

## 2.1. Visualización
- **Orden**: Descendente (Más recientes primero).
- **Metadatos**: Debe mostrarse siempre la fecha (Creado o Resuelto).
```

## 3. Flujo de Estados
### 3.1. Abierto (`open`)
- Estado inicial.
- Visible en la pestaña "🔥 Pendientes" del catálogo.
- Representa trabajo por hacer.

### 3.2. Resuelto (`resolved`)
- Soft-Delete.
- Al marcarse como resuelto:
    - Se asigna `status: 'resolved'`.
    - Se estampa `resolved_at` con fecha/hora actual.
    - Se mueve visualmente a la pestaña "🗑️ Histórico" (Papelera).
- **Persistencia**: El cambio de estado guarda automáticamente el JSON.

## 4. Operaciones Destructivas
### 4.1. Eliminar Definitivamente
- Desde el Histórico, se puede eliminar un item individual.
- Acción irreversible (borra del JSON).

### 4.2. Vaciar Papelera
- Botón global en Histórico.
- Elimina **TODOS** los items con `status: 'resolved'`.
- Requiere confirmación explícita del usuario.

## 5. Automatización AI
- El Agente AI tiene capacidad para:
    1.  Leer reportes de chat.
    2.  **OBLIGATORIO**: Registrar automáticamente en `issues.json` como primer paso de cualquier intervención de "fix". **PROHIBIDO solucionar sin registrar.**
    3.  Resolver y actualizar estado tras aplicar fixes.
