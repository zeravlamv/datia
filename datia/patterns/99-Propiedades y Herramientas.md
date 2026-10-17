# Patron: Propiedades y Herramientas

Este documento organiza los módulos de configuración y herramientas del sistema.

## 1. Módulos y Conceptos

### 1.1. Configuraciones de Usuario
- **Entidad**: `UserReference` / `UserParameter` (en `accounts`).
- **Frontend**: Modal de Ajustes (icono en borrador superior derecha).
- **Flujo**: JS -> `/api/accounts/preferences` -> DB.

### 1.2. Herramientas de Mapeo (Data Mapping)
- **Objetivo**: Configurar qué tablas del ERP se sincronizan y qué campos son dimensiones o métricas.
- **Backend**: `DataSource` y `DataField` (Models en `datia/models/semantic.py`).
- **UI**: Pestaña "Datia" -> Sección "Fuentes de Datos".

### 1.3. Auto-Entrenamiento (ETL & Embeddings)
- **Funcionalidad**: Proceso que lee metadatos, genera embeddings vectoriales y actualiza el contexto de la IA.
- **Backend**: `etl_service.py` y `embedding_service.py`.
- **Trigger**: Botón "Sincronizar" o tarea programada.

### 1.4. Gestión de Claves (API Keys)
- **Ubicación**: `.env` (No editable desde UI por seguridad).
- **Proveedores**: OpenAI, Anthropic, Gemini, DeepSeek (Configurable en `settings.py`).

### 1.5. Opciones de Desarrollador (AI Models)
- **Funcionalidad**: Selección manual de modelos LLM (Ollama) para chat y análisis semántico.
- **Frontend**: Modal de Ajustes -> Pestaña Desarrollador.
- **Persistencia**: `localStorage` (`datia-ai-model`, `datia-semantic-model`).
- **Uso**: Inyección dinámica en API calls (`/api/semantic/generate-metadata`, `/api/datia/qa`).

## 2. NEW (Desarrollo Futuro)
1.  **UI de Mapeo Semántico**: Crear una interfaz visual (DnD o Tabla) para editar `DataField.usage_type` y `synonyms` sin tocar la BD.
2.  **Monitor de Sync en tiempo real**: Usar WebSockets para ver el progreso del ETL en el frontend.

## 3. REVIEW (Mantenimiento)
1.  Revisar seguridad de endpoints de configuración (actualmente abiertos a todos los usuarios autenticados).
