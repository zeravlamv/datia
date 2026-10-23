import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.test import SimpleTestCase

from datia.services.ai.compilador_mapeo import compilar_sql, elegir, nombre_fisico
from datia.services.security.sql_guard import SQLGuard


def _campo(**datos):
    base = {
        'id': 1,
        'papel': 'cifra',
        'field_name': 'ImporteNeto',
        'business_name': 'Importe neto',
        'source_id': 10,
        'source_table': 'LineasAlbaranCliente',
        'local': 'datiadb_lineasalbarancliente',
        'is_key': False,
    }
    base.update(datos)
    return SimpleNamespace(**base)


class TestNombreFisico(SimpleTestCase):
    def test_usa_el_nombre_saneado_del_negocio(self):
        campo = _campo(business_name='Codigo contable', field_name='CodigoContable')
        self.assertEqual(nombre_fisico(campo, {'codigo_contable', 'codigocontable'}), 'codigo_contable')

    def test_si_no_hay_hueco_usa_el_nombre_sage(self):
        campo = _campo(business_name='Codigo contable', field_name='CodigoContable')
        self.assertEqual(nombre_fisico(campo, {'codigocontable'}), 'codigocontable')


class TestElegir(SimpleTestCase):
    def test_importe_neto_por_cliente_en_albaran(self):
        campos = [
            _campo(),
            _campo(id=2, papel='cifra', field_name='ImporteNeto', business_name='Importe neto', source_id=11, source_table='LineasAlbaranProveedor', local='datiadb_lineasalbaranproveedor'),
            _campo(id=3, papel='nombre', field_name='CodigoCliente', business_name='Cliente', source_id=20, source_table='Clientes', local='datiadb_clientes'),
        ]
        cifra, corte = elegir('importe neto por cliente', campos)
        self.assertEqual(cifra.source_table, 'LineasAlbaranCliente')
        self.assertEqual(corte.field_name, 'CodigoCliente')

    def test_sin_cifra_no_hay_consulta(self):
        self.assertIsNone(elegir('listado de clientes', [_campo(id=3, papel='nombre', field_name='CodigoCliente', business_name='Cliente')]))


class TestCompilar(SimpleTestCase):
    def test_el_albaran_cruza_las_cuatro_claves(self):
        cifra = _campo()
        corte = _campo(id=4, papel='nombre', field_name='CodigoCliente', business_name='Cliente', source_id=30, source_table='CabeceraAlbaranCliente', local='datiadb_cabeceraalbarancliente')
        empresa = _campo(id=5, papel=None, field_name='CodigoEmpresa', business_name='Empresa', source_id=10)
        anio = _campo(id=6, papel=None, field_name='EjercicioAlbaran', business_name='Ejercicio albaran', source_id=10)
        columnas = {
            10: {'importeneto', 'codigoempresa', 'ejercicioalbaran', 'seriealbaran', 'numeroalbaran'},
            30: {'codigocliente', 'codigoempresa', 'ejercicioalbaran', 'seriealbaran', 'numeroalbaran'},
        }
        saltos = [{
            'tabla': 'datiadb_cabeceraalbarancliente',
            'source_id': 30,
            'pares': [
                ('codigoempresa', 'codigoempresa'),
                ('ejercicioalbaran', 'ejercicioalbaran'),
                ('seriealbaran', 'seriealbaran'),
                ('numeroalbaran', 'numeroalbaran'),
            ],
        }]
        sql = compilar_sql(cifra, corte, [cifra, corte, empresa, anio], columnas, saltos, 1, 2025, 10, 'DESC')
        self.assertIn('JOIN "datiadb_cabeceraalbarancliente" t2 ON', sql)
        self.assertIn('t1."codigoempresa" = t2."codigoempresa"', sql)
        self.assertIn('t1."ejercicioalbaran" = t2."ejercicioalbaran"', sql)
        self.assertIn('t1."seriealbaran" = t2."seriealbaran"', sql)
        self.assertIn('t1."numeroalbaran" = t2."numeroalbaran"', sql)
        self.assertIn('t1."codigoempresa" = 1', sql)
        self.assertIn('t1."ejercicioalbaran" = 2025', sql)

    def test_dos_saltos_dejan_la_etiqueta_en_la_ultima_tabla(self):
        cifra = _campo()
        corte = _campo(id=7, papel='nombre', field_name='CodigoCliente', business_name='Cliente', source_id=40, source_table='Clientes', local='datiadb_clientes')
        razon = _campo(id=8, papel='agrupador', field_name='RazonSocial', business_name='Razon social', source_id=40, source_table='Clientes', local='datiadb_clientes')
        empresa = _campo(id=5, papel=None, field_name='CodigoEmpresa', business_name='Empresa', source_id=10)
        anio = _campo(id=6, papel=None, field_name='EjercicioAlbaran', business_name='Ejercicio albaran', source_id=10)
        columnas = {
            10: {'importeneto', 'codigoempresa', 'ejercicioalbaran'},
            40: {'cliente', 'razonsocial', 'empresa'},
        }
        saltos = [
            {'tabla': 'datiadb_cabeceraalbarancliente', 'source_id': 30, 'pares': [('numeroalbaran', 'numeroalbaran')]},
            {'tabla': 'datiadb_clientes', 'source_id': 40, 'pares': [('codigocliente', 'cliente'), ('codigoempresa', 'empresa')]},
        ]
        sql = compilar_sql(cifra, corte, [cifra, corte, razon, empresa, anio], columnas, saltos, 1, 2025, 10, 'DESC')
        self.assertIn('JOIN "datiadb_clientes" t3 ON t2."codigocliente" = t3."cliente" AND t2."codigoempresa" = t3."empresa"', sql)
        self.assertIn('t3."razonsocial"', sql)
        self.assertIn('GROUP BY t3."cliente"', sql)


class TestTablasMapeadas(unittest.TestCase):
    def test_una_tabla_mapeada_se_puede_leer(self):
        with patch.object(SQLGuard, '_tablas_mapeadas', return_value={'datiadb_clientes'}):
            res = SQLGuard.check_sql('SELECT 1 FROM "datiadb_clientes"')
        self.assertTrue(res['allowed'])

    def test_una_tabla_datiadb_ajena_sigue_bloqueada(self):
        with patch.object(SQLGuard, '_tablas_mapeadas', return_value=set()):
            res = SQLGuard.check_sql('SELECT * FROM "datiadb_financial_acumulados"')
        self.assertFalse(res['allowed'])
