import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import TestCase

from datia.services.ai.nlq_catalog import informe_adelantado
from datia.services.ai.reglas_negocio import decidir
from datia.services.ai_service import IAService


class TestAICatalogMinimo(TestCase):
    def setUp(self):
        self.svc = IAService()

    def _assert_report(self, resp):
        self.assertIsInstance(resp, dict)
        self.assertIn('type', resp)
        self.assertIn('answer', resp)
        self.assertIn('text', resp)
        self.assertEqual(resp['answer'], resp['text'])

    def test_top_clientes(self):
        self.assertIsNone(informe_adelantado('mejores clientes del año'))

    def test_top_productos(self):
        self.assertIsNone(informe_adelantado('mejores productos del año'))

    def test_ventas_mensual(self):
        self.assertIsNone(informe_adelantado('ventas por mes'))

    def test_margen_mensual(self):
        self.assertIsNone(informe_adelantado('margen mensual'))

    def test_finanzas_resumen(self):
        decision = decidir('analisis financiero del 2025', ejercicio=2024)
        self.assertEqual(decision['informe'], 'finanzas.resumen_ejercicio')
        self.assertEqual(decision['anio'], 2025)
        self.assertIsNone(decidir('resumen 2024', ejercicio=2025))
        self.assertIsNone(informe_adelantado('resumen financiero'))

    def test_finanzas_per100(self):
        self.assertEqual(decidir('coste por cada 100', ejercicio=2025)['informe'], 'finanzas.per100')

    def test_tesoreria_presupuesto_y_ratios(self):
        self.assertEqual(decidir('tesoreria', ejercicio=2025)['informe'], 'tesoreria.resumen')
        self.assertEqual(decidir('presupuesto', ejercicio=2025)['informe'], 'presupuestos.comparativa')
        self.assertEqual(decidir('ratios', ejercicio=2025)['informe'], 'financiera.ratios')

