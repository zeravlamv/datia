# Patrón: Sincronización Selectiva

Este patrón define la funcionalidad de sincronización selectiva que permite al usuario elegir qué tipo de tablas sincronizar durante el proceso de materialización y entrenamiento, optimizando tiempos y recursos.

## 1. Contexto

El proceso de sincronización ETL en Datia maneja **dos tipos** de tablas con propósitos diferentes:

### **Tablas Estándar** (`metrics_*`)
- **Descripción**: Tablas agregadas automáticas para dashboards BI
- **Prefijo**: `metrics_totales_*`
- **Volumen típico**: ~35,000 registros
- **Propósito**: Alimentar widgets de Actualidad/Histórico
- **Generación**: Automática por el ETL Service
- **Ejemplos**:
  - `metrics_totales_empresa_ejercicio`
  - `metrics_totales_empresa_ejercicio_mes`
  - `metrics_totales_empresa_ejercicio_cliente`
  - `metrics_totales_empresa_ejercicio_articulo`

### **Tablas Entrenadas** (`DatiaDB_*`)
- **Descripción**: Tablas mapeadas manualmente por el usuario en Auto Entreno
- **Prefijo**: `datiadb_*`
- **Volumen típico**: ~10,000 registros (variable según mapeo)
- **Propósito**: Consultas AI específicas basadas en mapeo semántico
- **Generación**: Manual (usuario define contexto, campos, roles)
- **Ejemplos**:
  - `datiadb_CabeceraPedidoCliente`
  - `datiadb_LineasAlbaran`
  - `datiadb_Facturas`

---

## 2. Problema

**Situación Original**:
- El botón "Finalizar y Sincronizar" sincronizaba **AMBOS** tipos de tablas siempre
- Tiempo total: ~2-3 minutos para ~45,000 registros
- **Ineficiencia**: Si solo se modificó un mapeo (ej: añadir campo), regenerar las 35K líneas de métricas era innecesario

**Necesidad del Usuario**:
> "Solo he entrenado CabeceraPedidoCliente que tiene 10 mil registros, ¿por qué tarda tanto y procesa 45 mil líneas?"

---

## 3. Solución: Selector de Tipo de Sincronización

### **3.1 Ubicación en UI**

**Sección**: Auto Entreno → "Materializar y Entrenar"  
**Posición**: Entre la descripción y el botón "Finalizar y Sincronizar"

### **3.2 Opciones Disponibles**

```
┌────────────────────────────────────────────────┐
│          Tipo de Sincronización                │
├────────────────────────────────────────────────┤
│  ◉ 📊 Todas                                    │
│     Estándar + Entrenadas                      │
│                                                 │
│  ○ 🎓 Solo Entrenadas                          │
│     datiadb_* (~10K)                           │
│                                                 │
│  ○ 📈 Solo Estándar                            │
│     Metrics_* (~35K)                           │
└────────────────────────────────────────────────┘
```

#### **Opción 1: 📊 Todas** (Predeterminada)
- **Tablas**: Estándar + Entrenadas
- **Volumen**: ~45,000 registros
- **Tiempo**: ~2-3 minutos
- **Uso recomendado**:
  - Primera sincronización inicial
  - Después de cambios en configuración de empresa
  - Cuando se necesita actualización completa

#### **Opción 2: 🎓 Solo Entrenadas**
- **Tablas**: SOLO datiadb_*
- **Volumen**: ~10,000 registros (variable)
- **Tiempo**: ~30 segundos ⚡
- **Uso recomendado**:
  - Después de añadir/modificar mapeos en Auto Entreno
  - Después de añadir nuevos campos a tabla entrenada
  - Actualización rápida de contexto de tabla
  - Testing de consultas AI con datos frescos

#### **Opción 3: 📈 Solo Estándar**
- **Tablas**: SOLO metrics_*
- **Volumen**: ~35,000 registros
- **Tiempo**: ~1.5 minutos
- **Uso recomendado**:
  - Actualización mensual de dashboards BI
  - Nuevo ejercicio fiscal cerrado
  - Corrección de datos de métricas sin tocar tablas entrenadas

---

## 4. Implementación Técnica

