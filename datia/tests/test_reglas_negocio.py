import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import SimpleTestCase

from datia.services.ai.interprete_mapeo import consultar
from datia.services.ai.reglas_negocio import cargar, decidir, guardar_fichero, leer_fichero, listar_ficheros


class TestReglasDeNegocio(SimpleTestCase):
    def test_el_fichero_declara_el_analisis_y_la_lectura(self):
        ids = [regla['id'] for regla in cargar()]
        self.assertIn('analisis-financiero', ids)
        self.assertIn('kilos-por-mes', ids)
        self.assertIn('lectura-mapeada', ids)
        for regla in (
            'resumen-comercial', 'han-comprado-es-venta', 'agrupacion-articulos',
            'precio-medio', 'dato-no-mapeado', 'cruces', 'memoria', 'top-y-todos', 'ambiguedad',
            'lectura-completa',
        ):
            self.assertIn(regla, ids)
        self.assertLess(ids.index('tesoreria-mensual'), ids.index('tesoreria'))
        self.assertLess(ids.index('tesoreria'), ids.index('analisis-financiero'))

    def test_el_ano_de_la_frase_manda_sobre_el_ejercicio(self):
        decision = decidir('analisis financiero del 2025', ejercicio=2024)
        self.assertEqual(decision['motor'], 'informe')
        self.assertEqual(decision['informe'], 'finanzas.resumen_ejercicio')
        self.assertEqual(decision['anio'], 2025)

    def test_sin_ano_en_la_frase_usa_el_del_hilo(self):
        lectura = {'periodo': [2024], 'conceptos': ['cliente'], 'plan': {'periodos': [2024]}}
        decision = decidir('resumen financiero', lectura=lectura, ejercicio=2025)
        self.assertEqual(decision['anio'], 2024)

    def test_el_resumen_comercial_no_es_el_informe_financiero(self):
        self.assertIsNone(decidir('resumen 2024', ejercicio=2024))
        self.assertIsNone(decidir('top articulos', ejercicio=2024))

    def test_kilos_vendidos_por_mes_es_venta_aunque_el_hilo_sea_de_compra(self):
        lectura = {
            'periodo': [2025],
            'conceptos': ['proveedor'],
            'plan': {'lado': 'compra', 'periodos': [2025]},
        }
        decision = decidir('kilos vendidos por mes', lectura=lectura, ejercicio=2024)
        self.assertEqual(decision['motor'], 'kilos')
        self.assertEqual(decision['lado'], 'cliente')
        self.assertEqual(decision['anio'], 2025)

    def test_kilos_comprados_por_mes_es_compra(self):
        decision = decidir('kilos comprados por mes', ejercicio=2025)
        self.assertEqual(decision['lado'], 'proveedor')
        self.assertEqual(decision['anio'], 2025)

    def test_el_total_de_kilos_no_entra_en_la_regla_mensual(self):
        self.assertIsNone(decidir('cuantos kilos se han vendido en 2025', ejercicio=2025))

    def test_la_respuesta_corta_cierra_los_kilos_y_no_repregunta(self):
        lectura = {
            'clase': 'cifra',
            'forma': 'tabla',
            'conceptos': ['proveedor'],
            'periodo': [2025],
            'plan': {'lado': 'compra', 'periodos': [2025]},
        }
        pendiente = {
            'pregunta': 'kilos vendidos por mes',
            'tipo': 'concepto',
            'claves': ['proveedor', 'cliente'],
            'opciones': ['proveedores', 'clientes'],
        }
        salida = consultar(
            'clientes', 1, 2024,
            campos=[], relaciones=[], sondear=False,
            lectura=lectura, pendiente=pendiente,
        )
        sql = salida['sql'].lower()
        texto = salida['reply']['answer'].lower()
        self.assertIn('lineasalbarancliente', sql)
        self.assertNotIn('lineasalbaranproveedor', sql)
        self.assertIn('2025', sql)
        self.assertIn('importeneto', sql)
        self.assertNotIn('proveedores o clientes', texto)

    def test_se_puede_crear_y_leer_otro_fichero(self):
        with tempfile.TemporaryDirectory() as tmp:
            nombre = guardar_fichero(
                'prueba-chat',
                ':::regla\nid: prueba\nmotor: informe\ninforme: finanzas.per100\ncontiene: frase de prueba unica\nanio: ejercicio\n:::\n',
                raiz=tmp,
                crear=True,
            )
            self.assertEqual(nombre, 'prueba-chat.md')
            self.assertEqual([item['nombre'] for item in listar_ficheros(tmp)], ['prueba-chat.md'])
            self.assertIn('frase de prueba unica', leer_fichero(nombre, tmp))
            self.assertEqual(cargar(tmp)[0]['id'], 'prueba')
            with self.assertRaises(ValueError):
                guardar_fichero('../secreto', 'x', raiz=tmp, crear=True)
            with self.assertRaises(FileExistsError):
                guardar_fichero('prueba-chat', 'otro', raiz=tmp, crear=True)
