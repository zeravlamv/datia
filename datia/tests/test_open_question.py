import datetime
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

from datia.services.ai.comparison import aviso_coste_y_hueco, celda
from datia.services.ai_service import _respuesta_tiene_valor
from datia.services.ai.nlq_catalog import cubre_la_pregunta, informe_adelantado, match_intent
from datia.services.ai.open_question import OpenQuestion
from datia.services.ai.semantic_plan import SemanticPlan
from datia.services.ai.profundizar import Profundizar
from datia.services.query_builder import QueryBuilder


class TestOrigenSiempre(SimpleTestCase):
    def test_el_ranking_de_productos_lleva_tabla_y_consulta(self):
        from datia.services.ai.presentacion import asegurar_origen
        salida = asegurar_origen({
            'type': 'report',
            'key': 'ventas_top_productos',
            'answer': 'Mejores productos del ejercicio 2025.',
            'query': 'los 10 mejores productos 2025',
        }, 1, 2025)
        self.assertIn('metrics_totales_empresa_ejercicio_articulo', salida['origen']['tabla'])
        self.assertIn('venta neta', salida['origen']['formula'])
        self.assertIn('ejercicio = 2025', salida['origen']['consulta'])

    def test_no_pisa_un_origen_que_ya_existe(self):
        from datia.services.ai.presentacion import asegurar_origen
        salida = asegurar_origen({
            'type': 'report',
            'key': 'ventas_top_productos',
            'origen': {'tabla': 'ya', 'formula': 'hecha', 'filtros': [], 'consulta': 'SELECT 1'},
        }, 1, 2025)
        self.assertEqual(salida['origen']['tabla'], 'ya')

    def test_la_ambiguedad_no_lleva_origen(self):
        from datia.services.ai.presentacion import asegurar_origen
        salida = asegurar_origen({'type': 'ambiguity_alert', 'answer': 'Indica si buscas productos.'}, 1, 2025)
        self.assertNotIn('origen', salida)


class TestCubreLaPregunta(SimpleTestCase):
    def test_mejores_clientes_sigue_en_el_catalogo(self):
        intent = match_intent('mejores clientes de 2025')
        self.assertEqual(intent['intent_id'], 'ventas.top_clientes')
        self.assertTrue(cubre_la_pregunta('mejores clientes de 2025', intent['intent_id']))

    def test_clientes_y_productos_no_caben_en_un_solo_informe(self):
        intent = match_intent('mejores clientes y productos de 2025')
        self.assertEqual(intent['intent_id'], 'ventas.top_clientes')
        self.assertFalse(cubre_la_pregunta('mejores clientes y productos de 2025', intent['intent_id']))

    def test_ventas_y_compras_no_caben_en_el_resumen_de_ventas(self):
        self.assertFalse(cubre_la_pregunta('ventas y compras de 2025', 'ventas.resumen_ejercicio'))

    def test_el_chat_no_adelanta_el_informe_comercial(self):
        from datia.services.ai.reglas_negocio import decidir
        for frase in ('resumen 2024', 'top articulos', 'resumen de ingresos'):
            self.assertIsNone(informe_adelantado(frase))
            self.assertIsNone(decidir(frase, ejercicio=2024))

    def test_el_informe_con_nombre_sale_de_las_reglas(self):
        from datia.services.ai.reglas_negocio import decidir
        for frase in ('resumen financiero', 'tesoreria', 'presupuesto 2025', 'ratios', 'coste por cada 100'):
            self.assertIsNone(informe_adelantado(frase))
            self.assertEqual(decidir(frase, ejercicio=2025)['motor'], 'informe')
        analisis = decidir('analisis financiero del 2025', ejercicio=2024)
        self.assertEqual(analisis['informe'], 'finanzas.resumen_ejercicio')
        self.assertEqual(analisis['anio'], 2025)


