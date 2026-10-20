import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = Path(__file__).resolve().parent
for carpeta in (ROOT, TESTS):
    if str(carpeta) not in sys.path:
        sys.path.insert(0, str(carpeta))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import SimpleTestCase

from banco_preguntas import construir_banco


class TestBancoDeMilPreguntas(SimpleTestCase):
    def test_son_mil_frases_distintas_y_cubren_las_familias(self):
        banco = construir_banco()
        self.assertEqual(len(banco), 1000)
        self.assertEqual(len({pregunta['texto'] for pregunta in banco}), 1000)
        familias = {pregunta['familia'] for pregunta in banco}
        self.assertIn('precio_medio', familias)
        self.assertIn('fuera', familias)
        self.assertIn('kilos', familias)
        self.assertIn('stock', familias)
        medias = [pregunta for pregunta in banco if pregunta['pista'] == 'precio_medio']
        self.assertTrue(medias)
        self.assertTrue(all('medio' in pregunta['texto'] or 'ticket' in pregunta['texto'] for pregunta in medias))
        fuera = [pregunta for pregunta in banco if pregunta['espera'] == 'rechazo']
        self.assertGreaterEqual(len(fuera), 40)


if __name__ == '__main__':
    unittest.main()
