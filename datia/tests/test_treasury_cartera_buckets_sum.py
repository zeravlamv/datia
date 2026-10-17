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
        self.rows = rows
        self.last_filter = {}
    def filter(self, **kwargs):
        self.last_filter.update(kwargs)
        return self
    def exclude(self, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return self.rows
    def aggregate(self, **kwargs):
        if self.last_filter.get('tipo_efecto') == 'C':
            total = sum(r['importe'] for r in self.rows if r['tipo_efecto'] == 'C')
            return {'total': total}
        total = sum(r['importe'] for r in self.rows)
        return {'total': total}

class TestCarteraBucketsSum(unittest.TestCase):
    def test_sum_buckets_equals_total_cobros(self):
        today = date.today()
        rows = [
            {'fecha_vencimiento': today + timedelta(days=15), 'importe': 100.0, 'importe_cobrado': 0.0, 'tipo_efecto': 'C', 'codigo_titular': 'A'},
            {'fecha_vencimiento': today + timedelta(days=45), 'importe': 200.0, 'importe_cobrado': 0.0, 'tipo_efecto': 'C', 'codigo_titular': 'B'},
            {'fecha_vencimiento': today + timedelta(days=75), 'importe': 300.0, 'importe_cobrado': 0.0, 'tipo_efecto': 'C', 'codigo_titular': 'C'},
            {'fecha_vencimiento': today - timedelta(days=120), 'importe': 400.0, 'importe_cobrado': 0.0, 'tipo_efecto': 'C', 'codigo_titular': 'D'},
        ]
        svc = FinancialService()
        with patch('datia.services.financial_service.DatiaCarteraEfectos') as MockModel, \
             patch.object(FinancialService, '_get_saldo_pattern', return_value=0.0), \
             patch.object(FinancialService, '_get_saldo_grupo', return_value=1.0):
            MockModel.objects.filter.return_value = _FakeQS(rows)
            data = svc.get_treasury_snapshot(empresa=1, ejercicio=2024)
            kpis = data.get('kpis', {})
            aging = data.get('aging', {})
            buckets = aging.get('receivables_cartera', {})
            total_buckets = sum(buckets.values())
            self.assertAlmostEqual(total_buckets, kpis.get('cartera_importe_cobros', 0.0), places=2)

if __name__ == '__main__':
    unittest.main()
