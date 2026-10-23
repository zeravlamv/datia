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

from datia.services.ai.formatter import ResponseFormatter
from datia.services.ai.interprete_mapeo import (
    compilar_plan,
    consultar,
    plan_determinista,
    senala_mapeo,
    validar_plan,
)


def _fuente(num, tabla, local):
    return SimpleNamespace(id=num, source_table=tabla, get_local_table_name=lambda local=local: local)


def _campo(num, fuente, field_name, business, papel, key=False):
    return SimpleNamespace(
        id=num,
        papel=papel,
        field_name=field_name,
        business_name=business,
        source_id=fuente.id,
        source_table=fuente.source_table,
        local=fuente.get_local_table_name(),
        is_key=key,
        usage_type=papel,
        synonyms=[],
    )


def _rel(origen, destino, izquierda, derecha):
    return SimpleNamespace(
        source_id=origen.id,
        target_id=destino.id,
        source=origen,
        target=destino,
        from_field=izquierda,
        to_field=derecha,
    )


def _catalogo():
    lineas = _fuente(10, 'LineasAlbaranCliente', 'datiadb_lineasalbarancliente')
    cabecera = _fuente(30, 'CabeceraAlbaranCliente', 'datiadb_cabeceraalbarancliente')
    clientes = _fuente(40, 'Clientes', 'datiadb_clientes')
    compras = _fuente(50, 'LineasAlbaranProveedor', 'datiadb_lineasalbaranproveedor')
    articulos = _fuente(60, 'Articulos', 'datiadb_articulos')
    campos = [
        _campo(1, lineas, 'ImporteNeto', 'Importe neto', 'cifra'),
        _campo(2, lineas, 'CodigoArticulo', 'Codigo articulo', 'nombre', key=True),
        _campo(3, lineas, 'CodigoEmpresa', '', 'agrupador', key=True),
        _campo(4, lineas, 'EjercicioAlbaran', '', 'fecha'),
        _campo(5, lineas, 'SerieAlbaran', '', 'agrupador', key=True),
        _campo(6, lineas, 'NumeroAlbaran', '', 'agrupador', key=True),
        _campo(7, cabecera, 'ImporteNeto', 'Importe neto', 'cifra'),
        _campo(8, cabecera, 'CodigoCliente', 'Cliente', 'nombre', key=True),
        _campo(9, cabecera, 'CodigoEmpresa', '', 'agrupador', key=True),
        _campo(10, cabecera, 'EjercicioAlbaran', '', 'fecha'),
        _campo(11, cabecera, 'SerieAlbaran', '', 'agrupador', key=True),
        _campo(12, cabecera, 'NumeroAlbaran', '', 'agrupador', key=True),
        _campo(13, clientes, 'CodigoCliente', 'Cliente', 'nombre', key=True),
        _campo(14, clientes, 'RazonSocial', 'Razon social', 'agrupador'),
        _campo(15, clientes, 'Empresa', 'Empresa', 'agrupador', key=True),
        _campo(18, clientes, 'CifDni', 'CifDni', 'agrupador'),
        _campo(16, compras, 'ImporteNeto', 'Importe neto', 'cifra'),
        _campo(17, compras, 'CodigoArticulo', 'Codigo articulo', 'nombre', key=True),
        _campo(20, articulos, 'CodigoArticulo', 'Codigo articulo', 'nombre', key=True),
        _campo(21, articulos, 'DescripcionArticulo', 'Descripcion articulo', 'agrupador'),
        _campo(22, articulos, 'CodigoEmpresa', 'Empresa', 'agrupador', key=True),
        _campo(24, articulos, 'CodigoFamilia', 'Familia', 'agrupador'),
        _campo(23, cabecera, 'FechaAlbaran', 'Fecha albaran', 'fecha'),
    ]
    relaciones = [
        _rel(lineas, cabecera, campos[2], campos[8]),
        _rel(lineas, cabecera, campos[3], campos[9]),
        _rel(lineas, cabecera, campos[4], campos[10]),
        _rel(lineas, cabecera, campos[5], campos[11]),
        _rel(cabecera, clientes, campos[8], campos[14]),
        _rel(cabecera, clientes, campos[7], campos[12]),
    ]
    columnas = {
        10: {'importeneto', 'codigoarticulo', 'codigoempresa', 'ejercicioalbaran', 'seriealbaran', 'numeroalbaran'},
        30: {'importeneto', 'codigocliente', 'codigoempresa', 'ejercicioalbaran', 'seriealbaran', 'numeroalbaran', 'fechaalbaran'},
        40: {'cliente', 'empresa', 'razon_social', 'cifdni'},
        50: {'importeneto', 'codigoarticulo', 'codigoempresa', 'ejercicioalbaran'},
        60: {'codigoarticulo', 'descripcionarticulo', 'codigoempresa', 'familia'},
    }
    return campos, relaciones, columnas


