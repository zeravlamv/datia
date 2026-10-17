# 12 - Arquitectura de Plantillas (SaaS / On-Premise)

> [!NOTE]
> Este patrón define la arquitectura necesaria para escalar Datia como producto multi-cliente, desacoplando la "Inteligencia" (Configuración) de los "Datos" (Instancia).

## 1. Concepto Fundamental: Metadatos vs. Datos

Datia no es solo una herramienta de visualización, es un **Sistema Operativo de Negocio Inteligente**. Para que sea escalable y desplegable en cualquier cliente (SaaS o On-Premise), distinguimos estrictamente entre dos tipos de información:

### A. El "BluePrint" (La Inteligencia)
Son los activos de configuración que definen **CÓMO** piensa Datia. Son portables y agnósticos del cliente específico.
*   **Fuente de Verdad:** `DataSource` (Definición lógica), `DataField` (Mapeo semántico), `BusinessContext` (Reglas de negocio).
*   **Conocimiento Base:** `MetricsEmbeddings` (Entrenamiento genérico, e.g., "Cómo se calcula el margen en SAP").
*   **Valor:** Es lo que Datia vende/licencia ("Pack SAGE", "Pack Hotelero").

### B. La "Instancia" (Los Datos)
Es la materialización de esa inteligencia con los datos reales del cliente.
*   **Fuente de Verdad:** Tablas `datiadb_*` en PostgreSQL.
*   **Volumen:** Millones de registros.
*   **Valor:** Es propiedad privada del cliente.
*   **Ciclo de Vida:** Se puede borrar y regenerar (Sincronización) siempre que el BluePrint exista. **El "Factory Reset" borra esto.**

---

## 2. Flujo de Trabajo: De "Master" a "Cliente"

El ciclo de despliegue de Datia sigue un modelo de **Plantillas (Templates)** o "Packs":

### Fase 1: Ingeniería (Entorno Master)
1.  Los ingenieros de Datia conectan una instancia a un ERP de prueba (e.g., SAGE Demo).
2.  Realizan el mapeo (`DataField`), definen descripciones semánticas y entrenan a la IA con preguntas tipo.
3.  **ACCIÓN:** Exportan el "Pack de Conocimiento" (JSON/YAML).
    *   *Contenido:* Definiciones de Tablas, Campos, Descripciones, Contexto y Embeddings base.
    *   *Exclusión:* Credenciales de DB, Datos brutos.

### Fase 2: Despliegue (Entorno Cliente)
1.  Se instala "Datia Core" (Docker/Cloud) vacío en el cliente.
2.  **ACCIÓN:** Se importa el "Pack de Conocimiento" adecuado (e.g., "Pack SAGE").
    *   El sistema carga las definiciones en `DataSource`, `DataField`, etc.
3.  Configuración de `Connection`: Se apuntan las credenciales al SQL Server real del cliente.
4.  **ACCIÓN:** Sincronización Inicial (ETL).
    *   Datia lee el SQL del cliente usando el "mapa" del Pack.
    *   Llena las tablas `datiadb_*` locales.
5.  **Resultado:** La IA es funcional desde el minuto 0 porque ya "conoce" la estructura del ERP.

---

## 3. Componentes Técnicos Requeridos

Para materializar este patrón, se requiere implementar las siguientes herramientas (propuestas):

### Gestor de Plantillas (Template Manager)
*   **Exportador:** Un script/comando (e.g., `python manage.py export_template --pack=sap_v1`) que serializa los modelos de Django (`semantic` app) a un archivo fixture.
*   **Importador:** Un mecanismo de *Seed* inteligente que carga esos fixtures, respetando IDs o usando claves naturales (e.g., nombre de tabla) para evitar conflictos.

### Versionado de Packs
*   Los Packs deben tener versión (v1.0, v1.1).
*   Al actualizar un Pack en un cliente (e.g., mejores descripciones semánticas), el sistema debe actualizar los metadatos sin romper la sincronización de datos existente.

---

## 4. Diferenciación Competitiva

Esta arquitectura permite:
1.  **Onboarding Instantáneo:** "Conecta tu SAP y en 30 minutos puedes preguntar por tus ventas".
2.  **Especialización Vertical:** Crear "Packs" para nichos (Farmacias, Hoteles, Talleres) con reglas de negocio muy específicas pre-cargadas.
3.  **Privacidad:** La IA se entrena en nuestros servidores (Master); en el cliente solo se ejecuta (Inference/RAG), minimizando la fuga de datos sensibles durante el entrenamiento.