### **4.1 Frontend (tab_auto.html)**

#### Selector HTML con Radio Buttons:
```html
<div style="margin-bottom: 2rem;">
    <label>Tipo de Sincronización</label>
    <div style="display: flex; gap: 1rem;">
        <label class="sync-type-option">
            <input type="radio" name="sync-type" value="all" checked>
            <span>📊 Todas<br>Estándar + Entrenadas</span>
        </label>
        <label class="sync-type-option">
            <input type="radio" name="sync-type" value="trained">
            <span>🎓 Solo Entrenadas<br>datiadb_* (~10K)</span>
        </label>
        <label class="sync-type-option">
            <input type="radio" name="sync-type" value="standard">
            <span>📈 Solo Estándar<br>Metrics_* (~35K)</span>
        </label>
    </div>
</div>
```

#### Estilos CSS:
```css
.sync-type-option {
    padding: 0.75rem;
    background: rgba(0, 0, 0, 0.3);
    border: 2px solid #3f3f46;
    border-radius: 8px;
    transition: all 0.3s ease;
}

.sync-type-option:has(input:checked) {
    background: rgba(16, 185, 129, 0.15);
    border-color: #10b981;
}
```

#### JavaScript (performSync):
```javascript
// Leer opción seleccionada
const syncTypeRadio = document.querySelector('input[name="sync-type"]:checked');
const syncType = syncTypeRadio ? syncTypeRadio.value : 'all';

// Construir query string con parámetros
const empParam = currEmpresa ? `empresa_id=${currEmpresa}` : '';
const syncParam = `sync_type=${syncType}`;
const queryString = [empParam, syncParam].filter(p => p).join('&');

// Llamar al endpoint
const res = await fetch(`/api/etl/sync?${queryString}`, { method: 'POST' });
```

---

### **4.2 Backend Endpoint (etl_endpoints.py)**

#### Endpoint actualizado:
```python
@router.post("/sync")
def trigger_sync(request, 
                 empresa_id: str = Query(None), 
                 table_name: str = Query(None), 
                 sync_type: str = Query("all")):
    """
    Parámetros (Via Query Params):
        empresa_id: Filtro opcional por empresa
        table_name: Filtro opcional por tabla (granular)
        sync_type: 'all', 'trained' (datiadb_*), 'standard' (metrics_*)
    """
    # Debug logs para trazabilidad
    print(f"🔍 DEBUG [trigger_sync] - empresa_id: {empresa_id}")
    print(f"🔍 DEBUG [trigger_sync] - sync_type: {sync_type}")

    job_id = str(uuid.uuid4())
    # ... (resto igual)
```

### **4.4 Gestión de Errores y UX (Toasts)**

Se ha reemplazado el uso de `alert()` y `confirm()` nativos por un sistema de notificaciones **Toast** no bloqueante (`showToast`).

**Comportamiento Visual:**
- **Éxito**: Toast verde con icono ✅ (ej: "Sincronización iniciada")
- **Error**: Toast rojo con icono ❌ (ej: "Error de conexión")
- **Info/Warning**: Toast amarillo/azul con icono ⚠️/ℹ️ (ej: "Resincronizando tabla...")

**Implementación Frontend:**
```javascript
if (typeof showToast === 'function') {
    showToast("✅ Todas las tablas ya están sincronizadas.");
}
```
```

---

### **4.3 Servicio ETL (etl_service.py)**

#### Lógica de filtrado en sync_all_years_for_empresa_generator:

```python
def sync_all_years_for_empresa_generator(self, empresa_id, 
                                          filter_table=None, 
                                          sync_type="all"):
    """
    Args:
        sync_type: 'all', 'trained', 'standard'
    """
    # 1. Estructura base
    yield send_progress("Setup", 5, "Sincronizando estructura base...")
    self.sync_structure()
    
    # 2. Determinar qué sincronizar
    should_sync_standard = sync_type in ['all', 'standard']
    should_sync_trained = sync_type in ['all', 'trained']
    
    # Override si hay filter_table
    if filter_table:
        should_sync_standard = False
    
    # 3. Tablas Estándar (metrics_*)
    if should_sync_standard:
        years = self.get_available_exercises(empresa_id)
        for year in years:
            yield send_progress("Syncing", p, 
                f"Sincronizando Tablas Estándar - Ejercicio {year}...")
            for progress in self.sync_mssql_sales_generator(empresa_id, year):
                yield progress
    else:
        yield send_progress("Syncing", 70, 
            "Omitiendo tablas estándar (solo entrenadas)...")
    
    # 4. Tablas Entrenadas (DatiaDB_*)
    if should_sync_trained:
        yield send_progress("DynamicSync", 75, 
            "Iniciando sincronización de tablas entrenadas...")
        for progress in self.sync_dynamic_tables_generator(empresa_id):
            yield progress
    else:
        yield send_progress("DynamicSync", 95, 
            "Omitiendo tablas entrenadas (solo estándar)...")
    
    yield send_progress("Done", 100, "Completado")