PREGUNTA = 'que clientes han comprado el producto 01110'


class TestPlanDeterminista(SimpleTestCase):
    def test_el_producto_filtra_el_articulo_y_agrupa_clientes(self):
        campos, _relaciones, _columnas = _catalogo()
        plan = plan_determinista(PREGUNTA, campos, 20)
        self.assertEqual(plan['campos'][0]['id'], 1)
        self.assertEqual(plan['campos'][0]['agregado'], 'sum')
        self.assertEqual(plan['filtros'], [{'id': 2, 'op': '=', 'valor': '01110'}])
        self.assertEqual(plan['agrupar'], [13])

    def test_sin_decir_pedido_usa_el_albaran(self):
        lineas = _fuente(10, 'LineasAlbaranCliente', 'datiadb_lineasalbarancliente')
        pedido = _fuente(11, 'LineasPedidoCliente', 'datiadb_lineaspedidocliente')
        clientes = _fuente(40, 'Clientes', 'datiadb_clientes')
        campos = [
            _campo(1, pedido, 'ImporteNeto', 'Importe neto', 'cifra'),
            _campo(2, pedido, 'CodigoArticulo', 'Codigo articulo', 'nombre', key=True),
            _campo(30, lineas, 'ImporteNeto', 'Importe neto', 'cifra'),
            _campo(31, lineas, 'CodigoArticulo', 'Codigo articulo', 'nombre', key=True),
            _campo(13, clientes, 'CodigoCliente', 'Cliente', 'nombre', key=True),
        ]
        plan = plan_determinista(PREGUNTA, campos, 20)
        self.assertEqual(plan['campos'][0]['id'], 30)
        self.assertEqual(plan['filtros'][0]['id'], 31)

    def test_ventas_del_ejercicio_senala_el_importe_mapeado(self):
        campos, _relaciones, _columnas = _catalogo()
        self.assertTrue(senala_mapeo('ventas del ejercicio', campos))

    def test_un_valor_envenenado_no_sale_en_el_plan_valido(self):
        campos, _relaciones, _columnas = _catalogo()
        self.assertFalse(validar_plan(
            {'campos': [{'id': 1, 'agregado': 'sum'}], 'filtros': [{'id': 2, 'op': '=', 'valor': "01110' OR '1'='1"}]},
            campos,
        ))


