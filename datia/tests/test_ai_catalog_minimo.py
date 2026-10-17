from django.test import TestCase

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
        resp = self.svc.generate_answer('mejores clientes del año', empresa=1, ejercicio=2025, request=None)
        self._assert_report(resp)
        self.assertEqual(resp.get('type'), 'report')
        self.assertEqual(resp.get('key'), 'ventas_top_clientes')

    def test_top_productos(self):
        resp = self.svc.generate_answer('mejores productos del año', empresa=1, ejercicio=2025, request=None)
        self._assert_report(resp)
        self.assertEqual(resp.get('type'), 'report')
        self.assertEqual(resp.get('key'), 'ventas_top_productos')

    def test_ventas_mensual(self):
        resp = self.svc.generate_answer('ventas por mes', empresa=1, ejercicio=2025, request=None)
        self._assert_report(resp)
        self.assertEqual(resp.get('type'), 'report')
        self.assertEqual(resp.get('key'), 'ventas_mensual')

    def test_margen_mensual(self):
        resp = self.svc.generate_answer('margen mensual', empresa=1, ejercicio=2025, request=None)
        self._assert_report(resp)
        self.assertEqual(resp.get('type'), 'report')
        self.assertEqual(resp.get('key'), 'margen_mensual')

    def test_finanzas_resumen(self):
        resp = self.svc.generate_answer('resumen financiero', empresa=1, ejercicio=2025, request=None)
        self._assert_report(resp)
        self.assertEqual(resp.get('type'), 'report')
        self.assertEqual(resp.get('key'), 'finanzas_resumen')

    def test_finanzas_per100(self):
        resp = self.svc.generate_answer('coste por cada 100', empresa=1, ejercicio=2025, request=None)
        self._assert_report(resp)
        self.assertEqual(resp.get('type'), 'report')
        self.assertEqual(resp.get('key'), 'finanzas_per100')