class TestPlantillasAbiertas(SimpleTestCase):
    def test_top_clientes_no_lo_absorbe_la_plantilla(self):
        self.assertIsNone(OpenQuestion.plantilla('Top 20 clientes en mayo 2025', 1, 2025, 20))

    def test_el_trimestre_lo_sigue_resolviendo_el_constructor(self):
        self.assertIsNone(OpenQuestion.plantilla('Margen por cliente del último trimestre 2025', 1, 2025, 10))

    def test_margen_negativo_filtra_coste_mayor_que_venta(self):
        hit = OpenQuestion.plantilla('clientes con margen negativo en 2025', 1, 2025, 10)
        sql = hit['sql'].lower()
        self.assertIn('metrics_totales_empresa_ejercicio_cliente', sql)
        self.assertIn('importe_coste_total > importe_neto_total', sql)
        self.assertIn('empresa = 1', sql)
        self.assertIn('ejercicio = 2025', sql)

    def test_ventas_y_compras_leen_las_dos_metricas(self):
        hit = OpenQuestion.plantilla('ventas y compras de 2025', 1, 2025, 10)
        sql = hit['sql'].lower()
        self.assertIn('metrics_totales_empresa_ejercicio ', sql)
        self.assertIn('metrics_totales_empresa_ejercicio_compra', sql)

    def test_cuantos_clientes_es_un_conteo(self):
        hit = OpenQuestion.plantilla('cuantos clientes en 2025', 1, 2025, 10)
        self.assertEqual(hit['key'], 'conteo')
        self.assertIn('count(*)', hit['sql'].lower())
        self.assertEqual(hit['origen']['tabla'], 'metrics_totales_empresa_ejercicio_cliente')
        self.assertIn('importe neto', hit['origen']['formula'])

    def test_cuanto_deben_se_distingue_de_un_pedido_pendiente(self):
        self.assertEqual(OpenQuestion.clasificar_deuda('cuanto deben los clientes'), 'C')
        self.assertEqual(OpenQuestion.clasificar_deuda('cuanto debemos a los proveedores'), 'P')
        self.assertEqual(OpenQuestion.clasificar_deuda('pendiente de cobro'), 'C')
        self.assertEqual(OpenQuestion.clasificar_deuda('pendiente de pago'), 'P')
        self.assertIsNone(OpenQuestion.clasificar_deuda('pedidos pendientes de servir'))
        self.assertIsNone(OpenQuestion.clasificar_deuda('margen por cliente del ultimo trimestre'))

    def test_fuera_de_negocio_no_inventa_sql(self):
        hit = OpenQuestion.responder('que tiempo hace mañana', 1, 2025, 10)
        self.assertIn('ventas', hit['reply']['text'])
        self.assertNotIn('sql', hit)


class TestDeudaEnCartera(SimpleTestCase):
    databases = {'analytics'}

    def test_la_respuesta_suma_lo_pendiente_de_cobro(self):
        hit = OpenQuestion.plantilla('cuanto deben los clientes', 1, 2025, 10)
        reply = hit['reply']
        self.assertEqual(reply['key'], 'deuda_clientes')
        self.assertGreater(reply['kpis'][0]['value'], 1000)
        self.assertNotIn('sql', reply)
        self.assertIn('Pendiente', reply['table']['columns'][1])
        self.assertTrue(reply['table']['rows'])

    def test_la_deuda_no_sale_como_pedidos(self):
        res = QueryBuilder.build_from_nl(
            'cuanto deben los clientes',
            {'empresa': 1, 'ejercicio': 2025, 'training_enabled': False, 'limit': 10},
        )
        self.assertEqual(res['reply']['key'], 'deuda_clientes')
        self.assertNotIn('cabecerapedidocliente', str(res).lower())


