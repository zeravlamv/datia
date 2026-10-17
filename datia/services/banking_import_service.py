import logging
import re
from typing import List, Dict, Any, Tuple

from django.conf import settings
from django.db import transaction, connections

from datia.models.banking import BankingBank, BankingAccount
from datia.services.etl_service import ETLService

logger = logging.getLogger(__name__)


class BankingImportService:
    def __init__(self, mssql_db=None):
        if mssql_db:
            self.etl = ETLService(mssql_db=mssql_db)
        else:
            self.etl = ETLService()

    def ensure_banking_tables(self):
        cur = connections['default'].cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS datia_banking_bank (
                id SERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                bank_code VARCHAR(64),
                nombre VARCHAR(255) NOT NULL,
                swift VARCHAR(32),
                rating VARCHAR(32),
                contacto JSONB DEFAULT '{}'::jsonb,
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS datia_banking_account (
                id SERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                bank_id INTEGER NOT NULL REFERENCES datia_banking_bank(id) ON DELETE CASCADE,
                iban VARCHAR(34) NOT NULL,
                erp_account_code VARCHAR(64),
                alias VARCHAR(128),
                uso VARCHAR(64),
                activo BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

    def _normalize_iban(self, raw: str) -> str | None:
        if not raw:
            return None
        v = re.sub(r'\s+', '', str(raw)).upper()
        if len(v) < 15 or len(v) > 34:
            return None
        if not re.match(r'^[A-Z0-9]+$', v):
            return None
        return v

    def _normalize_code(self, raw: str) -> str | None:
        if raw is None:
            return None
        v = str(raw).strip().upper()
        if not v:
            return None
        if len(v) > 64:
            v = v[:64]
        return v

    def _get_mssql_cursor(self):
        return self.etl.get_connection().cursor()

    def _fetch_rows(self, empresa: int) -> List[Dict[str, Any]]:
        cur = self._get_mssql_cursor()
        bancos_rows = []
        cols_bancos = []
        try:
            cur.execute("SELECT * FROM bancos WHERE CodigoEmpresa = ?", (empresa,))
            cols_bancos = [d[0] for d in cur.description]
            bancos_rows = cur.fetchall()
        except Exception:
            bancos_rows = []
            cols_bancos = []
        conta_rows = []
        cols_conta = []
        try:
            cur.execute("SELECT * FROM bancosconta WHERE CodigoEmpresa = ?", (empresa,))
            cols_conta = [d[0] for d in cur.description]
            conta_rows = cur.fetchall()
        except Exception:
            conta_rows = []
            cols_conta = []
        try:
            cur.connection.close()
        except Exception:
            pass
        banks = []
        for r in bancos_rows or []:
            d = {}
            for idx, col in enumerate(cols_bancos):
                d[col] = r[idx]
            banks.append(d)
        accounts = []
        for r in conta_rows or []:
            d = {}
            for idx, col in enumerate(cols_conta):
                d[col] = r[idx]
            accounts.append(d)
        return [{"empresa": empresa, "banks": banks, "accounts": accounts}]

    def import_empresa(self, empresa: int, dry_run: bool = False) -> Dict[str, Any]:
        self.ensure_banking_tables()
        report = {
            "empresa": empresa,
            "banks_created": 0,
            "accounts_created": 0,
            "accounts_updated": 0,
            "accounts_skipped": 0,
            "errors": [],
        }
        data = self._fetch_rows(empresa)
        if not data:
            return report
        item = data[0]
        banks_src = item["banks"]
        acc_src = item["accounts"]
        bank_by_code: Dict[str, BankingBank] = {}
        name_map: Dict[str, BankingBank] = {}
        with transaction.atomic(using='default'):
            for b in banks_src:
                nombre = str(b.get("NombreBanco") or b.get("Nombre") or "").strip()
                if not nombre:
                    continue
                code = self._normalize_code(b.get("IdBanco") or b.get("CodigoBanco") or "")
                obj, created = BankingBank.objects.get_or_create(
                    empresa=empresa,
                    nombre=nombre,
                    defaults={"bank_code": code},
                )
                if not created and code and not obj.bank_code:
                    obj.bank_code = code
                    obj.save(update_fields=["bank_code"])
                if code:
                    bank_by_code[code] = obj
                name_map[nombre.upper()] = obj
            for c in acc_src:
                raw_iban = c.get("IBAN") or c.get("CuentaIBAN") or c.get("CCC")
                iban = self._normalize_iban(raw_iban)
                erp_code = self._normalize_code(c.get("CodigoCuenta") or c.get("CodigoCuentaERP") or "")
                if not iban and not erp_code:
                    report["accounts_skipped"] += 1
                    report["errors"].append("Sin IBAN ni CodigoCuenta")
                    continue
                bank_code = self._normalize_code(c.get("IdBanco") or c.get("CodigoBanco") or "")
                bank_name = str(c.get("NombreBanco") or "").strip()
                bank_obj = None
                if bank_code and bank_code in bank_by_code:
                    bank_obj = bank_by_code[bank_code]
                elif bank_name:
                    bank_obj = name_map.get(bank_name.upper())
                if not bank_obj:
                    report["accounts_skipped"] += 1
                    report["errors"].append(f"Banco no encontrado para cuenta {erp_code or iban}")
                    continue
                alias = str(c.get("AliasCuenta") or c.get("Descripcion") or "").strip()
                if not alias and iban:
                    alias = f"{bank_obj.nombre} · ****{iban[-4:]}"
                uso = str(c.get("TipoCuenta") or c.get("UsoCuenta") or "").strip()
                if iban:
                    acc, created = BankingAccount.objects.get_or_create(
                        empresa=empresa,
                        bank=bank_obj,
                        iban=iban,
                        defaults={
                            "erp_account_code": erp_code,
                            "alias": alias,
                            "uso": uso,
                            "activo": True,
                        },
                    )
                    if created:
                        report["accounts_created"] += 1
                    else:
                        changed = False
                        fields = []
                        if erp_code and acc.erp_account_code != erp_code:
                            acc.erp_account_code = erp_code
                            fields.append("erp_account_code")
                            changed = True
                        if alias and acc.alias != alias:
                            acc.alias = alias
                            fields.append("alias")
                            changed = True
                        if uso and acc.uso != uso:
                            acc.uso = uso
                            fields.append("uso")
                            changed = True
                        if changed:
                            acc.save(update_fields=fields)
                            report["accounts_updated"] += 1
                else:
                    if not erp_code:
                        report["accounts_skipped"] += 1
                        report["errors"].append("Cuenta sin IBAN y sin CodigoCuenta normalizable")
                        continue
                    acc = BankingAccount.objects.filter(
                        empresa=empresa,
                        bank=bank_obj,
                        erp_account_code=erp_code,
                        iban__isnull=True,
                    ).first()
                    if not acc:
                        acc = BankingAccount.objects.create(
                            empresa=empresa,
                            bank=bank_obj,
                            iban="",
                            erp_account_code=erp_code,
                            alias=alias,
                            uso=uso,
                            activo=True,
                        )
                        report["accounts_created"] += 1
                    else:
                        changed = False
                        fields = []
                        if alias and acc.alias != alias:
                            acc.alias = alias
                            fields.append("alias")
                            changed = True
                        if uso and acc.uso != uso:
                            acc.uso = uso
                            fields.append("uso")
                            changed = True
                        if changed:
                            acc.save(update_fields=fields)
                            report["accounts_updated"] += 1
            if dry_run:
                raise transaction.TransactionManagementError("Dry run rollback")
        return report
