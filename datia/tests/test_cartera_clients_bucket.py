import os
import sys
import unittest
from unittest.mock import patch
from datetime import date, timedelta
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.financial_service import FinancialService

class _FakeQS:
    def __init__(self, rows):
        self._rows = rows
    def filter(self, **kwargs):
        return self
    def exclude(self, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return self._rows

class TestCarteraClientsBucket(unittest.TestCase):
    def test_returns_rows_sorted_desc(self):
        today = date.today()
        rows = [
            {'fecha_vencimiento': today + timedelta(days=10), 'importe': 100.0, 'codigo_titular': '430A'},
            {'fecha_vencimiento': today + timedelta(days=20), 'importe': 300.0, 'codigo_titular': '430B'},
            {'fecha_vencimiento': today + timedelta(days=5), 'importe': 50.0, 'codigo_titular': '430C'},
        ]
        svc = FinancialService()
        with patch('datia.services.financial_service.DatiaCarteraEfectos') as MockModel, \
             patch('datia.services.financial_service.DatiaPlanCuentas') as MockPlan:
            MockModel.objects.filter.return_value = _FakeQS(rows)
            MockPlan.objects.filter.return_value = []
            res = svc.get_cartera_clients_bucket(empresa=1, ejercicio=2024, bucket='0-30')
            arr = res.get('rows', [])
            self.assertEqual(len(arr), 3)
            # Sorted descending by value: 300, 100, 50
            self.assertEqual([x['value'] for x in arr], [300.0, 100.0, 50.0])

if __name__ == '__main__':
    unittest.main()
