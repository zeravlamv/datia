import os
import sys
import time
import unittest
from unittest.mock import patch
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.financial_service import FinancialService

class _FakeQSFlat:
    def __init__(self, n=50):
        self.n = n
    def filter(self, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return self
    def annotate(self, **kwargs):
        rows = []
        for i in range(self.n):
            rows.append({'cuenta': f'43000{i:02d}', 'total': float(i+1) * 10.0})
        return rows

class TestReceivablesBreakdownFlat(unittest.TestCase):
    def test_flat_expansion_speed_and_consistency(self):
        svc = FinancialService()
        with patch('datia.services.financial_service.DatiaAcumuladosConta') as MockModel, \
             patch.object(FinancialService, '_get_saldo_pattern', return_value=12750.0), \
             patch.object(FinancialService, '_get_account_desc', return_value='Desc'):
            MockModel.objects.filter.return_value = _FakeQSFlat(n=50)
            t0 = time.perf_counter()
            res = svc.get_receivables_breakdown_flat(empresa=1, ejercicio=2024, parent='430')
            elapsed = time.perf_counter() - t0
            self.assertLess(elapsed, 1.0)
            rows = res.get('rows', [])
            self.assertEqual(len(rows), 50)
            self.assertTrue(res.get('validation', {}).get('matched'))

if __name__ == '__main__':
    unittest.main()
