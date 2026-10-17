# Importador de Cuentas Bancarias (MSSQL → Postgres)

## Objetivo
- Generar y mantener cuentas bancarias por empresa a partir de `bancos` y `bancosconta` (MSSQL).
- Asegurar identidad, deduplicación, transacciones y reporte.

## Flujo
1. Extracción MSSQL: lectura directa o `sp_datia_pool_extract_accounts`.
2. Transformación: normalización IBAN y `CodigoCuenta` (erp_account_code), mapeo de banco.
3. Carga Postgres: upsert de `BankingBank` y `BankingAccount`, transacción por empresa.
4. Reporte JSON por empresa: creados, actualizados, omitidos, errores.

## Campos
- BankingBank: `empresa`, `bank_code`, `nombre`, `activo`.
- BankingAccount: `empresa`, `bank`, `iban`, `erp_account_code`, `alias`, `uso`, `activo`.

## Identidad y Únicos
- Principal: `(empresa, iban)` cuando `iban` existe.
- Secundario: `(empresa, bank, erp_account_code)` cuando `iban` es nulo.

## Ejecución
- Comando: `python manage.py datia_import_bank_accounts --empresa <id|all> [--dry-run]`.
- Programación: Windows Task Scheduler invocando el comando.

## Pruebas
- `tests/test_banking_import_accounts.py`: creación con IBAN, creación sin IBAN por `erp_account_code`, actualización mínima.

## SQL Opcional
- `scripts/mssql/sp_datia_pool_extract_accounts.sql`: procedimiento para extracción encapsulada.
