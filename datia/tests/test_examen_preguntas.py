import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import SimpleTestCase

from datia.services.ai.examen_preguntas import clasificar, empaquetar_revision, revision_aceptada


class TestClasificarExamen(SimpleTestCase):
    def test_el_importe_de_la_cartera_es_la_cifra_de_la_tabla(self):
        spec = {'modo': 'importe', 'valor': 1500.5}
        respuesta = {
            'kpis': [{'label': 'Pendiente de pago', 'value': 1500.5, 'suffix': '€'}],
            'answer': 'Pendiente de pago de 1.500,50 €.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_un_conteo_contestado_en_euros_es_otra_cifra(self):
        spec = {'modo': 'conteo', 'valor': 40}
        respuesta = {
            'kpis': [{'label': 'Pendiente de pago', 'value': 8800.0, 'suffix': '€'}],
            'answer': 'Tienen 8.800,00 € en 40 efectos.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_la_lista_de_efectos_coincide_con_los_importes(self):
        spec = {'modo': 'lista', 'importes': [500.0, 200.0]}
        respuesta = {
            'table': {
                'rows': [
                    ['Proveedor A', 500.0],
                    ['Proveedor B', 200.0],
                ],
            },
            'answer': 'Dos efectos.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_una_lista_agrupada_por_cuenta_es_otra_cifra(self):
        spec = {'modo': 'lista', 'importes': [500.0, 200.0]}
        respuesta = {
            'kpis': [{'label': 'Pendiente', 'value': 700.0, 'suffix': '€'}],
            'table': {'rows': [['Cuenta 400', 700.0, 2]]},
            'answer': 'Un titular.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_sin_datos_es_sin_respuesta(self):
        spec = {'modo': 'conteo', 'valor': 12}
        respuesta = {'type': 'text', 'text': 'No he podido obtener un resultado para esta pregunta.', 'answer': ''}
        self.assertEqual(clasificar(spec, respuesta), 'sin_respuesta')

    def test_facturas_con_un_importe_es_otra_cifra(self):
        spec = {'modo': 'sin_cifra'}
        respuesta = {
            'kpis': [{'label': 'Pendiente de cobro', 'value': 900.0, 'suffix': '€'}],
            'answer': 'Pendiente de cobro de 900,00 €.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_un_conteo_en_la_serie_de_datos_es_la_cifra(self):
        spec = {'modo': 'conteo', 'valor': 40}
        respuesta = {'data': [{'label': 'Total', 'val': 40}], 'text': 'El resultado es 40,00 €.'}
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_un_importe_en_la_serie_de_datos_es_la_cifra(self):
        spec = {'modo': 'importe', 'valor': 1500.5}
        respuesta = {'data': [{'label': 'Total', 'val': 1500.5}], 'text': 'Ventas del ejercicio.'}
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_una_lista_en_data_coincide(self):
        spec = {'modo': 'lista', 'importes': [500.0, 200.0]}
        respuesta = {
            'data': [{'label': 'A', 'val': 500}, {'label': 'B', 'val': 200}],
            'text': 'Dos clientes.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_los_codigos_del_listado_coinciden_en_orden(self):
        spec = {'modo': 'textos', 'textos': ['01110', '01130']}
        respuesta = {
            'kpis': [{'label': 'Registros', 'value': 2, 'suffix': 'uds'}],
            'table': {'rows': [['01110', 'Cafe'], ['01130', 'Otro'], ['01191', 'Mas']]},
            'text': 'Artículos',
        }
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_una_lista_de_codigos_distinta_es_otra_cifra(self):
        spec = {'modo': 'textos', 'textos': ['01110', '01130']}
        respuesta = {
            'table': {'rows': [['01130', 'Otro'], ['01110', 'Cafe']]},
            'text': 'Artículos',
        }
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_las_cifras_de_los_dos_ejercicios_coinciden(self):
        spec = {'modo': 'cifras', 'importes': [100.0, 250.0]}
        respuesta = {
            'data': [
                {'label': 'Ene', '2024': 40, '2025': 100, 'val': 100},
                {'label': 'Feb', '2024': 60, '2025': 150, 'val': 150},
            ],
            'text': 'Comparativa',
        }
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_cifras_distintas_son_otra_cifra(self):
        spec = {'modo': 'cifras', 'importes': [100.0, 250.0]}
        respuesta = {
            'data': [{'label': 'Ene', '2024': 1, '2025': 2, 'val': 2}],
            'text': 'Comparativa',
        }
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_el_listado_completo_coincide_si_estan_el_total_y_la_familia(self):
        spec = {
            'modo': 'listado',
            'valor': 1616,
            'textos': ['0000000001', '0000000002'],
            'familias': ['CAF', 'TE'],
        }
        respuesta = {
            'kpis': [{'label': 'Registros', 'value': 1616, 'suffix': 'uds'}],
            'table': {
                'columns': ['Código', 'Descripción', 'Familia'],
                'rows': [
                    ['0000000001', 'Cafe', 'CAF'],
                    ['0000000002', 'Otro', 'TE'],
                    ['001', 'Mas', 'XX'],
                ],
            },
            'text': 'Articulos',
        }
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_una_muestra_de_treinta_no_es_el_listado_completo(self):
        spec = {
            'modo': 'listado',
            'valor': 1616,
            'textos': ['0000000001'],
            'familias': ['CAF'],
        }
        filas = [['0000000001', 'Cafe', 'CAF']] + [['x', 'y', 'z'] for _ in range(29)]
        respuesta = {
            'kpis': [{'label': 'Registros', 'value': 30, 'suffix': 'uds'}],
            'table': {'columns': ['Código', 'Descripción', 'Familia'], 'rows': filas},
            'text': 'Articulos',
        }
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_facturas_sin_numero_queda_sin_respuesta(self):
        spec = {'modo': 'sin_cifra'}
        respuesta = {
            'type': 'text',
            'text': 'Puedo responder sobre ventas, compras, clientes, artículos, proveedores, margen, coste y stock de la empresa.',
            'answer': 'Puedo responder sobre ventas, compras, clientes, artículos, proveedores, margen, coste y stock de la empresa.',
        }
        self.assertEqual(clasificar(spec, respuesta), 'sin_respuesta')


    def test_una_continuacion_que_hereda_de_mas_es_otra_cifra(self):
        spec = {'modo': 'importe', 'valor': 10, 'vinculo': 'continuacion', 'sustituye': ['periodo']}
        respuesta = {'vinculo': 'continuacion', 'sustituye': ['periodo', 'concepto'], 'kpis': [{'value': 10}], 'text': '10'}
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_una_frase_sola_que_hereda_es_otra_cifra(self):
        spec = {'modo': 'importe', 'valor': 10, 'vinculo': 'sola'}
        respuesta = {'vinculo': 'sola', 'hereda': ['periodo'], 'kpis': [{'value': 10}], 'text': '10'}
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_el_dato_no_mapeado_coincide_con_la_negativa_fija(self):
        spec = {'modo': 'rechazo', 'texto': 'Esa pregunta no está en los datos mapeados.'}
        respuesta = {'type': 'text', 'text': 'Esa pregunta no está en los datos mapeados.', 'answer': 'Esa pregunta no está en los datos mapeados.'}
        self.assertEqual(clasificar(spec, respuesta), 'cifra_tabla')

    def test_una_frase_ajena_con_cifra_de_la_empresa_no_coincide(self):
        spec = {'modo': 'rechazo', 'texto': ''}
        respuesta = {'kpis': [{'value': 10, 'suffix': '€'}], 'text': 'Ventas 10 €'}
        self.assertEqual(clasificar(spec, respuesta), 'otra_cifra')

    def test_la_lista_previa_ensenya_vinculo_esperado_y_la_pieza_que_falta(self):
        vista = empaquetar_revision(
            1, 2025,
            [{'pregunta': 'ventas del ejercicio', 'esperado': '1,00 €', 'vinculo': 'sola'}],
            [{'pregunta': 'que tiempo hace hoy', 'esperado': 'Sin cifra de la empresa'}],
            True,
            'columna:Telefono',
        )
        self.assertEqual(vista['estado'], 'Preparada')
        self.assertTrue(vista['incompleta'])
        self.assertEqual(vista['falta'], 'columna:Telefono')
        self.assertEqual(vista['preguntas'][0]['vinculo'], 'sola')
        self.assertIn('esperado', vista['preguntas'][0])
        self.assertTrue(vista['probes'])
        self.assertFalse(revision_aceptada(True, 1, 1, 1, 1))
        self.assertTrue(revision_aceptada(False, 4, 4, 2, 2))


if __name__ == '__main__':
    unittest.main()