class TestRankingProveedor(SimpleTestCase):
    databases = {'analytics'}

    def test_al_que_mas_le_compro_es_el_mayor_proveedor(self):
        hit = OpenQuestion.plantilla('proveedor al que mas le compro', 1, 2025, 10)
        reply = hit['reply']
        self.assertEqual(reply['key'], 'ranking_proveedores')
        self.assertIn('COPROCAFE', reply['answer'])
        self.assertGreater(reply['kpis'][0]['value'], 1_000_000)
        self.assertNotIn('sql', reply)
        self.assertEqual(len(reply['table']['rows']), 1)

    def test_no_cae_en_la_evolucion_mensual_de_cabeceras(self):
        res = QueryBuilder.build_from_nl(
            'proveedor al que mas le compro',
            {'empresa': 1, 'ejercicio': 2025, 'training_enabled': True, 'limit': 10},
        )
        self.assertEqual(res['reply']['key'], 'ranking_proveedores')
        self.assertNotIn('cabeceraalbaranproveedor', str(res).lower())

    def test_un_importe_a_cero_tambien_es_resultado(self):
        self.assertTrue(_respuesta_tiene_valor({
            'type': 'table',
            'data': [{'label': '1', 'val': 0, 'coste': 0, 'ops': 1}],
        }))
        self.assertTrue(_respuesta_tiene_valor({
            'type': 'report',
            'kpis': [{'label': 'Compra', 'value': 0, 'suffix': '€'}],
        }))
        self.assertTrue(_respuesta_tiene_valor({
            'type': 'report',
            'kpis': [{'label': 'Compra', 'value': 1618676.66, 'suffix': '€'}],
        }))
        self.assertTrue(_respuesta_tiene_valor({
            'type': 'no_data_option',
            'text': 'No hay datos de ventas en 2025.',
            'answer': 'No hay datos de ventas en 2025.',
        }))
        self.assertFalse(_respuesta_tiene_valor({
            'type': 'text',
            'text': 'No he podido preparar una consulta segura para esta pregunta.',
        }))

    def test_la_consulta_sin_importe_no_se_repite(self):
        contexto = {'empresa': 1, 'ejercicio': 2025, 'training_enabled': False, 'limit': 10}
        primero = QueryBuilder.build_from_nl('gastos del ejercicio', contexto)
        self.assertIn('cabeceraalbaranproveedor', primero['sql'].lower())
        contexto['_sql_descartada'] = primero['sql']
        segundo = QueryBuilder.build_from_nl('gastos del ejercicio', contexto)
        sql2 = (segundo or {}).get('sql') or ''
        self.assertNotIn('cabeceraalbaranproveedor', sql2.lower())

    def test_el_proveedor_con_cifra_no_dispara_el_autoentreno(self):
        hit = OpenQuestion.plantilla('proveedor al que mas le compro', 1, 2025, 10)
        self.assertTrue(_respuesta_tiene_valor(hit['reply']))
        self.assertIn('COPROCAFE', hit['reply']['answer'])

    def test_a_quien_mas_le_compro_tambien_es_proveedor(self):
        self.assertEqual(OpenQuestion.clasificar_ranking_proveedor('a quien mas le compro'), 'DESC')
        self.assertIsNone(OpenQuestion.clasificar_ranking_proveedor('evolucion de las compras'))


class TestKilosPorProductoYCliente(SimpleTestCase):
    databases = {'analytics'}

    def test_producto_y_cliente_no_son_el_total_de_la_empresa(self):
        res = QueryBuilder.build_from_nl(
            'de que producto se venden mas kilos y a quien',
            {'empresa': 1, 'ejercicio': 2025, 'training_enabled': False, 'limit': 10},
        )
        reply = res['reply']
        self.assertEqual(reply['key'], 'cantidad_producto_cliente')
        self.assertGreater(reply['kpis'][0]['value'], 1)
        self.assertIn('producto', reply['answer'])
        self.assertIn('cliente', reply['answer'])
        self.assertNotIn('887.490', reply['answer'])
        self.assertTrue(reply['table']['rows'])

    def test_producto_menos_vendido_es_el_articulo_de_menor_venta(self):
        res = QueryBuilder.build_from_nl(
            'producto menos vendido',
            {'empresa': 1, 'ejercicio': 2025, 'training_enabled': False, 'limit': 10},
        )
        sql = (res or {}).get('sql') or ''
        self.assertEqual(res.get('key'), 'ranking_articulo')
        self.assertIn('metrics_totales_empresa_ejercicio_articulo', sql.lower())
        self.assertIn('importe_neto_total > 0', sql)
        self.assertIn('ASC', sql)
        self.assertIn('LIMIT 1', sql)
        self.assertNotIn('reply', res)

    def test_el_total_de_kilos_sigue_sin_producto_ni_cliente(self):
        res = QueryBuilder.build_from_nl(
            'cuantos kilos se han vendido en 2025',
            {'empresa': 1, 'ejercicio': 2025, 'training_enabled': False, 'limit': 10},
        )
        self.assertEqual(res.get('type'), 'cantidad')
        self.assertNotIn('reply', res)