```

---

### **4.5 Requisito Obligatorio: Baseline Inicial**

- La primera migración por dominio y ejercicio debe ser completa (baseline), nunca incremental.
- Dominios afectados: ventas, compras, financiera, cartera y existencias.
- Validación: el sistema comprueba presencia de registros en las tablas destino por empresa y ejercicio. Si no hay baseline, bloquea las rutas incrementales y fuerza la migración completa en el flujo estándar.
- Endpoints incrementales: requieren baseline previo; sin baseline devuelven error 400 con mensaje explicativo.
- Comportamiento en ETL:
  - Si no hay baseline, se ejecutan los generadores “full” correspondientes.
  - Si hay baseline, se permiten los generadores incrementales.
- Objetivo: garantizar consistencia de datos antes de aplicar actualizaciones selectivas.

---

## 5. Mensajes de Progreso

### **Opción: Todas**
```
Setup (5%):      Sincronizando estructura base...
Syncing (10%):   Sincronizando Tablas Estándar - Ejercicio 2024...
Syncing (40%):   Sincronizando Tablas Estándar - Ejercicio 2023...
DynamicSync (75%): Iniciando sincronización de tablas entrenadas...
DynamicSync (85%): Procesando datiadb_CabeceraPedidoCliente...
Done (100%):     Sincronización de 001 completada.
```

### **Opción: Solo Entrenadas**
```
Setup (5%):      Sincronizando estructura base...
Syncing (70%):   Omitiendo tablas estándar (solo entrenadas)...
DynamicSync (75%): Iniciando sincronización de tablas entrenadas...
DynamicSync (85%): Procesando datiadb_CabeceraPedidoCliente...
Done (100%):     Sincronización de 001 completada.
```

### **Opción: Solo Estándar**
```
Setup (5%):      Sincronizando estructura base...
Syncing (10%):   Sincronizando Tablas Estándar - Ejercicio 2024...
Syncing (40%):   Sincronizando Tablas Estándar - Ejercicio 2023...
DynamicSync (95%): Omitiendo tablas entrenadas (solo estándar)...
Done (100%):     Sincronización de 001 completada.
```

---

## 6. Casos de Uso Típicos

### **Escenario 1: Primera Configuración**
**Usuario**: Acaba de mapear `CabeceraPedidoCliente` por primera vez  
**Acción**: Seleccionar **📊 Todas**  
**Razón**: Necesita generar tanto métricas BI como tabla entrenada  
**Tiempo**: ~2-3 minutos

### **Escenario 2: Añadir Campo a Tabla Entrenada**
**Usuario**: Añadió campo "Estado" a `CabeceraPedidoCliente`  
**Acción**: Seleccionar **🎓 Solo Entrenadas**  
**Razón**: Solo necesita regenerar datiadb_*, las métricas siguen válidas  
**Tiempo**: ~30 segundos (6x más rápido)

### **Escenario 3: Nuevo Mes Cerrado**
**Usuario**: Cerró el mes de diciembre, quiere actualizar dashboards  
**Acción**: Seleccionar **📈 Solo Estándar**  
**Razón**: Solo necesita actualizar métricas BI, las tablas entrenadas no cambiaron  
**Tiempo**: ~1.5 minutos

### **Escenario 4: Testing de Consultas AI**
**Usuario**: Quiere probar consultas AI con datos más recientes  
**Acción**: Seleccionar **🎓 Solo Entrenadas**  
**Razón**: Actualización rápida para testing sin regenerar todo  
**Tiempo**: ~30 segundos

---

## 7. Compatibilidad

### **Con filter_table (Modo Granular)**:
- ✅ Compatible
- Si `filter_table` está presente, SIEMPRE omite tablas estándar
- Útil para sincronizar una sola tabla específica

### **Con empresa_id**:
- ✅ Compatible
- Filtra por empresa antes de aplicar tipo de sincronización

### **Con Checkbox "Activo"**:
- ✅ **Lógica inversa implementada**
- `is_active = True` → Tabla ya sincronizada, **SE SALTA**
- `is_active = False` → Tabla necesita sincronización, **SE INCLUYE**
- `last_sync_at = NULL` → Nunca sincronizada, **SE INCLUYE**

**Flujo:**
1. Usuario selecciona "🎓 Solo Entrenadas"
2. Sistema filtra tablas con `is_active=False` O `last_sync_at IS NULL`
3. Sincroniza solo esas tablas
4. Al terminar, marca `is_active=True` y actualiza `last_sync_at`
5. Usuario puede desmarcar checkbox para forzar re-sincronización

**Uso típico**:
```
┌─────────────────────────────┐
│ ☑ CabeceraPedido (SYNC ✓)  │ ← is_active=True, NO sincroniza
└─────────────────────────────┘

