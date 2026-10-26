import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import SimpleTestCase

from datia.services.ai.plan_diccionario import NEGATIVA, encajar, responder
from datia.services.ai.presentacion import barras, variacion
from datia.services.query_builder import QueryBuilder


class TestEncajar(SimpleTestCase):
    def test_ventas_trimestrales_es_la_operacion_de_ventas(self):
        ficha = encajar('ventas trimestrales del 2025', 2024)
        self.assertEqual(ficha['operacion'], 'ventas por trimestre')
        self.assertEqual(ficha['ejercicio'], 2025)

    def test_compras_por_trimestre(self):
        ficha = encajar('compras por trimestre', 2025)
        self.assertEqual(ficha['operacion'], 'compras por trimestre')
        self.assertEqual(ficha['ejercicio'], 2025)

    def test_un_cliente_no_cabe_en_el_trimestre(self):
        ficha = encajar('ventas trimestrales del cliente acme', 2025)
        self.assertTrue(ficha['negativa'])

    def test_saldo_del_grupo_7(self):
        ficha = encajar('dame el saldo de las cuentas del grupo 7', 2025)
        self.assertEqual(ficha['operacion'], 'saldo de un grupo de cuentas')
        self.assertEqual(ficha['grupo'], '7')
        self.assertEqual((ficha['desde'], ficha['hasta']), (1, 12))

    def test_saldos_del_ultimo_trimestre_es_el_grupo(self):
        ficha = encajar('saldos de las cuentas del grupo 7 del ultimo trimestre del 2025', 2024)
        self.assertEqual(ficha['operacion'], 'saldo de un grupo de cuentas')
        self.assertEqual(ficha['grupo'], '7')
        self.assertEqual(ficha['ejercicio'], 2025)
        self.assertEqual((ficha['desde'], ficha['hasta']), (10, 12))
        self.assertEqual(ficha['corte'], 'último trimestre')

    def test_grupo_sin_numero_no_encaja(self):
        ficha = encajar('saldo de las cuentas del grupo', 2025)
        self.assertTrue(ficha['negativa'])

    def test_lista_de_diez_efectos_de_pago(self):
        ficha = encajar('muestra una lista de los 10 efectos pendientes de pago de mayor importe', 2025)
        self.assertEqual(ficha['operacion'], 'efectos pendientes de cobro o de pago')
        self.assertEqual(ficha['sentido'], 'P')
        self.assertEqual(ficha['modo'], 'lista')
        self.assertEqual(ficha['limite'], 10)
        self.assertEqual(ficha['titular'], '')

    def test_conteo_de_efectos_de_pago(self):
        ficha = encajar('cuantos efectos de pago siguen pendientes', 2025)
        self.assertEqual(ficha['modo'], 'conteo')
        self.assertEqual(ficha['sentido'], 'P')

    def test_efectos_sin_lado_no_encajan(self):
        ficha = encajar('cuantos efectos pendientes hay', 2025)
        self.assertTrue(ficha['negativa'])

    def test_facturas_pendientes_no_estan_cargadas(self):
        ficha = encajar('dime cuantas facturas tengo pendientes de cobrar', 2025)
        self.assertTrue(ficha['negativa'])
        salida = responder('dime cuantas facturas tengo pendientes de cobrar', 1, 2025)
        self.assertEqual(salida['reply']['text'], NEGATIVA)
        self.assertTrue(salida['reply']['dato_no_cargado'])
        self.assertNotIn('€', salida['reply']['text'])
        self.assertIn('factura', salida['reply']['origen']['falta'])

    def test_ventas_de_un_cliente_siguen_por_otra_regla(self):
        self.assertIsNone(encajar('ventas del cliente pepe', 2025))
        self.assertIsNone(encajar('top 10 clientes', 2025))

    def test_trimestrales_no_es_un_nombre_de_cliente(self):
        self.assertIsNone(QueryBuilder._extract_named_party('ventas trimestrales del 2025'))

    def test_las_barras_de_trimestre_no_son_meses(self):
        grafico = barras(
            ['T1', 'T2', 'T3', 'T4'],
            [{'label': '2025', 'data': [1, 2, 3, 4]}],
        )
        self.assertEqual(grafico['data']['labels'], ['T1', 'T2', 'T3', 'T4'])
        self.assertEqual(variacion(110, 100, 2024), 'vs 2024: +10,0 %')
        self.assertEqual(variacion(1000, 10, 2024), '')

    def test_el_plan_responde_antes_que_el_modelo(self):
        marca = {'reply': {'type': 'text', 'text': 'hecho', 'answer': 'hecho', 'source': 'plan'}}
        with patch('datia.services.ai.plan_diccionario.responder', return_value=marca) as plan:
            with patch('datia.services.ai.semantic_plan.SemanticPlan.desde_modelo') as modelo:
                salida = QueryBuilder._construir_consulta(
                    'ventas trimestrales del 2025',
                    {'empresa': 1, 'ejercicio': 2025, 'limit': 10},
                )
        plan.assert_called_once()
        modelo.assert_not_called()
        self.assertEqual(salida, marca)


if __name__ == '__main__':
    unittest.main()