class TestNoRankingPorLaPalabraCliente(SimpleTestCase):
    def test_clientes_sin_metrica_no_es_desglose_de_ventas(self):
        self.assertFalse(QueryBuilder._pide_desglose_comercial('cuanto deben los clientes'))
        self.assertFalse(QueryBuilder._pide_desglose_comercial('listado de clientes'))
        self.assertTrue(QueryBuilder._pide_desglose_comercial('margen por cliente del ultimo trimestre'))


class TestModeloEscribeLaConsulta(SimpleTestCase):
    def test_filas_a_cero_se_devuelven(self):
        plan = {
            'fuente': 'ventas_ejercicio', 'metrica': 'importe',
            'orden': 'desc', 'limite': 10, 'filtro': 'ninguno',
        }
        fila = {'label': 'Ejercicio', 'val': 0, 'coste': 0, 'ops': 1}
        with patch.object(SemanticPlan, 'desde_frase', return_value=None), \
             patch.object(SemanticPlan, 'desde_modelo', return_value=plan), \
             patch.object(OpenQuestion, '_ejecutar', return_value=[fila]), \
             patch.object(OpenQuestion, '_guardar') as guardar:
            res = OpenQuestion.responder('ventas del articulo inventado 2099', 1, 2099, 10)
        self.assertIn('metrics_totales_empresa_ejercicio', res['sql'])
        self.assertNotIn('reply', res)
        self.assertEqual(res['plan']['fuente'], 'ventas_ejercicio')
        guardar.assert_called_once()

    def test_sin_filas_informa_que_no_hay_datos(self):
        plan = {
            'fuente': 'ventas_ejercicio', 'metrica': 'importe',
            'orden': 'desc', 'limite': 10, 'filtro': 'ninguno',
        }
        with patch.object(SemanticPlan, 'desde_frase', return_value=None), \
             patch.object(SemanticPlan, 'desde_modelo', return_value=plan), \
             patch.object(OpenQuestion, '_ejecutar', return_value=[]):
            res = OpenQuestion.responder('ventas del articulo inventado 2099', 1, 2099, 10)
        self.assertIn('no hay datos', res['reply']['text'].lower())
        self.assertNotIn('distinto de cero', res['reply']['text'].lower())

    def test_si_se_fuerza_el_modelo_no_repite_la_plantilla(self):
        with patch.object(SemanticPlan, 'desde_modelo', return_value=None) as pedido:
            res = OpenQuestion.responder(
                'proveedor al que mas le compro', 1, 2025, 10, forzar_modelo=True,
            )
        pedido.assert_called_once()
        self.assertNotIn('COPROCAFE', str(res))
        self.assertIn('reply', res)


class TestAceptarSqlAbierto(SimpleTestCase):
    def test_rechaza_tablas_de_lineas_y_funciones_peligrosas(self):
        sql = (
            "SELECT nombre AS label, importe_neto_total AS val FROM datiadb_lineasalbarancliente "
            "WHERE empresa = 1 AND ejercicio = 2025"
        )
        self.assertIsNone(OpenQuestion._aceptar(sql, 1, 2025))
        peligro = (
            "SELECT pg_read_file('x') AS label, 1 AS val FROM metrics_totales_empresa_ejercicio "
            "WHERE empresa = 1 AND ejercicio = 2025"
        )
        self.assertIsNone(OpenQuestion._aceptar(peligro, 1, 2025))

    def test_acepta_un_select_de_metricas_y_limita(self):
        sql = (
            "SELECT nombre AS label, importe_neto_total AS val, importe_coste_total AS coste, "
            "albaranes_count AS ops FROM metrics_totales_empresa_ejercicio_cliente "
            "WHERE empresa = 1 AND ejercicio = 2025 ORDER BY val DESC LIMIT 500"
        )
        aceptado = OpenQuestion._aceptar(sql, 1, 2025)
        self.assertIn('LIMIT 100', aceptado)
        self.assertIn('metrics_totales_empresa_ejercicio_cliente', aceptado)


