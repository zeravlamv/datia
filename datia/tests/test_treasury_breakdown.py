import os
import sys
import unittest
from unittest.mock import patch
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.financial_service import FinancialService

class _FakeQS2:
    def __init__(self):
        pass
    def filter(self, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return self
    def annotate(self, **kwargs):
        return [{'cuenta': '4300001', 'total': 200.0}, {'cuenta': '4310001', 'total': 300.0}, {'cuenta': '432', 'total': 0.0}]

class TestReceivablesBreakdown(unittest.TestCase):
    def test_breakdown_structure(self):
        svc = FinancialService()
        with patch('datia.services.financial_service.DatiaAcumuladosConta') as MockModel, \
             patch.object(FinancialService, '_get_account_desc', return_value='Desc'):
            MockModel.objects.filter.return_value = _FakeQS2()
            res = svc.get_receivables_breakdown(empresa=1, ejercicio=2024, level=3)
            rows = res.get('rows', [])
            self.assertTrue(len(rows) >= 2)
            self.assertEqual(rows[0]['cuenta'], '431')
            self.assertEqual(rows[0]['descripcion'], 'Desc')
            self.assertTrue(isinstance(rows[0]['saldo'], float))

if __name__ == '__main__':
    unittest.main()