class TestCompilarPlan(SimpleTestCase):
    def test_cruza_albaran_y_clientes_filtrando_el_articulo(self):
        campos, relaciones, columnas = _catalogo()
        plan = plan_determinista(PREGUNTA, campos, 20)
        sql = compilar_plan(plan, campos, relaciones, columnas, 1, 2025, 'postgres')
        self.assertIn('FROM "datiadb_lineasalbarancliente" t1', sql)
        self.assertIn('JOIN "datiadb_cabeceraalbarancliente" t2 ON', sql)
        self.assertIn('t1."codigoempresa" = t2."codigoempresa"', sql)
        self.assertIn('t1."ejercicioalbaran" = t2."ejercicioalbaran"', sql)
        self.assertIn('t1."seriealbaran" = t2."seriealbaran"', sql)
        self.assertIn('t1."numeroalbaran" = t2."numeroalbaran"', sql)
        self.assertIn('JOIN "datiadb_clientes" t3 ON', sql)
        self.assertIn('t2."codigocliente" = t3."cliente"', sql)
        self.assertIn('t2."codigoempresa" = t3."empresa"', sql)
        self.assertIn('t1."codigoarticulo" = \'01110\'', sql)
        self.assertIn('t1."ejercicioalbaran" = 2025', sql)
        self.assertIn('t3."razon_social"', sql)
        self.assertNotIn('lineasalbaranproveedor', sql)

    def test_el_listado_completo_no_se_recorta_al_validar(self):
        campos, _, _ = _catalogo()
        plan = validar_plan({
            'campos': [{'id': 20, 'agregado': 'ninguno', 'titulo': 'Código'}],
            'forma': 'listado',
            'completo': True,
            'limite': 5000,
        }, campos, 20)
        self.assertTrue(plan['completo'])
        self.assertEqual(plan['limite'], 5000)
        self.assertEqual(plan['campos'][0]['titulo'], 'Código')

    def test_sql_server_usa_top(self):
        campos, relaciones, columnas = _catalogo()
        plan = plan_determinista(PREGUNTA, campos, 20)
        sql = compilar_plan(plan, campos, relaciones, columnas, 1, 2025, 'sqlserver')
        self.assertIn('SELECT TOP 20', sql)
        self.assertNotIn('LIMIT', sql)
        self.assertIn('[codigoarticulo] = \'01110\'', sql)

    def test_el_listado_completo_en_sql_server_no_usa_top(self):
        campos, relaciones, columnas = _catalogo()
        plan = plan_determinista(
            'lista de todos los articulos con el codigo, la descripcion y la familia',
            campos,
            20,
        )
        sql = compilar_plan(plan, campos, relaciones, columnas, 1, 2025, 'sqlserver')
        self.assertNotIn('TOP', sql)
        self.assertNotIn('LIMIT', sql)
        self.assertIn('[familia]', sql)
        self.assertNotIn('ejercicio', sql.lower())