class TestPlanSemantico(SimpleTestCase):
    def test_postgres_usa_limit_y_sqlserver_usa_top(self):
        plan = {
            'fuente': 'ventas_cliente', 'metrica': 'margen',
            'orden': 'asc', 'limite': 5, 'filtro': 'margen_negativo',
        }
        pg = SemanticPlan.compilar(plan, 1, 2025, 'postgres')
        ss = SemanticPlan.compilar(plan, 1, 2025, 'sqlserver')
        self.assertIn('LIMIT 5', pg)
        self.assertNotIn('TOP ', pg)
        self.assertIn('TOP 5', ss)
        self.assertNotIn('LIMIT', ss)
        self.assertIn('metrics_totales_empresa_ejercicio_cliente', pg)
        self.assertIn('importe_neto_total - importe_coste_total', ss)
        self.assertIn('empresa = 1', pg)
        self.assertIn('ejercicio = 2025', ss)

    def test_un_plan_ajeno_no_compila(self):
        self.assertIsNone(SemanticPlan.compilar({'fuente': 'datiadb_clientes', 'metrica': 'importe'}, 1, 2025))
        self.assertIsNone(SemanticPlan.leer_json('no es json', 10))

    def test_precio_medio_no_es_el_total_de_ventas(self):
        plan = SemanticPlan.desde_frase('precio medio de venta en 2025', 10)
        self.assertEqual(plan['fuente'], 'ventas_ejercicio')
        self.assertEqual(plan['metrica'], 'precio_medio')
        sql = SemanticPlan.compilar(plan, 1, 2025, 'postgres')
        self.assertIn('NULLIF(albaranes_count, 0)', sql)
        self.assertNotEqual(plan['metrica'], 'importe')
        total = SemanticPlan.desde_frase('ventas de 2025', 10)
        self.assertEqual(total['metrica'], 'importe')
        suelto = {
            'text': 'Precio medio de venta en 2025: 1.641,61 € por albarán.',
            'answer': 'Precio medio de venta en 2025: 1.641,61 € por albarán.',
        }
        self.assertTrue(_respuesta_tiene_valor(suelto))
        self.assertEqual(QueryBuilder._party_reply(suelto['text'])['reply']['type'], 'text')

    def test_la_frase_de_margen_por_cliente_es_un_plan(self):
        plan = SemanticPlan.desde_frase('margen por cliente', 10)
        self.assertEqual(plan['fuente'], 'ventas_cliente')
        self.assertEqual(plan['metrica'], 'margen')

    def test_kilos_stock_y_lineas_se_compilan_en_los_dos_dialectos(self):
        kilos = SemanticPlan.desde_frase('kilos de cafe vendidos', 10)
        self.assertEqual(kilos['fuente'], 'kilos_articulo')
        self.assertEqual(kilos['texto'], 'cafe')
        pg = SemanticPlan.compilar(kilos, 1, 2025, 'postgres')
        ss = SemanticPlan.compilar(kilos, 1, 2025, 'sqlserver')
        self.assertIn('importeneto / L.precio', pg)
        self.assertIn("LIKE '%cafe%'", pg)
        self.assertIn('LIMIT 10', pg)
        self.assertIn('TOP 10', ss)
        self.assertNotIn('LIMIT', ss)
        self.assertNotIn('ILIKE', pg)

        stock = SemanticPlan.desde_frase('stock del 10045', 10)
        self.assertEqual(stock['fuente'], 'stock_articulo')
        self.assertEqual(stock['codigo'], '10045')
        sql_stock = SemanticPlan.compilar(stock, 1, 2025, 'postgres')
        self.assertIn('datia_acumulados_stocks', sql_stock)
        self.assertIn('unidadsaldo', sql_stock)
        self.assertIn("LOWER(articulo) = '10045'", sql_stock)

        lineas = SemanticPlan.desde_frase('detalle de lineas de albaran', 10)
        self.assertEqual(lineas['fuente'], 'lineas_venta')
        sql_lineas = SemanticPlan.compilar(lineas, 1, 2025, 'sqlserver')
        self.assertIn('datiadb_lineasalbarancliente', sql_lineas)
        self.assertIn('L.importeneto AS val', sql_lineas)
        self.assertIn('TOP 10', sql_lineas)
        self.assertIsNone(SemanticPlan.desde_frase('litros vendidos', 10))
        plan_malo = SemanticPlan.normalizar({
            'fuente': 'stock_articulo', 'metrica': 'stock', 'codigo': "x'; drop",
        }, 10)
        self.assertNotIn('codigo', plan_malo)

    def test_el_json_del_modelo_se_recorta_al_catalogo(self):
        texto = '```json\n{"fuente":"compras_proveedor","metrica":"importe","orden":"desc","limite":500,"filtro":"ninguno"}\n```'
        plan = SemanticPlan.leer_json(texto, 10)
        self.assertEqual(plan['fuente'], 'compras_proveedor')
        self.assertEqual(plan['limite'], 100)


