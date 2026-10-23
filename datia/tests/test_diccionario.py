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

from datia.services.ai.diccionario import operaciones, papel_de


class TestPapelDeMapeo(SimpleTestCase):
    def test_una_metrica_es_cifra(self):
        self.assertEqual(papel_de('metric', 'ImporteNeto', 'Importe neto'), 'cifra')

    def test_un_cliente_es_nombre(self):
        self.assertEqual(papel_de('dimension', 'CodigoCliente', 'Cliente'), 'nombre')

    def test_una_familia_es_nombre(self):
        self.assertEqual(papel_de('dimension', 'CodigoFamilia', 'Familia'), 'nombre')

    def test_una_partida_es_agrupador(self):
        self.assertEqual(papel_de('dimension', 'Partida', 'partida'), 'agrupador')

    def test_una_fecha_es_fecha(self):
        self.assertEqual(papel_de('date', 'FechaAlbaran', 'Fecha albarán'), 'fecha')

    def test_un_dato_suelto_no_entra(self):
        self.assertIsNone(papel_de('data', 'NumeroPedido', 'Número de pedido'))

    def test_las_operaciones_ya_cargadas_estan_declaradas(self):
        frases = {ficha['frase'] for ficha in operaciones()}
        self.assertIn('ventas por trimestre', frases)
        self.assertIn('efectos pendientes de cobro o de pago', frases)
        self.assertIn('saldo de un grupo de cuentas', frases)


if __name__ == '__main__':
    unittest.main()
