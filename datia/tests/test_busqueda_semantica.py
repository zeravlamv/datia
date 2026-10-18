import os
import sys
import time
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

from datia.services.query_builder import QueryBuilder
from datia.services.significado_service import SignificadoService, puntuar


def _fila(clase, identificador, texto, modelo='nomic-embed-text', vector=None):
    return SimpleNamespace(
        clase=clase,
        identificador=identificador,
        texto_indexado=texto,
        modelo=modelo,
        vector=vector if vector is not None else [1.0, 0.0, 0.0],
    )


class BusquedaSemanticaTests(SimpleTestCase):
    def setUp(self):
        self.context = {'empresa': 1, 'ejercicio': 2025, 'training_enabled': False}

    def test_una_entidad_usa_la_cifra_del_cliente_elegido(self):
        entidad = _fila('cliente', 'C9', 'Cafeteria Norte')
        vistos = []

        def handle(_question, _empresa, _ejercicio, party):
            vistos.append(party['name'])
            if party['name'] == 'C9':
                return {'reply': {'text': 'Ventas a Cafeteria Norte (C9): 10,00 €.', 'answer': '10'}}
            return {'reply': {'text': 'No encuentro un cliente llamado «cafeteria norte» en esta empresa.', 'answer': 'no'}}

        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_handle_named_party', side_effect=handle), \
             patch('datia.services.significado_service.SignificadoService.buscar', return_value={'status': 'encontrada', 'entidad': entidad}) as buscar:
            resultado = QueryBuilder.build_from_nl('ventas al cliente cafeteria norte', self.context)

        buscar.assert_called_once()
        self.assertIn('C9', vistos)
        self.assertIn('10,00 €', resultado['reply']['text'])
        self.assertIn('Cafeteria Norte', resultado['reply']['text'])

    def test_ambiguedad_ofrece_cinco_opciones_sin_cifra(self):
        opciones = [_fila('cliente', f'C{i}', f'Cliente {i}') for i in range(6)]
        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_handle_named_party', return_value={'reply': {'text': 'No encuentro un cliente.', 'answer': 'no'}}), \
             patch('datia.services.significado_service.SignificadoService.buscar', return_value={'status': 'ambiguo', 'opciones': opciones}):
            resultado = QueryBuilder.build_from_nl('ventas al cliente cafe', self.context)

        reply = resultado['reply']
        self.assertEqual(reply['type'], 'ambiguity_alert')
        self.assertLessEqual(len(reply['suggestions']), 5)
        self.assertEqual(len(reply['suggestions']), 5)
        for item in reply['suggestions']:
            self.assertNotIn('€', item['label'])
            self.assertNotIn('€', item['query'])
            self.assertIn('ventas al cliente', item['query'])

    def test_nombre_ausente_no_lleva_cifra(self):
        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_handle_named_party', return_value={'reply': {'text': 'No encuentro un cliente.', 'answer': 'no'}}), \
             patch('datia.services.significado_service.SignificadoService.buscar', return_value={'status': 'ninguna'}):
            resultado = QueryBuilder.build_from_nl('ventas al cliente zzzz', self.context)
        self.assertIn('catálogo', resultado['reply']['text'])
        self.assertNotIn('€', resultado['reply']['text'])

    def test_sin_empresa_pide_elegirla(self):
        contexto = {'empresa': None, 'ejercicio': 2025, 'training_enabled': False}
        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch('datia.services.query_builder.IntentDetector.detect', return_value={'grouping': None, 'tables': []}), \
             patch('datia.services.significado_service.SignificadoService.buscar') as buscar:
            resultado = QueryBuilder.build_from_nl('saldo de la cuenta bancos', contexto)
        buscar.assert_not_called()
        self.assertIn('Elige la empresa', resultado['reply']['text'])
        self.assertNotIn('€', resultado['reply']['text'])

    def test_reglas_fijas_no_llaman_al_significado(self):
        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_handle_named_party', return_value={'reply': {'text': 'Ventas a ACME: 20,00 €.', 'answer': '20'}}), \
             patch('datia.services.significado_service.SignificadoService.buscar') as buscar:
            resultado = QueryBuilder.build_from_nl('ventas al cliente ACME', self.context)
        buscar.assert_not_called()
        self.assertIn('20,00 €', resultado['reply']['text'])

        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_handle_stock_query', return_value={'reply': {'text': 'No encuentro el artículo «AB12» en esta empresa.', 'answer': 'no'}}), \
             patch('datia.services.significado_service.SignificadoService.buscar') as buscar_stock:
            QueryBuilder.build_from_nl('stock del AB12', self.context)
        buscar_stock.assert_not_called()

        columnas = {
            'codigoempresa': 'CodigoEmpresa',
            'ejerciciopedido': 'EjercicioPedido',
            'numeropedido': 'NumeroPedido',
            'fechapedido': 'FechaPedido',
            'importebruto': 'ImporteBruto',
            'importecoste': 'ImporteCoste',
            'cantidad': 'Cantidad',
            'nombre': 'Nombre',
        }

        def validar(_table, candidates):
            mejor = None
            for candidato in candidates or []:
                if candidato.lower() in columnas:
                    mejor = columnas[candidato.lower()]
                    break
            return mejor, columnas

        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_resolve_audit_cols', return_value={'company': 'CodigoEmpresa', 'year': 'EjercicioPedido', 'count': 'NumeroPedido'}), \
             patch.object(QueryBuilder, '_validate_table_columns', side_effect=validar), \
             patch('datia.services.significado_service.SignificadoService.buscar') as buscar_ranking:
            ranking = QueryBuilder.build_from_nl('Top 20 clientes en mayo 2025', self.context)
        buscar_ranking.assert_not_called()
        self.assertIn('LIMIT 20', ranking.get('sql') or '')
        self.assertIn('metrics_totales_empresa_ejercicio_cliente_mes', ranking.get('sql') or '')

    def test_mejor_cliente_usa_el_neto_calculado(self):
        with patch.object(QueryBuilder, '_memory_hit', return_value=None):
            ranking = QueryBuilder.build_from_nl('mejor cliente del 2025', self.context)
        sql = ranking.get('sql') or ''
        self.assertIn('metrics_totales_empresa_ejercicio_cliente', sql)
        self.assertIn('importe_neto_total AS val', sql)
        self.assertIn('LIMIT 1', sql)
        self.assertNotIn('importeneto', sql)

    def test_cafe_mas_popular_es_el_articulo_mas_vendido(self):
        with patch.object(QueryBuilder, '_memory_hit', return_value=None):
            ranking = QueryBuilder.build_from_nl('que cafe es es el mas popular', self.context)
        sql = ranking.get('sql') or ''
        self.assertIn('metrics_totales_empresa_ejercicio_articulo', sql)
        self.assertIn('importe_neto_total AS val', sql)
        self.assertIn('LIMIT 1', sql)
        self.assertNotIn('importeneto', sql)

    def test_kilos_de_cafe_no_es_el_ranking_en_euros(self):
        with patch.object(QueryBuilder, '_memory_hit', return_value=None):
            resultado = QueryBuilder.build_from_nl('cuantos kilos de cafe se han vendido en 2025', self.context)
        sql = resultado.get('sql') or ''
        self.assertEqual(resultado.get('type'), 'cantidad')
        self.assertIn('datiadb_lineasalbarancliente', sql)
        self.assertIn('importeneto / L.precio', sql)
        self.assertIn('cafe', sql)
        self.assertNotIn('metrics_totales_empresa_ejercicio_articulo', sql)

    def test_importe_medio_sale_del_total_de_la_empresa(self):
        class Cur:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, sql, params=None):
                self.params = params
            def fetchone(self):
                return (8687377.42, 5292)

        cursor = Cur()
        conexion = type('Conexion', (), {'cursor': lambda self: cursor})()
        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch('datia.services.query_builder.connections') as conexiones:
            conexiones.databases = {}
            conexiones.__getitem__.return_value = conexion
            resultado = QueryBuilder.build_from_nl('importe medio de albaranes de 2025', self.context)
        texto = resultado['reply']['text']
        self.assertIn('1.641,61', texto)
        self.assertIn('5.292', texto)
        self.assertIn('8.687.377,42', texto)

    def test_evolucion_mensual_lee_los_totales_por_mes(self):
        with patch.object(QueryBuilder, '_memory_hit', return_value=None):
            resultado = QueryBuilder.build_from_nl('ventas mensuales de 2025', self.context)
        sql = resultado.get('sql') or ''
        self.assertIn('metrics_totales_empresa_ejercicio_mes', sql)
        self.assertNotIn('cabecerapedidocliente', sql)
        self.assertIn('importe_neto_total AS val', sql)

        with patch.object(QueryBuilder, '_memory_hit', return_value=None), \
             patch.object(QueryBuilder, '_handle_year_analysis', return_value={'key': 'year_analysis', 'label': 'Análisis 2025: 1,00 €'}), \
             patch('datia.services.query_builder.IntentDetector.detect', return_value={'grouping': None, 'tables': []}), \
             patch('datia.services.significado_service.SignificadoService.buscar') as buscar_ano:
            analisis = QueryBuilder.build_from_nl('analisis del ejercicio 2025', self.context)
        buscar_ano.assert_not_called()
        self.assertEqual(analisis['key'], 'year_analysis')

    def test_vector_de_otro_modelo_o_longitud_no_se_compara(self):
        consulta = [1.0, 0.0, 0.0]
        otro_modelo = _fila('cliente', 'C1', 'Cafe', modelo='hash', vector=[1.0, 0.0, 0.0])
        otra_longitud = _fila('cliente', 'C2', 'Cafe', vector=[1.0, 0.0])
        self.assertEqual(puntuar(consulta, [otro_modelo, otra_longitud], 'nomic-embed-text')['status'], 'ninguna')

    def test_lote_en_construccion_no_devuelve_cifra(self):
        lote = SimpleNamespace(estado='construyendo', modelo='nomic-embed-text')
        with patch('datia.models.significado.SignificadoLote.objects') as objects:
            objects.filter.return_value.first.return_value = lote
            resultado = SignificadoService.buscar('cafe molido', 1, clase='articulo')
        self.assertEqual(resultado['status'], 'preparando')

    def test_ambiguedad_de_la_misma_clase_limita_a_cinco(self):
        consulta = [1.0, 0.0]
        filas = []
        for indice in range(6):
            filas.append(_fila('articulo', f'A{indice}', f'Cafe {indice}', vector=[1.0, 0.001 * indice]))
        resultado = puntuar(consulta, filas, 'nomic-embed-text', umbral=0.5, hueco=0.2)
        self.assertEqual(resultado['status'], 'ambiguo')
        self.assertEqual(len(resultado['opciones']), 5)

    def test_reindex_sin_modelo_no_deja_el_lote_listo(self):
        with patch.object(SignificadoService, 'vector_de', return_value=None):
            resultado = SignificadoService.reindex(1)
        self.assertFalse(resultado['ok'])
        self.assertIn('nomic-embed-text', resultado['message'])
        self.assertIn('no queda listo', resultado['message'])

    def test_comparacion_de_veinte_mil_textos_cabe_en_cinco_segundos(self):
        consulta = [1.0, 0.0, 0.0, 0.0]
        filas = [_fila('cliente', str(indice), f'Cliente {indice}', vector=[0.0, 1.0, 0.0, 0.0]) for indice in range(20000)]
        filas.append(_fila('cliente', 'C1', 'Cafe real', vector=[1.0, 0.0, 0.0, 0.0]))
        inicio = time.perf_counter()
        resultado = puntuar(consulta, filas, 'nomic-embed-text')
        duracion = time.perf_counter() - inicio
        self.assertLess(duracion, 5)
        self.assertEqual(resultado['status'], 'encontrada')
        self.assertEqual(resultado['entidad'].identificador, 'C1')


