# 12 - Pool Bancario

## Descripción
Submódulo de Financiera para la gestión del “Pool Bancario”: límites, disposición, disponibilidad, concentración por banco/producto y cronograma de vencimientos. Los datos se sustentan en PostgreSQL; MSSQL permanece en modo lectura. La empresa es siempre entero en todas las operaciones y tablas.

## Arquitectura
- Backend (API):
  - Router: `/api/financial` con endpoints del pool bajo `/pool/*`.
  - Endpoints lectura:
    - `GET /api/financial/pool/summary?empresa=&ejercicio=`
    - `GET /api/financial/pool/concentration?empresa=&ejercicio=`
    - `GET /api/financial/pool/maturities?empresa=&horizon=12`
  - Endpoints escritura (autenticados):
    - `GET/POST/PUT/DELETE /api/financial/pool/banks`
    - `GET/POST/PUT/DELETE /api/financial/pool/instruments`
    - `GET/POST/DELETE /api/financial/pool/instruments/{id}/accounts`
- Modelos (Postgres):
  - `BankingBank(empresa, nombre, swift?, rating?, contacto{}, activo)`  
  - `BankingAccount(empresa, bank, iban, alias?, uso?, activo)`  
  - `BankingInstrument(empresa, bank, account?, tipo, producto?, fecha_inicio?, fecha_fin?, renovable, estado, limite, base, diferencial, com_apertura, com_disponibilidad, com_no_disposicion, gastos_fijos, garantia{}, covenants{}, notas?)`
  - `BankingInstrumentAccountMap(empresa, instrument, cuenta_prefix, prioridad)`
  - `BankingAmortization(empresa, instrument, fecha_cuota, principal, interes, cuota, pendiente)`
- Servicios:
  - `BankingService.get_summary(empresa, ejercicio)`
  - `BankingService.get_concentration(empresa, ejercicio)`
  - `BankingService.get_maturities(empresa, horizon)`
- Cálculo “dispuesto”:
  - Suma de `DatiaAcumuladosConta.saldo` por prefijos mapeados; se usa `abs()` para normalizar signos en cuentas de pasivo.

## UI (Separada)
- HTML: `tab_pool_bancario.html` (contenedores KPI, gráfico concentración, calendario/heatmap de vencimientos).
- JS: `pool_bancario.js` (fetch y render de summary/concentration/maturities; formato € con 2 decimales y miles).
- CSS: `pool_bancario.css` (bordes con color de acento y glow al seleccionar).

## Seguridad y Reglas
- Escritura autenticada obligatoria en bancos, instrumentos y mapeos.
- Validaciones:
  - `fecha_inicio` ≤ `fecha_fin` cuando ambas existan.
  - `cuenta_prefix`: numérico 3–12 dígitos.
  - `empresa`: entero en filtros y modelos.
- Formato monetario:
  - 2 decimales por defecto.
- MSSQL solo consulta; la agregación y modelos residen en Postgres.

## NEW
1. Subpestaña “Pool Bancario” (HTML/JS/CSS separados) con:
   - Tarjetas KPI: límite total, dispuesto, disponible y % de utilización global y por banco/tipo.
   - Gráfica de concentración (Top‑1/Top‑3) con ECharts (renderer SVG).
   - Calendario/heatmap de vencimientos a 12 meses.
2. Filtro opcional “hasta_mes” en `/pool/summary` y `/pool/concentration` para cortes intra‑ejercicio.
3. CRUD de cuentas bancarias (BankingAccount) vía endpoints si la UI lo requiere.
4. Preferencias de usuario: selección de banco/tipo por defecto persistidas en `UserPreference`.

## REVIEW
1. Homogeneizar modelos Banking* con `RawModelBase` si se desea alineación completa con financiera.
2. Revisión de índices: cubrir consultas frecuentes por `empresa`, `bank_id`, `tipo` y `fecha_cuota`.
3. Endurecer autorización (roles) para operaciones de escritura en admin de Django.
4. Performance sobre grandes planes de amortización: paginación y límites de horizonte.

## Verificación
- Unit tests para:
  - Suma de “dispuesto” por prefijos (incluye signos).
  - Concentración (Top‑1/Top‑3 y total).
  - Buckets de vencimientos por mes.
- UI:
  - Render correcto con 2 decimales y miles; interacción fluida.
  - Sin modales nativos y sin bloqueos UX.
