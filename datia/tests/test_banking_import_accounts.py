import os
import sys
import unittest
from unittest.mock import patch
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.banking_import_service import BankingImportService
from datia.models.banking import BankingBank, BankingAccount


class FakeCursor:
    def __init__(self, empresa, banks, accounts):
        self.empresa = empresa
        self._banks = banks
        self._accounts = accounts
        self._mode = None
        self.description = None

    def execute(self, sql, params=None):
        txt = sql.lower()
        if 'from bancos ' in txt:
            self._mode = 'banks'
            self.description = [('CodigoEmpresa',), ('IdBanco',), ('CodigoBanco',), ('Nombre',)]
        elif 'from bancosconta ' in txt:
            self._mode = 'conta'
            self.description = [('CodigoEmpresa',), ('IdBanco',), ('CodigoBanco',), ('IBAN',), ('CCC',), ('CodigoCuenta',), ('Descripcion',), ('AliasCuenta',), ('TipoCuenta',), ('Activo',)]
        else:
            self._mode = None
            self.description = []

    def fetchall(self):
        if self._mode == 'banks':
            rows = []
            for b in self._banks:
                rows.append((b.get('CodigoEmpresa'), b.get('IdBanco'), b.get('CodigoBanco'), b.get('Nombre')))
            return rows
        if self._mode == 'conta':
            rows = []
            for c in self._accounts:
                rows.append((c.get('CodigoEmpresa'), c.get('IdBanco'), c.get('CodigoBanco'), c.get('IBAN'), c.get('CCC'), c.get('CodigoCuenta'), c.get('Descripcion'), c.get('AliasCuenta'), c.get('TipoCuenta'), c.get('Activo')))
            return rows
        return []

    @property
    def connection(self):
        class Conn:
            def close(self_inner): 
                return None
        return Conn()


class TestBankingImportAccounts(unittest.TestCase):
    def setUp(self):
        BankingBank.objects.all().delete()
        BankingAccount.objects.all().delete()

    @patch('datia.services.banking_import_service.ETLService.get_connection')
    def test_create_account_with_iban(self, m_get_conn):
        empresa = 1
        banks = [{"CodigoEmpresa": empresa, "IdBanco": "001", "CodigoBanco": "001", "Nombre": "Banco A"}]
        accounts = [{"CodigoEmpresa": empresa, "IdBanco": "001", "CodigoBanco": "001", "IBAN": "ES76 2100 0418 4502 0005 1332", "CCC": None, "CodigoCuenta": "A-001", "Descripcion": "Cuenta Corriente", "AliasCuenta": "", "TipoCuenta": "Corriente", "Activo": 1}]
        cur = FakeCursor(empresa, banks, accounts)
        class Conn:
            def cursor(self_inner): return cur
        m_get_conn.return_value = Conn()
        svc = BankingImportService()
        rep = svc.import_empresa(empresa, dry_run=False)
        self.assertEqual(rep['accounts_created'], 1)
        self.assertEqual(BankingAccount.objects.filter(empresa=empresa).count(), 1)
        acc = BankingAccount.objects.filter(empresa=empresa).first()
        self.assertTrue(acc.iban.startswith('ES'))
        self.assertEqual(acc.erp_account_code, 'A-001')

    @patch('datia.services.banking_import_service.ETLService.get_connection')
    def test_create_without_iban_by_code(self, m_get_conn):
        empresa = 2
        banks = [{"CodigoEmpresa": empresa, "IdBanco": "010", "CodigoBanco": "010", "Nombre": "Banco B"}]
        accounts = [{"CodigoEmpresa": empresa, "IdBanco": "010", "CodigoBanco": "010", "IBAN": None, "CCC": None, "CodigoCuenta": "CC-B-01", "Descripcion": "Operativa", "AliasCuenta": "", "TipoCuenta": "Corriente", "Activo": 1}]
        cur = FakeCursor(empresa, banks, accounts)
        class Conn:
            def cursor(self_inner): return cur
        m_get_conn.return_value = Conn()
        svc = BankingImportService()
        rep = svc.import_empresa(empresa, dry_run=False)
        self.assertEqual(rep['accounts_created'], 1)
        acc = BankingAccount.objects.filter(empresa=empresa).first()
        self.assertEqual(acc.erp_account_code, 'CC-B-01')
        self.assertTrue(acc.iban in ('', None))