class AutoLearnTests(SimpleTestCase):
    def test_rechaza_sql_sobre_la_columna_vacia(self):
        from datia.services.ai.auto_learn import AutoLearn
        sql = AutoLearn._aceptar(
            'SELECT importeneto AS val FROM datiadb_cabeceraalbarancliente WHERE empresa = 1 AND ejercicio = 2025',
            1,
            2025,
        )
        self.assertIsNone(sql)

    def test_guarda_la_consulta_cuando_el_total_tiene_cifra(self):
        from datia.services.ai.auto_learn import AutoLearn
        bueno = (
            "SELECT 'total' AS label, importe_neto_total AS val, importe_coste_total AS coste, "
            'albaranes_count AS ops FROM metrics_totales_empresa_ejercicio '
            'WHERE empresa = 1 AND ejercicio = 2025'
        )

        class Cur:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, sql):
                self.sql = sql
            def fetchone(self):
                return ('total', 10, 4, 2)

        conexion = type('Conexion', (), {'cursor': lambda self: Cur()})()
        with patch('datia.services.ai.auto_learn.connections') as conexiones, \
             patch.object(AutoLearn, '_pedir_sql', return_value=bueno), \
             patch.object(AutoLearn, '_guardar') as guardar:
            conexiones.databases = {}
            conexiones.__getitem__.return_value = conexion
            resultado = AutoLearn.aprender('cuanto se vendio en total', 1, 2025)
        self.assertIn('metrics_totales_empresa_ejercicio', resultado['sql'])
        guardar.assert_called_once()


if __name__ == '__main__':
    unittest.main()
