import os
import sys
import unittest
from unittest.mock import patch

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.db.models import Sum  # noqa

from datia.services.financial_service import FinancialService


class _FakeQS:
    def __init__(self, rows):
        self._rows = rows

    def values(self, *args, **kwargs):
        return self

    def annotate(self, **kwargs):
        return self._rows


class TestFinancialRatioDrilldown(unittest.TestCase):
    def setUp(self):
        self.svc = FinancialService()
        self.empresa = 1
        self.ejercicio = 2024

    def test_drilldown_returns_all_accounts_without_truncation(self):
        rows = [
            {'cuenta': f'410{str(i).zfill(3)}', 'd': 0.0, 'h': 100.0 + i}
            for i in range(75)
        ]
        with patch('datia.services.financial_service.DatiaAcumuladosConta') as MockModel, \
             patch.object(FinancialService, '_get_account_desc', return_value='Cuenta Test'), \
             patch.object(FinancialService, '_get_balance_prefixes', return_value=['41']):
            MockModel.objects.filter.return_value = _FakeQS(rows)
            data = self.svc.get_ratio_drilldown(self.empresa, self.ejercicio, 'endeudamiento')
            num_details = data['numerator']['details']
            den_details = data['denominator']['details']
            self.assertGreaterEqual(len(num_details), 75)
            self.assertGreaterEqual(len(den_details), 75)

    def test_recompute_ratio_with_selection_like_frontend_logic(self):
        data = {
            'ratio': 'endeudamiento',
            'numerator': {
                'details': [
                    {'code': '41A', 'value': 200.0},
                    {'code': '41B', 'value': 300.0},
                ]
            },
            'denominator': {
                'details': [
                    {'code': 'PN1', 'value': 100.0},
                    {'code': 'PN2', 'value': 400.0},
                ]
            },
        }

        def recompute(ratio, payload, numerator_codes, denominator_codes):
            num_selected = [r for r in payload['numerator']['details'] if r['code'] in numerator_codes]
            den_selected = [r for r in payload['denominator']['details'] if r['code'] in denominator_codes]
            num_total = sum(r.get('value') or 0.0 for r in num_selected)
            den_total = sum(r.get('value') or 0.0 for r in den_selected)
            ratio_val = 0.0
            if den_total:
                if ratio == 'endeudamiento':
                    ratio_val = (num_total / den_total) * 100.0
                else:
                    ratio_val = num_total / den_total
            return num_total, den_total, ratio_val

        num_total, den_total, ratio_val = recompute(
            'endeudamiento',
            data,
            {'41A', '41B'},
            {'PN1', 'PN2'},
        )
        self.assertAlmostEqual(num_total, 500.0, places=2)
        self.assertAlmostEqual(den_total, 500.0, places=2)
        self.assertAlmostEqual(ratio_val, 100.0, places=2)

        num_total2, den_total2, ratio_val2 = recompute(
            'endeudamiento',
            data,
            {'41A'},
            {'PN1', 'PN2'},
        )
        self.assertAlmostEqual(num_total2, 200.0, places=2)
        self.assertAlmostEqual(den_total2, 500.0, places=2)
        self.assertAlmostEqual(ratio_val2, 40.0, places=2)

        num_total3, den_total3, ratio_val3 = recompute(
            'endeudamiento',
            data,
            {'41A', '41B'},
            {'PN2'},
        )
        self.assertAlmostEqual(num_total3, 500.0, places=2)
        self.assertAlmostEqual(den_total3, 400.0, places=2)
        self.assertAlmostEqual(ratio_val3, 125.0, places=2)


if __name__ == '__main__':
    unittest.main()

