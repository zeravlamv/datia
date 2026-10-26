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
    _MENSAJE,
    compilar_plan,
    consultar,
    lectura_de_plan,
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
        self.assertIn('recorrido', salida)
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


class TestMemoriaYClasificacion(SimpleTestCase):
    def _salida(self, frase, lectura=None, campos=None, relaciones=None, columnas=None, pendiente=None):
        campos, relaciones, columnas = (campos, relaciones, columnas) if campos is not None else _catalogo()
        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            return consultar(
                frase, 1, 2025, 10,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=lambda *_args: (_ for _ in ()).throw(AssertionError('el modelo no debía entrar')),
                dialecto='postgres', sondear=False, lectura=lectura, pendiente=pendiente,
            )

    def _catalogo_dos_razones(self):
        campos, relaciones, columnas = _catalogo()
        proveedores = _fuente(70, 'Proveedores', 'datiadb_proveedores')
        campos = list(campos) + [
            _campo(30, proveedores, 'CodigoProveedor', 'Proveedor', 'nombre', key=True),
            _campo(31, proveedores, 'RazonSocial', 'Razon social', 'agrupador'),
        ]
        columnas = dict(columnas)
        columnas[70] = {'codigoproveedor', 'razon_social'}
        return campos, relaciones, columnas

    def test_dos_conceptos_piden_distinguir_y_no_mezclan(self):
        campos, relaciones, columnas = self._catalogo_dos_razones()
        salida = self._salida('listado con la razon social', campos=campos, relaciones=relaciones, columnas=columnas)
        self.assertIn('clientes', salida['reply']['answer'])
        self.assertIn('proveedores', salida['reply']['answer'])
        self.assertNotIn('sql', salida)
        self.assertIsNone(salida['lectura'])

    def test_si_la_frase_nombra_un_concepto_esa_es_la_lectura(self):
        campos, relaciones, columnas = self._catalogo_dos_razones()
        salida = self._salida(
            'lista de todos los clientes con el codigo y la razon social',
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(salida['vinculo'], 'sola')
        self.assertIn('datiadb_clientes', salida['sql'])
        self.assertNotIn('proveedores', salida['sql'])

    def test_dos_relaciones_piden_distinguir(self):
        campos, relaciones, columnas = _catalogo()
        cabecera = next(campo for campo in campos if campo.id == 9).source_id and _fuente(30, 'CabeceraAlbaranCliente', 'datiadb_cabeceraalbarancliente')
        clientes = _fuente(40, 'Clientes', 'datiadb_clientes')
        contable = _campo(40, cabecera, 'CodigoContable', 'Codigo contable', 'agrupador', key=True)
        alterno = _campo(41, cabecera, 'CodigoAlterno', 'Codigo alterno', 'agrupador', key=True)
        destino_c = _campo(42, clientes, 'CodigoContable', 'Codigo contable', 'agrupador')
        destino_a = _campo(43, clientes, 'CodigoAlterno', 'Codigo alterno', 'agrupador')
        relaciones = [
            rel for rel in relaciones
            if not (rel.source_id == 30 and rel.target_id == 40 and _clave_visible(rel))
        ] + [_rel(cabecera, clientes, contable, destino_c), _rel(cabecera, clientes, alterno, destino_a)]
        salida = self._salida('ventas por cliente', campos=list(campos) + [contable, alterno, destino_c, destino_a], relaciones=relaciones, columnas=columnas)
        self.assertIn('contable', salida['reply']['answer'].lower())
        self.assertIn('alterno', salida['reply']['answer'].lower())
        self.assertNotIn('sql', salida)
        self.assertIsNone(salida['lectura'])

    def _dos_albaranes(self):
        campos, relaciones, columnas = _catalogo()
        compras = _fuente(50, 'LineasAlbaranProveedor', 'datiadb_lineasalbaranproveedor')
        campos = list(campos) + [
            _campo(51, compras, 'CodigoEmpresa', 'Empresa', 'agrupador', key=True),
            _campo(52, compras, 'EjercicioAlbaran', 'Ejercicio albaran', 'fecha'),
        ]
        return campos, relaciones, columnas

    def _lectura_venta(self):
        return {
            'clase': 'cifra',
            'conceptos': ['cliente'],
            'columnas': [7],
            'filtros': [],
            'corte': None,
            'periodo': [2025],
            'forma': 'tabla',
            'plan': {
                'campos': [{'id': 7, 'agregado': 'avg'}],
                'filtros': [],
                'agrupar': [],
                'orden': {'id': 7, 'sentido': 'desc'},
                'limite': None,
                'forma': 'tabla',
                'periodos': [2025],
                'medida': 'precio_medio',
                'lado': 'venta',
            },
        }

    def test_sin_hilo_el_numero_de_lineas_pregunta_las_dos_opciones(self):
        campos, relaciones, columnas = self._dos_albaranes()
        salida = self._salida(
            'numero de lineas de albaran',
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        texto = salida['reply']['answer']
        self.assertIn('albarán de cliente', texto)
        self.assertIn('albarán de proveedor', texto)
        self.assertNotIn('sql', salida)
        self.assertIsNone(salida['lectura'])
        self.assertEqual(salida['pendiente']['pregunta'], 'numero de lineas de albaran')

    def test_el_hilo_de_venta_cuenta_las_lineas_de_cliente(self):
        campos, relaciones, columnas = self._dos_albaranes()
        salida = self._salida(
            'numero de lineas de albaran',
            lectura=self._lectura_venta(),
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertIn('concepto', salida['hereda'])
        self.assertIn('periodo', salida['hereda'])
        self.assertIn('COUNT(*) AS registros', salida['sql'])
        self.assertIn('datiadb_lineasalbarancliente', salida['sql'])
        self.assertIn('2025', salida['sql'])
        self.assertNotIn('proveedor', salida['sql'])

    def test_si_la_frase_dice_cliente_cuenta_esas_lineas(self):
        campos, relaciones, columnas = self._dos_albaranes()
        lectura = self._lectura_venta()
        lectura['periodo'] = [2024]
        lectura['plan']['periodos'] = [2024]
        salida = self._salida(
            'numero de lineas de albaran de cliente',
            lectura=lectura,
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertEqual(salida['hereda'], ['periodo'])
        self.assertIn('datiadb_lineasalbarancliente', salida['sql'])
        self.assertIn('2024', salida['sql'])
        self.assertNotIn('2025', salida['sql'])
        self.assertNotIn('proveedor', salida['sql'])

    def test_la_opcion_elegida_cuenta_esas_lineas(self):
        campos, relaciones, columnas = self._dos_albaranes()
        aviso = self._salida(
            'numero de lineas de albaran',
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        salida = self._salida(
            'de cliente',
            pendiente=aviso['pendiente'],
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(salida['vinculo'], 'sola')
        self.assertIn('COUNT(*) AS registros', salida['sql'])
        self.assertIn('datiadb_lineasalbarancliente', salida['sql'])
        self.assertNotIn('proveedor', salida['sql'])

    def test_el_hilo_elige_la_razon_social_de_clientes(self):
        campos, relaciones, columnas = self._catalogo_dos_razones()
        salida = self._salida(
            'listado con la razon social',
            lectura=self._lectura_venta(),
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertIn('datiadb_clientes', salida['sql'])
        self.assertNotIn('proveedores', salida['sql'])

    def test_el_motivo_no_rellena_huecos(self):
        base = self._salida('ventas del ejercicio')
        self.assertEqual(base['vinculo'], 'sola')
        salida = self._salida('listado con el motivo', lectura=base['lectura'])
        self.assertEqual(salida['reply']['answer'], _MENSAJE)
        self.assertIsNone(salida['lectura'])
        self.assertEqual(salida['vinculo'], 'rechazo')

    def test_y_en_2024_continua_y_sustituye_el_periodo(self):
        base = self._salida('ventas del ejercicio')
        lectura = lectura_de_plan(base['lectura']['plan'], _catalogo()[0])
        self.assertTrue(lectura['clase'])
        self.assertTrue(lectura['conceptos'])
        self.assertEqual(lectura['forma'], 'tabla')
        salida = self._salida('y en 2024', lectura=base['lectura'])
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertIn('2024', salida['sql'])
        self.assertNotIn('2025', salida['sql'])
        self.assertEqual(salida['sustituye'], ['periodo'])
        self.assertIn('concepto', salida['hereda'])
        self.assertIn('recorrido', salida)

    def test_la_continuacion_no_deja_entrar_al_modelo(self):
        campos, relaciones, columnas = _catalogo()
        base = self._salida('ventas del ejercicio')
        llamadas = []

        def pedir(*args):
            llamadas.append(args)
            return {'campos': [{'id': 1, 'agregado': 'sum'}], 'filtros': [], 'forma': 'tabla'}

        with patch('datia.services.ai.interprete_mapeo._probar', return_value=True), \
             patch('datia.services.security.sql_guard.SQLGuard.check_sql', return_value={'allowed': True}):
            salida = consultar(
                'y en 2024', 1, 2025, 10,
                campos=campos, relaciones=relaciones, columnas=columnas,
                pedir=pedir, dialecto='postgres', sondear=False, lectura=base['lectura'],
            )
        self.assertEqual(llamadas, [])
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertIn('2024', salida['sql'])

    def test_el_precio_medio_de_venta_es_el_importe_partido_por_albaranes(self):
        campos, relaciones, columnas = _catalogo()
        lectura_previa = {
            'clase': 'agrupacion',
            'conceptos': ['articulo'],
            'forma': 'tabla',
            'plan': {
                'campos': [{'id': 1, 'agregado': 'sum'}],
                'agrupar': [20],
                'limite': 10,
                'periodos': [2024],
                'forma': 'tabla',
            },
        }

        def falso(compra, empresa, year, mes):
            if compra:
                return (400, 8)
            if year == 2024:
                return (100, 4)
            return (8687377.42, 5292)

        with patch('datia.services.ai.interprete_mapeo._leer_totales', side_effect=falso):
            salida = self._salida(
                'precio medio de venta', lectura=lectura_previa,
                campos=campos, relaciones=relaciones, columnas=columnas,
            )
            seguido = self._salida(
                'y en 2024', lectura=salida['lectura'],
                campos=campos, relaciones=relaciones, columnas=columnas,
            )
            compra = self._salida(
                'importe medio de compra',
                campos=campos, relaciones=relaciones, columnas=columnas,
            )
        texto = salida['reply']['text']
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertEqual(salida['hereda'], ['periodo'])
        self.assertIn('Precio medio de venta en 2024: 25,00 € por albarán.', texto)
        self.assertIn('100,00 €', texto)
        self.assertIn('4 albaranes', texto)
        self.assertNotIn(_MENSAJE, texto)
        self.assertNotIn('2025', texto)
        self.assertEqual(seguido['vinculo'], 'continuacion')
        self.assertIn('periodo', seguido['sustituye'])
        self.assertIn('2024: 25,00 € por albarán.', seguido['reply']['text'])
        self.assertIn('Importe medio de compra en 2025: 50,00 € por albarán.', compra['reply']['text'])

    def test_top_20_sigue_los_productos_y_cambia_el_corte(self):
        campos, relaciones, columnas = _catalogo()
        lineas = _fuente(10, 'LineasAlbaranCliente', 'datiadb_lineasalbarancliente')
        articulos = _fuente(60, 'Articulos', 'datiadb_articulos')
        codigo_linea = next(campo for campo in campos if campo.id == 2)
        codigo_articulo = next(campo for campo in campos if campo.id == 20)
        empresa_linea = next(campo for campo in campos if campo.id == 3)
        empresa_articulo = next(campo for campo in campos if campo.id == 22)
        relaciones = list(relaciones) + [
            _rel(lineas, articulos, codigo_linea, codigo_articulo),
            _rel(lineas, articulos, empresa_linea, empresa_articulo),
        ]
        columnas = dict(columnas)
        columnas[10] = set(columnas[10]) | {'importecoste'}
        base = self._salida(
            'productos vendidos en 2024',
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(base['vinculo'], 'sola')
        self.assertIn('datiadb_lineasalbarancliente', base['sql'])
        self.assertIn('AS coste', base['sql'])
        self.assertIn('AS ops', base['sql'])
        self.assertNotIn('cabecera', base['sql'])
        self.assertIn('2024', base['sql'])
        self.assertIn('LIMIT 10', base['sql'])
        salida = self._salida(
            'top 20', lectura=base['lectura'],
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(salida['vinculo'], 'continuacion')
        self.assertEqual(salida['sustituye'], ['corte'])
        self.assertIn('concepto', salida['hereda'])
        self.assertIn('periodo', salida['hereda'])
        self.assertIn('LIMIT 20', salida['sql'])
        self.assertIn('2024', salida['sql'])
        self.assertNotIn('2025', salida['sql'])
        todos = self._salida(
            'todos', lectura=salida['lectura'],
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(todos['vinculo'], 'continuacion')
        self.assertEqual(todos['sustituye'], ['corte'])
        self.assertTrue(todos['completo'])
        self.assertNotIn('LIMIT', todos['sql'])
        self.assertIn('GROUP BY', todos['sql'])
        self.assertIn('2024', todos['sql'])
        self.assertIn('datiadb_lineasalbarancliente', todos['sql'])

    def test_resumen_de_un_ano_es_la_venta_y_el_top_hereda_el_ano(self):
        campos, relaciones, columnas = _catalogo()
        lineas = _fuente(10, 'LineasAlbaranCliente', 'datiadb_lineasalbarancliente')
        articulos = _fuente(60, 'Articulos', 'datiadb_articulos')
        relaciones = list(relaciones) + [
            _rel(lineas, articulos, next(campo for campo in campos if campo.id == 2), next(campo for campo in campos if campo.id == 20)),
            _rel(lineas, articulos, next(campo for campo in campos if campo.id == 3), next(campo for campo in campos if campo.id == 22)),
        ]
        resumen = self._salida(
            'resumen 2024',
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(resumen['vinculo'], 'sola')
        self.assertIn('SUM', resumen['sql'])
        self.assertIn('datiadb_cabeceraalbarancliente', resumen['sql'])
        self.assertIn('2024', resumen['sql'])
        self.assertNotIn('proveedor', resumen['sql'])
        self.assertEqual(resumen['lectura']['periodo'], [2024])
        secciones = resumen['secciones']
        self.assertEqual([item['label'] for item in secciones], ['Artículos', 'Clientes'])
        self.assertIn('datiadb_lineasalbarancliente', secciones[0]['sql'])
        self.assertIn('LIMIT 10', secciones[0]['sql'])
        self.assertIn('2024', secciones[0]['sql'])
        self.assertIn('LIMIT 10', secciones[1]['sql'])
        self.assertIn('2024', secciones[1]['sql'])
        self.assertNotIn('proveedor', secciones[1]['sql'])
        top = self._salida(
            'top articulos',
            lectura=resumen['lectura'],
            campos=campos, relaciones=relaciones, columnas=columnas,
        )
        self.assertEqual(top['vinculo'], 'continuacion')
        self.assertIn('periodo', top['hereda'])
        self.assertIn('datiadb_lineasalbarancliente', top['sql'])
        self.assertIn('2024', top['sql'])
        self.assertNotIn('2025', top['sql'])
        self.assertIn('LIMIT 10', top['sql'])
        self.assertNotIn('proveedor', top['sql'])

    def test_la_frase_siguiente_que_se_entiende_sola_no_hereda(self):
        base = self._salida('ventas del ejercicio')
        salida = self._salida(
            'lista de todos los articulos con el codigo y la descripcion',
            lectura=base['lectura'],
        )
        self.assertEqual(salida['vinculo'], 'sola')
        self.assertEqual(salida['hereda'], [])
        self.assertNotIn('cabecera', salida['sql'])
        self.assertNotIn('2025', salida['sql'])

    def test_sin_lectura_aceptada_la_frase_incompleta_no_inventa_datos(self):
        salida = self._salida('y en 2024')
        self.assertIsNone(salida)

    def test_una_frase_ajena_no_devuelve_cifra(self):
        self.assertIsNone(self._salida('que tiempo hace hoy'))

    def test_la_revision_cubre_el_territorio_o_nombra_la_pieza(self):
        from datia.services.ai.examen_preguntas import cubrir_territorio, empaquetar_revision, revision_aceptada
        campos, relaciones, columnas = _catalogo()

        def consultar_fn(frase, lectura=None):
            return self._salida(frase, lectura, campos, relaciones, columnas)

        cubierto = cubrir_territorio(campos, relaciones, columnas, 2025, consultar_fn)
        self.assertLess(len(cubierto['preguntas']), len(campos) * max(1, len(relaciones)) * 15)
        self.assertTrue(any(item['pieza'].startswith('forma:') for item in cubierto['preguntas']))
        self.assertTrue(any(item['pieza'].endswith(':continuacion') for item in cubierto['preguntas']))
        solas = [item for item in cubierto['preguntas'] if item['pieza'].endswith(':sola')]
        self.assertTrue(solas)
        self.assertTrue(all(item['hereda'] == [] for item in solas))
        self.assertEqual(cubierto['probes'][1]['texto'], _MENSAJE)
        conjunto = next(item for item in cubierto['preguntas'] if item['pieza'] == 'forma:conjunto')
        self.assertNotIn('ejercicio', conjunto['sql'].lower())
        numero = next(item for item in cubierto['preguntas'] if item['pieza'] == 'forma:numero')
        self.assertIn('LIMIT 10', numero['sql'])
        self.assertNotIn('LIMIT', conjunto['sql'])
        vista = empaquetar_revision(1, 2025, cubierto['preguntas'], cubierto['probes'], cubierto['incompleta'], cubierto['falta'])
        self.assertEqual(vista['estado'], 'Preparada')
        self.assertIn('vinculo', vista['preguntas'][0])
        self.assertTrue(vista['probes'])
        self.assertFalse(revision_aceptada(True, 2, 2, 2, 2))
        self.assertTrue(revision_aceptada(False, 2, 2, 2, 2))
        if cubierto['incompleta']:
            self.assertTrue(cubierto['falta'])


class TestTopSinConcepto(SimpleTestCase):
    def _analizar(self, lectura=None):
        from datia.services.ai.ambiguity_analyzer import AmbiguityAnalyzer
        contexto = {'empresa': 1, 'ejercicio': 2025, 'ambiguity_threshold': 0.85}
        if lectura is not None:
            contexto['lectura'] = lectura
        with patch('datia.services.ai.ambiguity_analyzer.IntentDetector.detect', return_value={'temporal': None}), \
             patch('os.path.exists', return_value=False), \
             patch('os.makedirs'), \
             patch('builtins.open', unittest.mock.mock_open()):
            return AmbiguityAnalyzer().analyze('Top 20', contexto)

    def test_sin_lectura_pide_el_concepto(self):
        salida = self._analizar()
        self.assertTrue(salida['ambiguous'])
        self.assertEqual(salida['text'], 'Indica si buscas productos, clientes o proveedores.')

    def test_con_lectura_no_pide_el_concepto(self):
        salida = self._analizar({'conceptos': ['articulo'], 'periodo': [2024], 'corte': 10})
        self.assertFalse(salida['ambiguous'])
        self.assertNotEqual(salida['text'], 'Indica si buscas productos, clientes o proveedores.')

    def test_el_informe_muestra_el_ano_de_la_lectura(self):
        salida = ResponseFormatter.format_response(
            {
                'type': 'table',
                'label': 'ImporteNeto por Articulo',
                'sql': 'select 1',
                'lectura': {'periodo': [2024], 'clase': 'agrupacion'},
            },
            [{'label': 'CAFE', 'val': 10}],
            2025,
            20,
        )
        texto = salida.get('answer') or salida.get('text') or ''
        self.assertIn('2024', texto)
        self.assertNotIn('2025', texto)


def _clave_visible(rel):
    texto = f'{rel.from_field.field_name} {rel.from_field.business_name}'.lower()
    return not any(token in texto for token in ('empresa', 'ejercicio', 'serie', 'numero'))


if __name__ == '__main__':
    unittest.main()
