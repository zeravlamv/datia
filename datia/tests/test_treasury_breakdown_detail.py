import os
import sys
import unittest
from unittest.mock import patch
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.financial_service import FinancialService

class _FakeQS3:
    def filter(self, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return self
    def annotate(self, **kwargs):
        return [
            {'cuenta': '4300001', 'total': 120.0},
            {'cuenta': '4300002', 'total': 80.0},
            {'cuenta': '4300003', 'total': -50.0},
        ]

class TestReceivablesBreakdownDetail(unittest.TestCase):
    def test_detail_rows(self):
        svc = FinancialService()
        with patch('datia.services.financial_service.DatiaAcumuladosConta') as MockModel, \
             patch.object(FinancialService, '_get_account_desc', return_value='Desc'):
            MockModel.objects.filter.return_value = _FakeQS3()
            res = svc.get_receivables_breakdown_detail(empresa=1, ejercicio=2024, parent='430', level=7)
            rows = res.get('rows', [])
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]['cuenta'], '4300001')
            self.assertTrue(isinstance(rows[0]['saldo'], float))
            self.assertEqual(rows[0]['descripcion'], 'Desc')

    def test_invalid_parent(self):
        svc = FinancialService()
        res = svc.get_receivables_breakdown_detail(empresa=1, ejercicio=2024, parent='x43', level=6)
        self.assertEqual(res.get('rows'), [])

if __name__ == '__main__':
    unittest.main()