Usuario desmarca checkbox:

┌─────────────────────────────┐
│ ☐ CabeceraPedido           │ ← is_active=False, SÍ sincroniza
└─────────────────────────────┘
```

### **Retrocompatibilidad**:
- ✅ Compatible
- Si no se envía `sync_type`, usa `"all"` por defecto
- Código antiguo sigue funcionando sin cambios

---

## 8. Mejoras Futuras

### **8.1 Persistencia de Selección**
**Descripción**: Guardar última opción usada en `localStorage`  
**Beneficio**: Usuario no tiene que reseleccionar cada vez  
**Código sugerido**:
```javascript
// Al seleccionar
localStorage.setItem('datia-sync-type', syncType);

// Al cargar página
const savedType = localStorage.getItem('datia-sync-type') || 'all';
document.querySelector(`input[value="${savedType}"]`).checked = true;
```

### **8.2 Estimación de Registros**
**Descripción**: Mostrar estimación de registros antes de sincronizar  
**Beneficio**: Usuario sabe qué esperar  
**Ejemplo UI**:
```
🎓 Solo Entrenadas
datiadb_* (~10,247 registros estimados)
Tiempo estimado: 30 segundos
```

### **8.3 Sincronización Programada**
**Descripción**: Permitir agendar sincronizaciones automáticas  
**Beneficio**: Automatización de actualizaciones nocturnas  
**Ejemplo**:
```
Sincronizar automáticamente:
○ Nunca
○ Diariamente (Solo Estándar)
○ Al cerrar mes (Todas)
```

---

## 9. Archivos Técnicos

### **Frontend**:
- `datia/templates/datia/components/tab_auto.html` (líneas 247-276, 1233-1237)

### **Backend**:
- `datia/api/etl_endpoints.py` (trigger_sync, full_sync_worker)
- `datia/services/etl_service.py` (sync_all_years_for_empresa_generator)

### **Modelos**:
- `datia/models/semantic.py` (DataSource, DataField)

---

## REVIEW

### **Performance**
- ✅ Reducción de tiempo: 6x más rápido para "Solo Entrenadas"
- ✅ Menor carga en base de datos
- ✅ Feedback claro al usuario sobre qué se está procesando

### **UX**
- ✅ Interfaz clara y visual con iconos distintivos
- ✅ Opción predeterminada segura ("Todas")
- ✅ Descripciones contextuales con estimaciones

### **Código**
- ✅ Retrocompatible con código existente
- ✅ Compatible con otras features (filter_table, empresa_id)
- ✅ Mensajes de progreso específicos por tipo

---

**Versión**: 1.0  
**Fecha**: 2024-12-24  
**Implementado en**: v2.8.0
