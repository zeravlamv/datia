import re
import unittest
from unittest.mock import patch


class TestAIQueries(unittest.TestCase):
    def setUp(self):
        self.empresa = 1
        self.ejercicio = 2025
        self.context = {'empresa': self.empresa, 'ejercicio': self.ejercicio, 'training_enabled': False}

    def _mock_validate_columns(self, table_name: str, candidates):
        cols = {
            'codigoempresa': 'CodigoEmpresa',
            'ejerciciopedido': 'EjercicioPedido',
            'numeropedido': 'NumeroPedido',
            'fechapedido': 'FechaPedido',
            'importebruto': 'ImporteBruto',
            'importecoste': 'ImporteCoste',
            'cantidad': 'Cantidad',
            'nombre': 'Nombre',
            'descripcion': 'Descripcion',
        }
        best = None
        for c in candidates or []:
            lc = c.lower()
            if lc in cols:
                best = cols[lc]
                break
        return best, cols

    def _mock_audit_cols(self, table_name: str):
        return {'company': 'CodigoEmpresa', 'year': 'EjercicioPedido', 'count': 'NumeroPedido'}

    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_ranking_top_20_clientes_mayo(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        q = "Top 20 clientes en mayo 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertIn('LIMIT 20', sql)
        self.assertRegex(sql, r'EXTRACT\(MONTH FROM .*?\) BETWEEN 5 AND 5')
        self.assertRegex(sql, r'ORDER BY 2 DESC')

    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_cliente_compra_menos_asc(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        q = "Qué cliente compra menos en 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertRegex(sql, r'ORDER BY 2 ASC')
        self.assertRegex(sql, r'EXTRACT\(YEAR FROM .*?\) = 2025')

    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_margen_por_cliente_ultimo_trimestre(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        q = "Margen por cliente del último trimestre 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertRegex(sql, r'EXTRACT\(QUARTER FROM .*?\) = 4')
        im = res.get('intent_meta') or {}
        self.assertEqual(im.get('metric'), 'margin')
    
    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_mejor_producto_2025(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        q = "Mejor producto del 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertRegex(sql, r'LIMIT 1')
        self.assertRegex(sql, r'ORDER BY 2 DESC')
        self.assertRegex(sql, r'EXTRACT\(YEAR FROM .*?\) = 2025')
    
    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_peor_producto_2025(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        q = "Peor producto del 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertRegex(sql, r'LIMIT 1')
        self.assertRegex(sql, r'ORDER BY 2 ASC')
        self.assertRegex(sql, r'EXTRACT\(YEAR FROM .*?\) = 2025')
    
    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_mejor_cliente_q2_2025(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        q = "Mejor cliente Q2 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertRegex(sql, r'LIMIT 1')
        self.assertRegex(sql, r'ORDER BY 2 DESC')
        self.assertRegex(sql, r'EXTRACT\(QUARTER FROM .*?\) = 2|EXTRACT\(MONTH FROM .*?\) BETWEEN 4 AND 6')
        self.assertRegex(sql, r'EXTRACT\(YEAR FROM .*?\) = 2025')

    @patch('datia.services.query_builder.QueryBuilder._resolve_audit_cols')
    @patch('datia.services.query_builder.QueryBuilder._validate_table_columns')
    def test_ten_thousand_nl_queries(self, m_validate, m_audit):
        from datia.services.query_builder import QueryBuilder
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols
        for i in range(1, 10001):
            if i % 4 == 0:
                q = f"Top 20 clientes en mayo 2025 variación {i}"
            elif i % 4 == 1:
                q = f"Mejor producto del 2025 caso {i}"
            elif i % 4 == 2:
                q = f"Qué cliente compra menos en 2025 ejemplo {i}"
            else:
                q = f"Margen por cliente del último trimestre 2025 id {i}"
            res = QueryBuilder.build_from_nl(q, self.context)
            self.assertIsInstance(res, dict)
            self.assertTrue((res.get("sql") or "").strip(), f"SQL vacío para: {q}")
    
    def test_ambiguity_analyzer_top_clientes_albaranes(self):
        from datia.services.ai.ambiguity_analyzer import AmbiguityAnalyzer
        analyzer = AmbiguityAnalyzer()
        res = analyzer.analyze("top clientes albaranes", {'empresa': 1})
        self.assertFalse(res.get('ambiguous'), f"Ambiguity should be False. Payload: {res}")

    def test_prefer_human_label_cliente(self):
        from datia.services.query_builder import QueryBuilder
        col_map = {'codigocliente': 'codigocliente', 'razonsocial': 'razonsocial'}
        chosen = QueryBuilder._prefer_human_label('cliente', col_map, 'codigocliente')
        self.assertEqual(chosen, 'razonsocial')

    def test_prefer_human_label_proveedor(self):
        from datia.services.query_builder import QueryBuilder
        col_map = {'codigoproveedor': 'codigoproveedor', 'razonsocial': 'razonsocial'}
        chosen = QueryBuilder._prefer_human_label('proveedor', col_map, 'codigoproveedor')
        self.assertEqual(chosen, 'razonsocial')

    def test_master_join_articulo_label(self):
        from datia.services.query_builder import QueryBuilder
        self.assertTrue(QueryBuilder._is_code_like('codigoarticulo'))
        j, expr, gb = QueryBuilder._master_label_join('articulo', 'L', 'codigoarticulo', 'codigoempresa')
        self.assertIn('datia_articulos', j)
        self.assertIn('COALESCE', expr)
        self.assertIn('M."descripcion"', expr)
        self.assertIn('GROUP', f"GROUP BY {gb}")

class TestBaselineSelector(unittest.TestCase):
    @patch('datia.services.etl_service.ETLService.get_available_exercises')
    @patch('datia.services.etl_service.ETLService.sync_mssql_sales_incremental_generator')
    @patch('datia.services.etl_service.ETLService.sync_mssql_sales_generator')
    @patch('datia.services.etl_service.ETLService.has_baseline')
    def test_full_on_first_sales(self, m_base, m_full, m_inc, m_years):
        m_base.return_value = False
        m_years.return_value = [2025]
        m_full.side_effect = lambda empresa, year, fast_bulk=False: iter(["FULL_VENTAS"])
        m_inc.side_effect = lambda empresa, year, days_back=7: iter(["INC_VENTAS"])
        from datia.services.etl_service import ETLService
        svc = ETLService()
        out = []
        for x in svc.sync_all_years_for_empresa_generator(1, sync_type='standard', standard_tables=['ventas'], years_count=1, target_year=2025, fast_bulk=True):
            out.append(x)
        self.assertTrue(any(s == "FULL_VENTAS" for s in out))
        self.assertFalse(any(s == "INC_VENTAS" for s in out))

    @patch('datia.services.etl_service.ETLService.get_available_exercises')
    @patch('datia.services.etl_service.ETLService.sync_mssql_sales_incremental_generator')
    @patch('datia.services.etl_service.ETLService.sync_mssql_sales_generator')
    @patch('datia.services.etl_service.ETLService.has_baseline')
    def test_incremental_after_baseline_sales(self, m_base, m_full, m_inc, m_years):
        m_base.return_value = True
        m_years.return_value = [2025]
        m_full.side_effect = lambda empresa, year, fast_bulk=False: iter(["FULL_VENTAS"])
        m_inc.side_effect = lambda empresa, year, days_back=7: iter(["INC_VENTAS"])
        from datia.services.etl_service import ETLService
        svc = ETLService()
        out = []
        for x in svc.sync_all_years_for_empresa_generator(1, sync_type='standard', standard_tables=['ventas'], years_count=1, target_year=2025, fast_bulk=True):
            out.append(x)
        self.assertTrue(any(s == "INC_VENTAS" for s in out))
        self.assertFalse(any(s == "FULL_VENTAS" for s in out))

class TestEndpointsIncremental(unittest.TestCase):
    @patch('datia.services.etl_service.ETLService.has_baseline')
    def test_incremental_sales_requires_baseline(self, m_base):
        m_base.return_value = False
        from datia.api.etl_endpoints import incremental_sales
        res = incremental_sales(None, empresa_id='1', year=2025, days=7)
        self.assertIsInstance(res, tuple)
        self.assertEqual(res[1], 400)

class TestVentasUninvoicedCard(unittest.TestCase):
    def test_card_exists_in_sub_ventas_section(self):
        import os
        p = os.path.join(os.path.dirname(__file__), 'templates', 'datia', 'components', 'tab_actualidad.html')
        with open(p, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('id="sub-ventas"', content)
        ventas_start = content.find('id="sub-ventas"')
        compras_pos = content.find('id="sub-compras"')
        if compras_pos == -1:
            compras_pos = len(content)
        sub_ventas_block = content[ventas_start:compras_pos]
        self.assertIn('id="sales-uninvoiced-card"', sub_ventas_block)
        self.assertIn('id="sales-uninv-albaranes"', sub_ventas_block)
        self.assertIn('id="sales-uninv-lineas"', sub_ventas_block)
        self.assertIn('id="sales-uninv-importe"', sub_ventas_block)

    def test_js_calls_uninvoiced_endpoint(self):
        import os
        p = os.path.join(os.path.dirname(__file__), 'static', 'js', 'dashboard', 'actualidad.js')
        with open(p, 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('loadUninvoicedLinesSalesCard', js)
        self.assertRegex(js, r'/api/financial/uninvoiced-lines\\?')


class TestAICatalogMinimo(unittest.TestCase):
    def test_match_intent_top_clientes(self):
        from datia.services.ai.nlq_catalog import match_intent
        res = match_intent("mejores clientes del año")
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("intent_id"), "ventas.top_clientes")
    
    def test_match_intent_tesoreria_resumen(self):
        from datia.services.ai.nlq_catalog import match_intent
        res = match_intent("informe de tesorería 2025")
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("intent_id"), "tesoreria.resumen")
    
    def test_match_intent_tesoreria_caja_mensual(self):
        from datia.services.ai.nlq_catalog import match_intent
        res = match_intent("saldos mensuales de caja 2025")
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("intent_id"), "tesoreria.caja_mensual")
    
    def test_resumen_ejercicio_sin_ventas_no_debe_ser_ventas(self):
        from datia.services.ai.nlq_catalog import match_intent
        res = match_intent("resumen ejercicio 2025")
        self.assertTrue(res is None or res.get("intent_id") != "ventas.resumen_ejercicio")

    def test_match_intent_financiera_ratios(self):
        from datia.services.ai.nlq_catalog import match_intent
        res = match_intent("ratios 2025")
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("intent_id"), "financiera.ratios")
    
    def test_match_intent_presupuesto(self):
        from datia.services.ai.nlq_catalog import match_intent
        res = match_intent("presupuesto 2025")
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("intent_id"), "presupuestos.comparativa")

    def test_parse_years_from_query(self):
        from datia.services.ai.handlers.catalog_report_handler import CatalogReportHandler
        years = CatalogReportHandler._parse_years_from_query("ratios 2024 vs 2025")
        self.assertEqual(years, [2024, 2025])

class TestSQLGuardMetrics(unittest.TestCase):
    def test_allow_metrics_select(self):
        from datia.services.security.sql_guard import SQLGuard
        allowed_sqls = [
            'SELECT * FROM "metrics_totales_empresa_ejercicio" WHERE "empresa"=1 AND "ejercicio"=2025',
            'SELECT * FROM public."metrics_totales_empresa_ejercicio_cliente" WHERE "empresa"=1',
            'SELECT * FROM public."datiadb_cabecerapedidocliente" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM public."datia_financial_acumulados" WHERE "empresa"=1 AND "ejercicio"=2025',
            'SELECT * FROM public."datia_financial_cartera" WHERE "empresa"=1 AND "ejercicio"=2025',
            'SELECT * FROM public."datia_banking_instrument" WHERE "empresa"=1',
            'SELECT * FROM public."datia_acumulados_stocks" WHERE "empresa"=1 AND "ejercicio"=2025',
            'SELECT * FROM public."datia_almacenes" WHERE "empresa"=1',
            'SELECT * FROM public."datia_articulos" WHERE "empresa"=1',
            'SELECT * FROM public."datia_cliente" WHERE "empresa"=1',
            'SELECT * FROM public."datia_comisionistas" WHERE "empresa"=1',
            'SELECT * FROM public."datia_empresa" WHERE "id"=1',
            'SELECT * FROM public."datia_familias" WHERE "empresa"=1',
        ]
        for sql in allowed_sqls:
            res = SQLGuard.check_sql(sql)
            self.assertTrue(res["allowed"], f"Should allow: {sql}")

    def test_block_write_operations(self):
        from datia.services.security.sql_guard import SQLGuard
        blocked_sqls = [
            'DELETE FROM "metrics_totales_empresa_ejercicio" WHERE 1=1',
            'UPDATE "datiadb_cabecerapedidocliente" SET "CodigoEmpresa"=2 WHERE 1=1',
            'TRUNCATE TABLE "metrics_totales_empresa_ejercicio"',
        ]
        for sql in blocked_sqls:
            res = SQLGuard.check_sql(sql)
            self.assertFalse(res["allowed"], f"Should block: {sql}")

    def test_ten_thousand_queries_sql_guard(self):
        from datia.services.security.sql_guard import SQLGuard
        for i in range(1, 10001):
            if i % 3 == 0:
                q = f'SELECT * FROM public."metrics_totales_empresa_ejercicio" WHERE "empresa"=1 AND "ejercicio"=2025 LIMIT {i % 100}'
                res = SQLGuard.check_sql(q)
                self.assertTrue(res["allowed"], f"Should allow metrics: {q}")
            elif i % 3 == 1:
                q = f'SELECT * FROM public."datiadb_cabecerapedidocliente" c JOIN "datiadb_lineaspedidocliente" l ON 1=1 WHERE c."CodigoEmpresa"=1 LIMIT {i % 100}'
                res = SQLGuard.check_sql(q)
                self.assertTrue(res["allowed"], f"Should allow datiadb pedidos: {q}")
            else:
                q = f'SELECT * FROM "any_other_table_{i}" LIMIT 1'
                res = SQLGuard.check_sql(q)
                self.assertFalse(res["allowed"], f"Should block: {q}")


class TestReportHandlerPGC(unittest.TestCase):
    def _fake_snapshot(self):
        return {
            'ingresos': 8678914.2,
            'otros_ingresos': 3106.19,
            'gastos': 6367537.2,
            'otros_gastos': 2910519.25,
            'resultado': -596036.06,
            'variacion': 0.0,
            'ratios': {'margen': -6.87},
            'py': {
                'ingresos': 7448455.09,
                'otros_ingresos': 2090.11,
                'gastos': 4513573.15,
                'otros_gastos': 3048305.52,
                'resultado': -239684.58,
                'variacion': -128351.11,
                'ejercicio': 2024
            },
            'var': {
                'ingresos': {'abs': 1230459.11, 'pct': 16.52},
                'otros_ingresos': {'abs': 1016.08, 'pct': 48.61},
                'gastos': {'abs': 1853964.05, 'pct': 41.08},
                'otros_gastos': {'abs': -137786.27, 'pct': -4.52},
                'resultado': {'abs': -356351.48, 'pct': 148.68},
                'variacion': {'abs': 128351.11, 'pct': -100.0},
            }
        }

    @patch('datia.services.financial_service.FinancialService.get_quarterly_report')
    @patch('datia.services.financial_service.FinancialService.get_monthly_kpis')
    @patch('datia.services.financial_service.FinancialService.get_snapshot')
    def test_report_handler_uses_pgc_snapshot(self, m_snap, m_monthly, m_quarterly):
        from django.utils import translation
        from datia.services.ai.handlers.report_handler import ReportHandler

        m_snap.return_value = self._fake_snapshot()
        m_monthly.return_value = {'labels': ['Ene'], 'ingresos': [1.0], 'gastos': [2.0], 'ebitda': [3.0], 'margen_pct': [4.0]}
        m_quarterly.return_value = {
            'quarters': {'Q1': {'ingresos': 10}, 'Q2': {'ingresos': 20}, 'Q3': {'ingresos': 30}, 'Q4': {'ingresos': 40}},
            'comparison': {'prev_values': {'quarters': {'Q1': {'ingresos': 9}, 'Q2': {'ingresos': 19}, 'Q3': {'ingresos': 29}, 'Q4': {'ingresos': 39}}}},
        }

        h = ReportHandler(None)
        h._get_metrics_rankings = lambda *a, **k: {'clients': [{'name': 'A', 'value': 1}]}
        h._get_metrics_top_products = lambda *a, **k: [{'name': 'P', 'value': 2}]
        h._get_metrics_purchases_advanced = lambda *a, **k: {'total': 100, 'variation': 5.0}
        h._execute_sql = lambda q: [{'ejercicio': 2025, 'importe_neto_total': 1000, 'albaranes_count': 10}]

        with translation.override('es'):
            res = h.handle({}, {'empresa': 1, 'ejercicio': 2025})

        self.assertEqual(res.get('type'), 'report')
        kpis = res.get('kpis') or []
        self.assertTrue(any(k.get('label') == 'Ingresos Totales' and k.get('value') == 8678914.2 for k in kpis))
        self.assertTrue(res.get('chart_config') and res['chart_config'].get('echarts_option'))
        self.assertIn('<h2>', res.get('answer') or '')

    @patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicioCliente')
    def test_catalog_handler_incluye_text_y_answer(self, m_cli):
        class _FakeQS:
            def order_by(self, *_):
                return []
        m_cli.objects.filter.return_value = _FakeQS()
        from datia.services.ai.handlers.catalog_report_handler import CatalogReportHandler
        h = CatalogReportHandler(None)
        payload = h.handle({'intent_id': 'ventas.top_clientes'}, {'empresa': 1, 'ejercicio': 2025})
        self.assertIsInstance(payload, dict)
        self.assertIn('answer', payload)
        self.assertIn('text', payload)
        self.assertEqual(payload.get('answer'), payload.get('text'))
        self.assertEqual(payload.get('type'), 'report')


class TestAICatalogBateriaExtensa(unittest.TestCase):
    def _fake_obj(self, **kw):
        o = type('O', (), {})()
        for k, v in kw.items():
            setattr(o, k, v)
        return o

    class _FakeQS:
        def __init__(self, items=None, first=None):
            self._items = list(items or [])
            self._first = first

        def filter(self, **_):
            return self

        def order_by(self, *_):
            return self

        def first(self):
            return self._first

        def __iter__(self):
            return iter(self._items)

        def __getitem__(self, sl):
            return self._items[sl]

    def _fake_month_filter(self, year: int):
        def _filter(**kwargs):
            a = int(kwargs.get('mes__gte') or 1)
            b = int(kwargs.get('mes__lte') or 12)
            ejercicio = int(kwargs.get('ejercicio') or year)
            base = 1000.0 if ejercicio == year else 800.0
            rows = []
            for m in range(a, b + 1):
                rows.append(self._fake_obj(mes=m, importe_neto_total=base + m * 10.0, importe_coste_total=base * 0.6))
            return rows
        return _filter

    def _fake_top_qs(self, field_name: str, base: float):
        items = []
        for i in range(1, 51):
            name = f"{field_name.upper()}_{i}"
            kw = {field_name: name, 'nombre': name, 'descripcion': name, 'importe_neto_total': base - i * 10.0}
            items.append(self._fake_obj(**kw))
        return self._FakeQS(items=items)

    def _fake_totals_filter(self, year: int):
        def _filter(**kwargs):
            ejercicio = int(kwargs.get('ejercicio') or year)
            val = 120000.0 if ejercicio == year else 100000.0
            return self._FakeQS(first=self._fake_obj(importe_neto_total=val))
        return _filter

    def _fake_monthly_kpis(self, empresa: int, ejercicio: int):
        labels = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        base = 20000.0 if int(ejercicio) % 2 == 1 else 18000.0
        ingresos = [base + i * 500.0 for i in range(12)]
        return {'labels': labels, 'ingresos': ingresos}

    def _fake_per100(self, empresa: int, ejercicio: int, eq_mode: bool = True):
        cy = {'parts': [{'key': 'costo_ventas', 'pct': 40.0}, {'key': 'otros_gastos_exp', 'pct': 35.0}, {'key': 'utilidad_neta', 'pct': 25.0}]}
        py = {'parts': [{'key': 'costo_ventas', 'pct': 42.0}, {'key': 'otros_gastos_exp', 'pct': 33.0}, {'key': 'utilidad_neta', 'pct': 25.0}]}
        return {'cy': cy, 'py': py}

    def test_10000_consultas_variantes_catalogo(self):
        from datia.services.ai_service import IAService
        from datia.services.ai.handlers.catalog_report_handler import CatalogReportHandler

        class _FakeModel:
            def __init__(self, filter_fn):
                self.objects = type('M', (), {'filter': staticmethod(filter_fn)})()

        year = 2025
        prev = 2024

        fake_mes = _FakeModel(self._fake_month_filter(year))
        fake_compra_mes = _FakeModel(self._fake_month_filter(year))

        fake_cli = type('MC', (), {'objects': type('O', (), {'filter': lambda *_a, **_k: self._fake_top_qs('cliente', 50000.0)})()})()
        fake_art = type('MA', (), {'objects': type('O', (), {'filter': lambda *_a, **_k: self._fake_top_qs('articulo', 60000.0)})()})()
        fake_prov = type('MP', (), {'objects': type('O', (), {'filter': lambda *_a, **_k: self._fake_top_qs('proveedor', 70000.0)})()})()

        fake_tot = _FakeModel(self._fake_totals_filter(year))
        fake_compra_tot = _FakeModel(self._fake_totals_filter(year))

        months = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']

        queries = []
        for n in [1, 3, 5, 10, 20]:
            queries.append(f"top {n} clientes del año")
            queries.append(f"mejores {n} clientes 2025")
            queries.append(f"ranking {n} clientes ejercicio 2025")
            queries.append(f"top {n} productos 2025")
            queries.append(f"mejores {n} artículos del año")
            queries.append(f"top {n} proveedores del año")
            queries.append(f"mejores {n} proveedores 2025")
        for a in range(1, 13):
            for b in range(a, min(12, a + 4) + 1):
                queries.append(f"ventas entre el periodo {a} y {b}")
                queries.append(f"ventas de {months[a-1]} a {months[b-1]} comparativas con el mismo periodo del año anterior")
        bases = [
            "resumen del ejercicio",
            "resumen de ventas del ejercicio",
            "resumen financiero",
            "coste por cada 100",
            "per100",
            "compras por mes",
            "evolución compras",
            "resumen compras 2025",
            "ventas por mes",
            "margen mensual",
        ]
        while len(queries) < 10020:
            for b in bases:
                queries.append(b)
                if len(queries) >= 10020:
                    break

        self.assertGreaterEqual(len(queries), 10000)

        with patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicio', fake_tot), \
             patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicioCompra', fake_compra_tot), \
             patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicioCliente', fake_cli), \
             patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicioArticulo', fake_art), \
             patch.object(CatalogReportHandler.Models, 'MetricsTotalesEmpresaEjercicioMes', fake_mes), \
             patch.object(CatalogReportHandler.Models, 'MetricsTotalesEmpresaEjercicioCompraMes', fake_compra_mes), \
             patch.object(CatalogReportHandler.Models, 'MetricsTotalesEmpresaEjercicioProveedor', fake_prov), \
             patch('datia.services.ai.handlers.catalog_report_handler.FinancialService.get_monthly_kpis', side_effect=self._fake_monthly_kpis), \
             patch('datia.services.ai.handlers.catalog_report_handler.FinancialService.get_per100', side_effect=self._fake_per100):
            svc = IAService()
            for q in queries:
                resp = svc.generate_answer(q, empresa=1, ejercicio=year, request=None)
                self.assertIsInstance(resp, dict)
                self.assertIn('type', resp)
                self.assertIn('answer', resp)
                self.assertIn('text', resp)
                self.assertEqual(resp.get('answer'), resp.get('text'))
                self.assertEqual(resp.get('type'), 'report')

                key = resp.get('key') or ''
                chart = resp.get('chart_config')
                self.assertIsInstance(chart, dict)
                self.assertIn('data', chart)
                data = chart.get('data') or {}
                self.assertIn('labels', data)
                self.assertIn('datasets', data)
                if key in ('ventas_top_clientes', 'ventas_top_productos', 'compras_top_proveedores'):
                    tbl = resp.get('table') or {}
                    self.assertIsInstance(tbl, dict)
                    self.assertIsInstance(tbl.get('rows'), list)
                    rows = tbl.get('rows') or []
                    self.assertGreaterEqual(len(rows), 1)
                    self.assertIsInstance(rows[0][0], str)
                    self.assertNotEqual(rows[0][0].strip(), '')
                    kpis = resp.get('kpis') or []
                    if kpis:
                        self.assertRegex(str(kpis[0].get('label') or ''), r'Top 1:')
                    self.assertEqual(data.get('labels'), [str(prev), str(year)])
                    ds = (data.get('datasets') or [])[0]
                    self.assertEqual(len(ds.get('data') or []), 2)
                else:
                    self.assertGreaterEqual(len(data.get('datasets') or []), 2)

    def test_rango_periodos_resuelve_mes(self):
        from datia.services.ai.handlers.catalog_sections import build_ventas_rango_periodos
        from datia.services.ai.handlers.catalog_report_handler import CatalogReportHandler

        class _FakeModel:
            def __init__(self, rows_fn):
                self.objects = type('O', (), {'filter': staticmethod(rows_fn)})()

        handler = CatalogReportHandler(None)

        def rows_fn(**kwargs):
            a = int(kwargs.get('mes__gte') or 1)
            b = int(kwargs.get('mes__lte') or 12)
            rows = []
            for m in range(a, b + 1):
                rows.append(self._fake_obj(mes=m, importe_neto_total=1000 + m * 10))
            return rows

        handler.Models.MetricsTotalesEmpresaEjercicioMes = _FakeModel(rows_fn)
        payload = build_ventas_rango_periodos(handler, "ventas de enero a marzo", 1, 2025, 2024)
        chart = payload.get('chart_config') or {}
        labels = (chart.get('data') or {}).get('labels') or []
        self.assertEqual(labels, ['Ene', 'Feb', 'Mar'])

    def test_topn_devuelve_n_filas_y_nombres(self):
        from datia.services.ai.handlers.catalog_report_handler import CatalogReportHandler

        class _Row:
            def __init__(self, **kw):
                for k, v in kw.items():
                    setattr(self, k, v)

        class _QS:
            def __init__(self, items):
                self._items = items

            def order_by(self, *_):
                return self

            def __getitem__(self, sl):
                return self._items[sl]

        items = [_Row(cliente=f"C{i}", nombre=f"Cliente {i}", importe_neto_total=10000 - i, importe_coste_total=6000 - i, albaranes_count=10 + i) for i in range(1, 31)]
        fake_cli = type('MC', (), {'objects': type('O', (), {'filter': lambda *_a, **_k: _QS(items)})()})()

        with patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicioCliente', fake_cli), \
             patch('datia.services.ai.handlers.catalog_report_handler.MetricsTotalesEmpresaEjercicio', type('MT', (), {'objects': type('O', (), {'filter': lambda *_a, **_k: type('Q', (), {'first': lambda *_: _Row(importe_neto_total=1)})()})()})()):
            h = CatalogReportHandler(None)
            payload = h.handle({'intent_id': 'ventas.top_clientes', 'query': 'top 10 clientes 2025'}, {'empresa': 1, 'ejercicio': 2025, 'limit': 10})
            tbl = payload.get('table') or {}
            rows = tbl.get('rows') or []
            self.assertEqual(len(rows), 10)
            self.assertEqual(rows[0][0], 'Cliente 1')
            self.assertGreaterEqual(len(rows[0]), 10)


class TestTotalsServiceRellenaNombres(unittest.TestCase):
    def test_sql_no_inserta_nombre_null_en_clientes_y_proveedores(self):
        from datia.services.totals_service import TotalsService

        class _FakeCursor:
            def __init__(self):
                self.sqls = []
                self._cols = []

            def execute(self, sql, params=None):
                s = str(sql)
                self.sqls.append(s)
                if "SELECT table_name FROM information_schema.tables" in s:
                    self._cols = [('datiadb_cabeceraalbarancliente',)]
                elif "SELECT column_name FROM information_schema.columns" in s:
                    self._cols = [
                        ('codigoempresa',), ('ejercicioalbaran',), ('fechaalbaran',), ('codigocliente',),
                        ('numeroalbaran',), ('importeliquido',), ('importetotal',),
                        ('codigoproveedor',)
                    ]
                else:
                    self._cols = []

            def fetchall(self):
                return list(self._cols)

        class _FakeConn:
            def __init__(self):
                self._cursor = _FakeCursor()

            def cursor(self):
                return self._cursor

        fake_conn = _FakeConn()

        class _FakeConnections:
            def __getitem__(self, _alias):
                return fake_conn

        import datetime
        now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

        with patch('django.db.connections', _FakeConnections()), \
             patch('django.utils.timezone.now', return_value=now):
            svc = TotalsService()
            svc.aggregate_from_datiadb_sales(empresa=1, ejercicio=2025)
            svc.aggregate_from_datiadb_purchases(empresa=1, ejercicio=2025)

        joined = "\n".join(fake_conn._cursor.sqls).lower()
        self.assertNotIn(", null,", joined)
        self.assertIn("left join datia_cliente", joined)
        self.assertIn("left join datia_proveedores", joined)
        self.assertIn("coalesce(max(dc.nombre)", joined)
        self.assertIn("coalesce(max(dp.nombre)", joined)


class TestTotalsServiceCosteDesdeLineas(unittest.TestCase):
    def test_sql_usa_lineas_coste_y_precio_compra(self):
        from datia.services.totals_service import TotalsService

        class _FakeCursor:
            def __init__(self):
                self.sqls = []
                self._rows = []

            def execute(self, sql, params=None):
                s = str(sql)
                self.sqls.append(s)
                if "SELECT table_name FROM information_schema.tables" in s:
                    self._rows = [('datiadb_lineasalbarancliente',)]
                elif "SELECT column_name FROM information_schema.columns" in s and params and params[0] == 'datiadb_lineasalbarancliente':
                    self._rows = [
                        ('codigoempresa',), ('ejercicioalbaran',), ('fechaalbaran',),
                        ('codigocliente',), ('codigoarticulo',), ('numeroalbaran',),
                        ('importeneto',), ('importetotal',),
                        ('preciocoste',), ('importecoste',), ('unidades',),
                    ]
                else:
                    self._rows = []

            def fetchall(self):
                return list(self._rows)

        class _FakeConn:
            def __init__(self):
                self._cursor = _FakeCursor()

            def cursor(self):
                return self._cursor

        fake_conn = _FakeConn()

        class _FakeConnections:
            def __getitem__(self, _alias):
                return fake_conn

        import datetime
        now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

        with patch('django.db.connections', _FakeConnections()), \
             patch('django.utils.timezone.now', return_value=now):
            svc = TotalsService()
            svc.aggregate_from_datiadb_sales(empresa=1, ejercicio=2025)

        joined = "\n".join(fake_conn._cursor.sqls).lower()
        self.assertIn("from datiadb_lineasalbarancliente", joined)
        self.assertIn("left join datia_articulos da", joined)
        self.assertIn("da.precio_compra", joined)
        self.assertIn("importecoste", joined)
        self.assertIn("preciocoste", joined)

class TestTotalsServiceJoinSerieAlbaran(unittest.TestCase):
    def test_join_hdr_incluye_serie_para_evitar_duplicados(self):
        from datia.services.totals_service import TotalsService

        class _FakeCursor:
            def __init__(self):
                self.sqls = []
                self._rows = []

            def execute(self, sql, params=None):
                s = str(sql)
                self.sqls.append(s)
                if "SELECT table_name FROM information_schema.tables" in s:
                    self._rows = [('datiadb_lineasalbarancliente',), ('datiadb_cabeceraalbarancliente',)]
                elif "SELECT column_name FROM information_schema.columns" in s and params and params[0] == 'datiadb_lineasalbarancliente':
                    self._rows = [
                        ('codigoempresa',), ('ejercicioalbaran',), ('seriealbaran',), ('numeroalbaran',),
                        ('fechaalbaran',), ('codigoarticulo',), ('importeneto',),
                    ]
                elif "SELECT column_name FROM information_schema.columns" in s and params and params[0] == 'datiadb_cabeceraalbarancliente':
                    self._rows = [
                        ('codigoempresa',), ('ejercicioalbaran',), ('seriealbaran',), ('numeroalbaran',),
                        ('codigocliente',),
                    ]
                else:
                    self._rows = []

            def fetchall(self):
                return list(self._rows)

        class _FakeConn:
            def __init__(self):
                self._cursor = _FakeCursor()

            def cursor(self):
                return self._cursor

        fake_conn = _FakeConn()

        class _FakeConnections:
            def __getitem__(self, _alias):
                return fake_conn

        import datetime
        now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

        with patch('django.db.connections', _FakeConnections()), \
             patch('django.utils.timezone.now', return_value=now):
            TotalsService().aggregate_from_datiadb_sales(empresa=1, ejercicio=2025)

        joined = "\n".join(fake_conn._cursor.sqls).lower()
        self.assertIn("and l.seriealbaran = h.seriealbaran", joined)
        self.assertIn("count(distinct (h.seriealbaran, h.numeroalbaran))", joined)

class TestPDFServiceLandscape(unittest.TestCase):
    def test_pdf_landscape_cuando_tabla_muy_ancha(self):
        from datia.services.pdf_service import PDFService
        raw = {
            "payload": {
                "table": {
                    "columns": ["A"] + [f"C{i}" for i in range(1, 15)],
                    "rows": [["x"] + list(range(1, 15))]
                }
            }
        }
        self.assertTrue(PDFService._should_landscape(raw))


class TestQAEndpointPassthrough(unittest.TestCase):
    def test_passthrough_campos_report_top(self):
        from datia.api.endpoints import qa_query

        class _FakeSvc:
            def generate_answer(self, *a, **k):
                return {
                    'text': 'ok',
                    'sql': None,
                    'type': 'report',
                    'chart_config': {'type': 'bar', 'data': {'labels': ['2024','2025'], 'datasets': [{'data': [1,2]}]}},
                    'chart_pareto_clients': {'type': 'bar', 'data': {'labels': ['A','B'], 'datasets': [{'data': [10,9]}]}},
                    'chart_concentration_clients': {'type': 'doughnut', 'data': {'labels': ['A','Resto'], 'datasets': [{'data': [10,90]}]}},
                    'table': {'title': 'Detalle', 'columns': ['Cliente','Ventas (€)'], 'rows': [['ACME', 10.0], ['B', 9.0]]},
                    'kpis': [{'label': 'Top 1: ACME', 'value': 10.0}],
                    'key': 'ventas_top_clientes',
                    'source': 'catalog'
                }

        class _FakeResp:
            def set_cookie(self, *a, **k):
                return None

        with patch('datia.factories.ServiceFactory.get_ai_service', return_value=_FakeSvc()):
            out = qa_query(request=None, response=_FakeResp(), question='top 10 clientes', empresa=1, ejercicio=2025, training_enabled=False, model=None)
            self.assertEqual(out.get('type'), 'report')
            self.assertIsNotNone(out.get('chart_pareto_clients'))
            self.assertIsNotNone(out.get('chart_concentration_clients'))
            self.assertIsNotNone(out.get('table'))


class TestFeedbackEndpointAlwaysJSON(unittest.TestCase):
    def test_feedback_guardado_tabla_inexistente_devuelve_json_error(self):
        from datia.api.endpoints import submit_feedback, FeedbackInput

        class _FakeQS:
            def first(self):
                raise Exception('psycopg2.errors.UndefinedTable: no existe la relación «metrics_saved_queries»')

        class _FakeMgr:
            def filter(self, **_):
                return _FakeQS()

        with patch('datia.models.MetricsSavedQuery.objects', _FakeMgr()):
            payload = FeedbackInput(query='top 10 clientes', vote=1, key='ventas.top_clientes', empresa=1, ejercicio=2025)
            out = submit_feedback(None, payload)
            self.assertIsInstance(out, dict)
            self.assertEqual(out.get('status'), 'error')
            self.assertIn('metrics_saved_queries', out.get('message', ''))


class TestGeminiService(unittest.TestCase):
    def test_generate_text_with_policy_fallback_sin_api_key(self):
        import os
        from datia.services.gemini_service import GeminiService

        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            svc = GeminiService()
            res = svc.generate_text_with_policy(prompt="hola", kind="financiera")
            self.assertEqual(res.get("status"), "fallback")
            self.assertEqual(res.get("reason"), "missing_api_key")

    def test_generate_text_with_policy_ok_con_mock(self):
        import os
        from datia.services.gemini_service import GeminiService

        class _Resp:
            status_code = 200
            content = b"{}"

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "x", "GEMINI_MODEL_TEXT": "gemini-1.5-pro"}, clear=False):
            svc = GeminiService()
            with patch("datia.services.gemini_service.requests.post", return_value=_Resp()):
                res = svc.generate_text_with_policy(prompt="hola", kind="ventas", deadline=10)
                self.assertEqual(res.get("status"), "ok")
                self.assertEqual(res.get("text"), "OK")
    
    def test_generate_text_with_policy_usa_model_report_por_kind(self):
        import os
        from datia.services.gemini_service import GeminiService

        class _Resp:
            status_code = 200
            content = b"{}"

            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

        with patch.dict(os.environ, {"GEMINI_API_KEY": "x", "GEMINI_MODEL_TEXT": "gemini-2.5-flash", "GEMINI_MODEL_REPORT": "gemini-2.5-pro"}, clear=False):
            svc = GeminiService()
            with patch("datia.services.gemini_service.requests.post", return_value=_Resp()):
                res = svc.generate_text_with_policy(prompt="hola", kind="financiera", deadline=10)
                self.assertEqual(res.get("status"), "ok")
                self.assertEqual(res.get("model"), "gemini-2.5-pro")


class TestFactoryGemini(unittest.TestCase):
    def test_factory_devuelve_gemini_para_reportes(self):
        import os
        from datia.factories import ServiceFactory

        with patch.dict(os.environ, {"DATIA_REPORT_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "x"}, clear=False):
            svc = ServiceFactory.get_report_llm_service(kind="financiera")
            self.assertEqual(svc.__class__.__name__, "GeminiService")


class TestTesoreriaIntentRouting(unittest.TestCase):
    def test_match_intent_tesoreria_resumen_simple(self):
        from datia.services.ai.nlq_catalog import match_intent

        q = "tesoreria 2025"
        res = match_intent(q)
        self.assertIsNotNone(res)
        self.assertEqual(res.get("intent_id"), "tesoreria.resumen")