class TestConsultar(SimpleTestCase):
    def test_la_pregunta_del_producto_no_cae_en_el_ranking(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'qué clientes han comprado el producto 01110',
                1, 2025, 20,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: None, dialecto='postgres',
            )
        self.assertIn('01110', salida['sql'])
        self.assertEqual(salida['source'], 'mapeo')

    def test_ventas_del_ejercicio_suman_el_albaran_de_cliente(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'ventas del ejercicio', 1, 2025, 20,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertIn('SUM', salida['sql'])
        self.assertIn('datiadb_cabeceraalbarancliente', salida['sql'])
        self.assertIn('2025', salida['sql'])
        self.assertNotIn('proveedor', salida['sql'])

    def test_una_frase_ajena_sigue_el_atajo(self):
        campos, relaciones, columnas = _catalogo()
        salida = consultar(
            'que tiempo hace hoy', 1, 2025, 20,
            campos=campos, relaciones=relaciones, columnas=columnas,
            pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
            dialecto='postgres',
        )
        self.assertIsNone(salida)

    def test_la_lista_de_articulos_muestra_codigo_y_descripcion(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'quiero ver una lista de artículos con el código y descripción',
                1, 2025, 20,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertEqual(salida['type'], 'listado')
        self.assertIn('datiadb_articulos', salida['sql'])
        self.assertIn('codigoarticulo', salida['sql'])
        self.assertIn('descripcionarticulo', salida['sql'])
        self.assertNotIn('proveedor', salida['sql'])
        self.assertNotIn('importe', salida['sql'])
        self.assertIn('LIMIT 100', salida['sql'])

    def test_todos_los_articulos_salen_sin_corte_y_con_familia(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'quiero ver una lista de TODOS artículos con el código y descripción y Familia',
                1, 2025, 20,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertEqual(salida['type'], 'listado')
        self.assertTrue(salida['completo'])
        self.assertEqual(salida['titulos'], ['Código', 'Descripción', 'Familia'])
        self.assertNotIn('LIMIT', salida['sql'])
        self.assertNotIn('ejercicio', salida['sql'].lower())
        self.assertIn('codigoarticulo', salida['sql'])
        self.assertIn('descripcionarticulo', salida['sql'])
        self.assertIn('familia', salida['sql'])

    def test_los_diez_primeros_siguen_cortados(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'los 10 primeros articulos con el codigo y la descripcion',
                1, 2025, 10,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertIn('LIMIT 10', salida['sql'])
        self.assertNotIn('familia', salida['sql'])

    def test_todos_los_clientes_tampoco_filtran_el_ejercicio(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'lista de todos los clientes con el codigo y la razon social',
                1, 2025, 20,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertTrue(salida['completo'])
        self.assertNotIn('LIMIT', salida['sql'])
        self.assertNotIn('ejercicio', salida['sql'].lower())
        self.assertIn('datiadb_clientes', salida['sql'])
        self.assertEqual(salida['titulos'], ['Código', 'Razón social'])

    def test_el_listado_de_clientes_incluye_el_cif(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'listado de todos los clientes, codigo, razon comercial y cif',
                1, 2025, 10,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertTrue(salida['completo'])
        self.assertEqual(salida['titulos'], ['Código', 'Razón social', 'CIF'])
        self.assertIn('cifdni', salida['sql'])
        self.assertNotIn('LIMIT', salida['sql'])
        self.assertNotIn('ejercicio', salida['sql'].lower())

    def test_un_listado_enorme_avisa_que_esta_incompleto(self):
        filas = [{'codigo': str(i)} for i in range(10001)]
        salida = ResponseFormatter.format_response(
            {
                'type': 'listado',
                'completo': True,
                'label': 'Articulos',
                'sql': 'select 1',
                'source': 'mapeo',
                'columnas': ['codigo'],
                'titulos': ['Código'],
            },
            filas,
            2025,
        )
        self.assertEqual(salida['kpis'][0]['value'], 10001)
        self.assertEqual(len(salida['table']['rows']), 10000)
        self.assertIn('incompleta', salida['text'].lower())

    def test_la_comparativa_de_ventas_lee_los_dos_anos(self):
        campos, relaciones, columnas = _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'grafica de ventas comparativa 2024 vs 2025',
                1, 2025, 20,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres',
            )
        self.assertEqual(salida['type'], 'chart')
        self.assertEqual(salida['chart_type'], 'line')
        self.assertIn('2024', salida['sql'])
        self.assertIn('2025', salida['sql'])
        self.assertIn('AS serie', salida['sql'])
        self.assertIn('datiadb_cabeceraalbarancliente', salida['sql'])
        self.assertNotIn('proveedor', salida['sql'])
        self.assertNotIn('pedido', salida['sql'])

    def test_un_plan_con_campo_ajeno_no_se_sustituye(self):
        campos, relaciones, columnas = _catalogo()
        salida = consultar(
            'clientes con importe mayor que 1000', 1, 2025, 20,
            campos=campos, relaciones=relaciones, columnas=columnas,
            pedir=lambda *_args: {'campos': [{'id': 999, 'agregado': 'sum'}]},
            dialecto='postgres',
        )
        self.assertIn('no está en los datos mapeados', salida['reply']['answer'])

    def test_el_listado_se_pinta_como_tabla_de_columnas(self):
        salida = ResponseFormatter.format_response(
            {
                'type': 'listado',
                'label': 'Articulos',
                'sql': 'select 1',
                'source': 'mapeo',
                'columnas': ['codigo_articulo', 'descripcion_articulo'],
                'titulos': ['Codigo articulo', 'Descripcion articulo'],
            },
            [{'codigo_articulo': '01110', 'descripcion_articulo': 'CAFE'}],
            2025,
        )
        self.assertEqual(salida['type'], 'report')
        self.assertEqual(salida['table']['columns'], ['Codigo articulo', 'Descripcion articulo'])
        self.assertEqual(salida['table']['rows'], [['01110', 'CAFE']])

    def test_la_comparativa_prepara_una_serie_por_ano(self):
        salida = ResponseFormatter.format_response(
            {
                'type': 'chart',
                'chart_type': 'line',
                'label': 'Comparativa 2024 vs 2025',
                'sql': 'select 1',
                'intent_meta': {'is_comparison': True},
            },
            [
                {'label': 1, 'serie': 2024, 'val': 10},
                {'label': 1, 'serie': 2025, 'val': 12},
            ],
            2025,
        )
        self.assertEqual(len(salida['chart_config']['data']['datasets']), 2)


if __name__ == '__main__':
    unittest.main()
