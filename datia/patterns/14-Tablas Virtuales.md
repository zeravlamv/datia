# Patrón 14: Tablas Virtuales (NF-016)

## Objetivo

Permitir que ciertas tablas de MSSQL **NO se migren a PostgreSQL** pero sean consultables por la IA mediante JOINs directos. Esto es útil para tablas maestras grandes (ej: Clientes, Artículos) que no cambian frecuentemente.

## Caso de Uso

**Problema**: La tabla `Clientes` tiene 50,000 registros y rara vez se actualiza. Migrarla a PostgreSQL consume espacio y tiempo innecesariamente.

**Solución**: Marcar `Clientes` como **tabla virtual**. La IA podrá consultarla directamente desde MSSQL cuando necesite información de clientes.

## Arquitectura

### Modelo de Datos

```python
class DataSource(models.Model):
    is_virtual = models.BooleanField(
        default=False,
        help_text="Si True, esta tabla NO se migra a PostgreSQL"
    )
    
    def get_local_table_name(self):
        if self.is_virtual:
            return None  # No tiene tabla en PostgreSQL
        return f"datiadb_{self.source_table.lower()}"
```

### Flujo de Sincronización

```python
# ETL Service
if source.is_virtual:
    yield send_progress("DynamicSync", progress, 
                      f"📡 {source.name}: Tabla virtual. Omitiendo sincronización...")
    continue  # Skip migration
```

## Uso en UI

### 1. Mapear Tabla como Virtual

**Ubicación**: Auto Entreno → Mapeo de Datos

**Pasos**:
1. Seleccionar tabla (ej: `Clientes`)
2. Marcar checkbox **"📡 Tabla Virtual (No migrada)"**
3. Mapear campos necesarios
4. Guardar mapeo

**Resultado**: Tabla se guarda con `is_virtual=True`

### 2. Verificar Estado

**Ubicación**: Auto Entreno → Mapeo de Datos (Sidebar)

**Indicador**: Badge azul **"📡 VIRTUAL"** en lista de tablas

### 3. Sincronización

**Comportamiento**: 
- Tabla virtual se **omite** durante sincronización
- Mensaje en log: "📡 Tabla virtual (No migrada)"
- NO se crea tabla en PostgreSQL

### 4. Relaciones

**Uso**: Se pueden crear relaciones entre tablas físicas y virtuales

**Ejemplo**:
```
CabeceraPedido (física) → Clientes (virtual)
  FK: CodigoCliente → PK: Codigo
```

## Consultas de IA

### Estrategia Actual (Fase 1)

**Limitación**: La IA actualmente **NO puede** consultar tablas virtuales directamente.

**Pendiente**: Implementar AI Service para queries híbridas (PostgreSQL + MSSQL)

### Estrategia Futura (Fase 2)

**Opción A: Ejecución Dual en Python**
```python
# 1. Detectar tablas virtuales en query
# 2. Ejecutar query en PostgreSQL para tablas físicas
# 3. Ejecutar query en MSSQL para tablas virtuales
# 4. Combinar resultados en Python
```

**Opción B: Linked Server (postgres_fdw)**
```sql
-- Configurar Foreign Data Wrapper
CREATE EXTENSION postgres_fdw;
CREATE SERVER mssql_server FOREIGN DATA WRAPPER postgres_fdw ...;

-- Query transparente
SELECT p.*, c.NombreCliente
FROM datiadb_pedidos p
JOIN mssql_server.dbo.Clientes c ON p.CodigoCliente = c.Codigo;
```

## Ventajas

✅ **Ahorro de espacio**: Tablas grandes no se duplican  
✅ **Sincronización rápida**: Menos datos a migrar  
✅ **Datos en tiempo real**: Siempre consulta MSSQL directamente  
✅ **Flexibilidad**: Decide qué tablas migrar

## Limitaciones

⚠️ **Rendimiento**: JOINs entre PostgreSQL y MSSQL pueden ser lentos  
⚠️ **Complejidad**: Queries híbridas requieren lógica adicional  
⚠️ **Dependencia**: Requiere conexión activa a MSSQL

## Implementación Técnica

### Backend

**Archivos Modificados**:
1. `datia/models/semantic.py` - Campo `is_virtual`
2. `datia/migrations/0027_datasource_is_virtual.py` - Migración
3. `datia/api/introspection_endpoints.py` - 3 endpoints
4. `datia/services/etl_service.py` - Skip virtual tables

### Frontend

**Archivo**: `datia/templates/datia/components/tab_auto.html`

**Cambios**:
1. Checkbox `chk-is-virtual` en formulario de mapeo
2. Badge 📡 en lista de tablas mapeadas
3. JavaScript para guardar/cargar estado

### API

**Endpoint**: `POST /api/semantic/mapping`

**Payload**:
```json
{
  "empresa_id": "DEMO",
  "table_name": "Clientes",
  "business_name": "Clientes",
  "table_description": "Maestro de clientes",
  "is_virtual": true,  // ← NF-016
  "fields": [...]
}
```

## Testing

### Test Manual 1: Mapeo

```
1. Ir a Auto Entreno → Mapeo de Datos
2. Seleccionar tabla "Clientes"
3. Marcar "📡 Tabla Virtual"
4. Mapear campos: Codigo, Nombre, NIF
5. Guardar
6. Verificar badge 📡 en sidebar
```

### Test Manual 2: Sincronización

```
1. Ir a Auto Entreno → Sincronización
2. Ejecutar sincronización
3. Verificar mensaje: "📡 Clientes: Tabla virtual. Omitiendo..."
4. Confirmar que tabla NO existe en PostgreSQL
```

### Test Manual 3: Relaciones

```
1. Ir a Auto Entreno → Relaciones
2. Crear: CabeceraPedido.CodigoCliente → Clientes.Codigo
3. Guardar
4. Verificar que relación se guarda correctamente
```

## Generación de Consultas Sintéticas (AI Training)

El generador de consultas sintéticas (`SyntheticSQLGenerator`) tiene un tratamiento especial para tablas virtuales:

1. **Validación**: Se realiza contra MSSQL usando `SET FMTONLY ON`.
2. **Sintaxis**:
   - Usa `TOP 50` en lugar de `LIMIT 50`.
   - **GROUP BY**: Debe usar nombres explícitos de columnas (`GROUP BY "Columna"`) en lugar de ordinales (`GROUP BY 1`), ya que MSSQL no soporta ordinales de forma segura/predeterminada.
   - **Identifiers**: Se usan comillas dobles (`"Table"`, `"Column"`) asumiendo `QUOTED_IDENTIFIER ON`.

## Referencias

- **NF-016**: Funcionalidad de Tablas Virtuales
- **Patrón 03**: Auto Entreno (mapeo de datos)
- **Patrón 10**: AI Service (generación de SQL)

## Estado

**Implementado**: Backend + UI de Mapeo (100%)
**Validado**: Generación de queries sintéticas para tablas virtuales (2025-12-29)