class TestAvisosDeComparacion(SimpleTestCase):
    def test_hueco_de_ano_anterior_no_es_cero(self):
        self.assertEqual(celda(False, 0), 'sin datos')
        self.assertEqual(celda(True, 0), 0)

    def test_avisa_si_el_coste_supera_la_venta(self):
        texto, debil = aviso_coste_y_hueco(
            [{'value': 100, 'cost': 240, 'hay_anterior': False}],
            2024,
        )
        self.assertTrue(debil)
        self.assertIn('supera la venta', texto)
        self.assertIn('sin datos', texto)


class TestProfundizar(SimpleTestCase):
    databases = {'analytics'}

    def test_la_deuda_se_parte_en_vencido_y_por_vencer(self):
        detalle = Profundizar.responder('cuanto deben los clientes', 1, 2025)
        self.assertTrue(detalle['profundizado'])
        self.assertEqual(detalle['table']['columns'][1], 'Vencido (€)')
        self.assertGreater(len(detalle['table']['rows']), 10)
        self.assertGreater(detalle['kpis'][0]['value'], 1000)

    def test_un_ranking_baja_a_meses(self):
        detalle = Profundizar.responder('mejores clientes de 2025', 1, 2025)
        self.assertEqual(detalle['key'], 'detalle_meses_venta')
        self.assertIn('Enero', [fila[0] for fila in detalle['table']['rows']])

    def test_los_kilos_no_repiten_una_tabla_de_ventas(self):
        detalle = Profundizar.responder('cuantos kilos de cafe se han vendido en 2025', 1, 2025)
        self.assertEqual(detalle['type'], 'text')
        self.assertNotIn('table', detalle)


