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

from datia.services.ai.lectura_completa import cubre, exigidos, grano_pedido
from datia.services.query_builder import QueryBuilder


class TestLecturaCompleta(SimpleTestCase):
    def test_ventas_trimestrales_piden_la_serie_y_la_operacion(self):
        pedido = exigidos('Ventas trimestrales', ejercicio=2025)
        self.assertIn('grano:trimestre-serie', pedido)
        self.assertIn('operacion:ventas por trimestre', pedido)

    def test_el_total_del_ano_no_cubre_el_trimestre(self):
        total = {
            'type': 'table',
            'sql': 'SELECT SUM(t1."importeneto") AS val FROM "datiadb_cabeceraalbarancliente" t1',
            'lectura': {'plan': {'grano': 'ejercicio'}},
            'vinculo': 'sola',
        }
        self.assertFalse(cubre('Ventas trimestrales', total, ejercicio=2025))

    def test_el_plan_del_diccionario_cubre_las_ventas_trimestrales(self):
        plan = {'reply': {'type': 'report', 'text': 'T1 1 €', 'answer': 'T1 1 €', 'source': 'plan'}}
        self.assertTrue(cubre('Ventas trimestrales', plan, ejercicio=2025))

    def test_las_ventas_del_ano_no_exigen_otro_corte(self):
        self.assertEqual(exigidos('ventas del ejercicio', ejercicio=2025), frozenset())
        self.assertEqual(grano_pedido('ventas del ejercicio'), '')

    def test_el_ultimo_trimestre_es_un_filtro_y_lo_cubre_el_rango(self):
        pedido = exigidos('margen por cliente del ultimo trimestre', ejercicio=2025)
        self.assertIn('grano:trimestre-filtro', pedido)
        self.assertFalse(any(item.startswith('operacion:') for item in pedido))
        agrupado = {
            'type': 'table',
            'sql': 'SELECT cliente, SUM(importe) FROM t WHERE EXTRACT(MONTH FROM fecha) BETWEEN 10 AND 12',
        }
        self.assertTrue(cubre('margen por cliente del ultimo trimestre', agrupado, ejercicio=2025))

    def test_los_kilos_no_los_cubre_un_total_en_euros(self):
        self.assertIn('medida:kilos', exigidos('cuantos kilos se han vendido en 2025', ejercicio=2024))
        euros = {'type': 'table', 'sql': 'SELECT SUM(importeneto) AS val'}
        self.assertFalse(cubre('cuantos kilos se han vendido en 2025', euros, ejercicio=2024))
        cantidad = {'type': 'cantidad', 'label': 'kilos', 'key': 'cantidad_kilos'}
        self.assertTrue(cubre('cuantos kilos se han vendido en 2025', cantidad, ejercicio=2024))

    def test_el_analisis_financiero_no_entra_en_esta_puerta(self):
        self.assertEqual(exigidos('analisis financiero del 2025', ejercicio=2024), frozenset())

    def test_el_total_mapeado_no_tapa_la_serie(self):
        total = {
            'type': 'table',
            'sql': 'SELECT SUM(importeneto) AS val',
            'vinculo': 'sola',
            'lectura': {'plan': {'grano': 'ejercicio'}},
        }
        marca = {'reply': {'type': 'text', 'text': 'T1', 'answer': 'T1', 'source': 'plan'}}
        with patch('datia.services.ai.interprete_mapeo.consultar', return_value=total):
            with patch('datia.services.ai.plan_diccionario.responder', return_value=marca) as plan:
                with patch('datia.services.ai.semantic_plan.SemanticPlan.desde_modelo') as modelo:
                    salida = QueryBuilder._construir_consulta(
                        'Ventas trimestrales',
                        {'empresa': 1, 'ejercicio': 2025, 'limit': 10},
                    )
        plan.assert_called_once()
        modelo.assert_not_called()
        self.assertEqual(salida, marca)

    def test_las_ventas_solas_siguen_en_el_mapeo(self):
        total = {'type': 'table', 'sql': 'SELECT SUM(importeneto) AS val', 'vinculo': 'sola'}
        with patch('datia.services.ai.interprete_mapeo.consultar', return_value=total):
            with patch('datia.services.ai.plan_diccionario.responder') as plan:
                salida = QueryBuilder._construir_consulta(
                    'ventas del ejercicio',
                    {'empresa': 1, 'ejercicio': 2025, 'limit': 10},
                )
        plan.assert_not_called()
        self.assertEqual(salida, total)


if __name__ == '__main__':
    unittest.main()
