import os
import sys
import unittest
from unittest.mock import patch
from datetime import date, timedelta
import django

# Setup Django environment for model imports
sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.financial_service import FinancialService

class _FakeQS:
    def __init__(self):
        self.last_filter = {}
    def filter(self, **kwargs):
        self.last_filter.update(kwargs)
        return self
    def exclude(self, **kwargs):
        return self
    def values(self, *args, **kwargs):
        return []
    def aggregate(self, **kwargs):
        if self.last_filter.get('tipo_efecto') == 'C' and 'fecha_vencimiento__lt' in self.last_filter:
            return {'total': 100.0}
        if self.last_filter.get('tipo_efecto') == 'C':
            return {'total': 600.0}
        if self.last_filter.get('tipo_efecto') == 'P':
            return {'total': 400.0}
        return {'total': 1000.0}

class TestTesoreriaEfectos(unittest.TestCase):
    def test_importes_cartera_suma(self):
        svc = FinancialService()
        with patch('datia.services.financial_service.DatiaCarteraEfectos') as MockModel, \
             patch.object(FinancialService, '_get_saldo_pattern', return_value=0), \
             patch.object(FinancialService, '_get_saldo_grupo', return_value=1):
            MockModel.objects.filter.return_value = _FakeQS()
            data = svc.get_treasury_snapshot(empresa=1, ejercicio=2024)
            kpis = data.get('kpis', {})
            self.assertAlmostEqual(kpis.get('cartera_importe_total', 0), 1000.0, places=2)
            self.assertAlmostEqual(kpis.get('cartera_importe_cobros', 0), 600.0, places=2)
            self.assertAlmostEqual(kpis.get('cartera_importe_pagos', 0), 400.0, places=2)
            self.assertAlmostEqual(kpis.get('cartera_importe_overdue_90', 0), 100.0, places=2)

if __name__ == '__main__':
    unittest.main()