class TestVentasDeUnDia(SimpleTestCase):
    def test_ayer_es_el_dia_anterior_y_no_el_ejercicio(self):
        hoy = datetime.date(2026, 10, 21)
        self.assertIsNone(QueryBuilder._dia_natural('ventas por mes de 2025', hoy))
        self.assertIsNone(QueryBuilder._dia_natural('compras de ayer', hoy))
        dia, nombre = QueryBuilder._dia_natural('dime las ventas que hicimos ayer', hoy)
        self.assertEqual(nombre, 'ayer')
        self.assertEqual(dia, datetime.date(2026, 10, 20))
        self.assertEqual(QueryBuilder._dia_natural('ventas de hoy', hoy)[0], hoy)
        self.assertEqual(QueryBuilder._dia_natural('albaranes de anteayer', hoy)[0], datetime.date(2026, 10, 19))

    def test_la_consulta_filtra_el_dia_y_la_empresa(self):
        hoy = datetime.date(2026, 10, 21)
        cur = _CursorDia((1234.5, 2))
        with patch('datia.services.query_builder.connections') as conexiones:
            conexiones.databases = {}
            conexiones.__getitem__.return_value.cursor.return_value = cur
            respuesta = QueryBuilder._ventas_de_un_dia('dime las ventas que hicimos ayer', 1, hoy)
        texto = respuesta['reply']['answer']
        self.assertIn('20 de octubre de 2026', texto)
        self.assertIn('1.234,50 €', texto)
        self.assertIn('2 albaranes', texto)
        self.assertNotIn('ejercicio', cur.sql.lower())
        self.assertEqual(cur.params[0], 1)
        self.assertEqual(cur.params[1], datetime.date(2026, 10, 20))
        self.assertEqual(cur.params[2], datetime.date(2026, 10, 21))
        self.assertTrue(_respuesta_tiene_valor(respuesta['reply']))

    def test_sin_albaranes_no_cambia_al_grafico_del_ano(self):
        cur = _CursorDia((0, 0))
        with patch('datia.services.query_builder.connections') as conexiones:
            conexiones.databases = {}
            conexiones.__getitem__.return_value.cursor.return_value = cur
            respuesta = QueryBuilder._construir_consulta(
                'dime las ventas que hicimos ayer',
                {'empresa': 2, 'ejercicio': 2025},
            )
        self.assertIn('no hubo ventas', respuesta['reply']['answer'])
        self.assertNotIn('metrics_totales', cur.sql)
        self.assertTrue(_respuesta_tiene_valor(respuesta['reply']))

    def test_el_ultimo_dia_es_la_fecha_mas_reciente_con_albaranes(self):
        self.assertFalse(QueryBuilder._pide_ultimo_dia('ventas por mes de 2025'))
        self.assertFalse(QueryBuilder._pide_ultimo_dia('compras del ultimo dia'))
        self.assertTrue(QueryBuilder._pide_ultimo_dia('el último día de ventas'))
        cur = _CursorCola([
            (datetime.datetime(2026, 9, 3, 18, 30),),
            (800.25, 4),
        ])
        with patch('datia.services.query_builder.connections') as conexiones:
            conexiones.databases = {}
            conexiones.__getitem__.return_value.cursor.return_value = cur
            respuesta = QueryBuilder._construir_consulta(
                'el último día de ventas',
                {'empresa': 2, 'ejercicio': 2025},
            )
        texto = respuesta['reply']['answer']
        self.assertIn('Último día de ventas', texto)
        self.assertIn('3 de septiembre de 2026', texto)
        self.assertIn('800,25 €', texto)
        self.assertIn('4 albaranes', texto)
        self.assertNotIn('ejercicio', cur.llamadas[0][0].lower())
        self.assertNotIn('metrics_totales', cur.llamadas[1][0])
        self.assertEqual(cur.llamadas[1][1], [2, datetime.date(2026, 9, 3), datetime.date(2026, 9, 4)])
        self.assertTrue(_respuesta_tiene_valor(respuesta['reply']))

    def test_el_ultimo_albaran_es_el_documento_no_el_resumen_del_ano(self):
        self.assertTrue(QueryBuilder._pide_ultimo_albaran('el ultimo albaran'))
        self.assertTrue(QueryBuilder._pide_ultimo_albaran('el último albarán'))
        self.assertFalse(QueryBuilder._pide_ultimo_albaran('el último día de ventas'))
        self.assertFalse(QueryBuilder._pide_ultimo_albaran('ultimo albaran de proveedor'))
        cur = _CursorCola([
            (datetime.datetime(2026, 9, 3, 18, 30),),
            (datetime.datetime(2026, 9, 3, 18, 30), 'A', 4521, 'CAFES RONDA', '100', 1234.5),
        ])
        with patch('datia.services.query_builder.connections') as conexiones:
            conexiones.databases = {}
            conexiones.__contains__.return_value = True
            conexiones.__getitem__.return_value.vendor = 'postgresql'
            conexiones.__getitem__.return_value.cursor.return_value = cur
            respuesta = QueryBuilder._construir_consulta(
                'el ultimo albaran',
                {'empresa': 2, 'ejercicio': 2025},
            )
        texto = respuesta['reply']['answer']
        self.assertIn('Último albarán', texto)
        self.assertIn('3 de septiembre de 2026', texto)
        self.assertIn('serie A', texto)
        self.assertIn('número 4521', texto)
        self.assertIn('CAFES RONDA', texto)
        self.assertIn('1.234,50 €', texto)
        self.assertNotIn('Resumen Ejecutivo', texto)
        self.assertNotIn('ejercicio', cur.llamadas[0][0].lower())
        self.assertNotIn('metrics_totales', cur.llamadas[1][0])
        self.assertIn('ORDER BY numeroalbaran DESC', cur.llamadas[1][0])
        self.assertEqual(cur.llamadas[1][1][0], 2)
        self.assertEqual(cur.llamadas[1][1][1], datetime.date(2026, 9, 3))
        self.assertTrue(_respuesta_tiene_valor(respuesta['reply']))


class _CursorCola:
    def __init__(self, filas):
        self.filas = list(filas)
        self.llamadas = []
        self.sql = ''
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params
        self.llamadas.append((sql, params))

    def fetchone(self):
        return self.filas.pop(0)


class _CursorDia:
    def __init__(self, fila):
        self.fila = fila
        self.sql = ''
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self.fila


if __name__ == '__main__':
    unittest.main()
