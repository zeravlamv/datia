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

from datia.services.ai.handlers.snapshot_handler import SnapshotHandler


COLUMNAS = {
    'codigoempresa': 'codigoempresa',
    'ejercicioalbaran': 'ejercicioalbaran',
    'fechaalbaran': 'fechaalbaran',
    'importeneto': 'importeneto',
    'importecoste': 'importecoste',
    'numeroalbaran': 'numeroalbaran',
    'seriealbaran': 'seriealbaran',
}


class TestSqlVentasDesdeLineas(SimpleTestCase):
    def test_suma_el_neto_de_las_lineas_y_cuenta_el_albaran_una_vez(self):
        sql = SnapshotHandler.sql_ventas_desde_lineas(COLUMNAS, 1, 2025, '2025-12-02', '2025-12-31')
        self.assertIn('FROM datiadb_lineasalbarancliente', sql)
        self.assertIn('SUM("importeneto")', sql)
        self.assertIn('SUM("importecoste")', sql)
        self.assertIn('COUNT(DISTINCT ("seriealbaran", "numeroalbaran"))', sql)
        self.assertIn("DATE '2025-12-02'", sql)
        self.assertIn("DATE '2025-12-31'", sql)
        self.assertNotIn('cabeceraalbarancliente', sql)

    def test_sin_columna_de_neto_no_hay_consulta(self):
        cols = dict(COLUMNAS)
        cols.pop('importeneto')
        self.assertIsNone(SnapshotHandler.sql_ventas_desde_lineas(cols, 1, 2025, '2025-12-02', '2025-12-31'))

    def test_rechaza_una_fecha_mal_formada(self):
        self.assertIsNone(SnapshotHandler.sql_ventas_desde_lineas(COLUMNAS, 1, 2025, '31/12/2025', '2025-12-31'))


if __name__ == '__main__':
    unittest.main()
