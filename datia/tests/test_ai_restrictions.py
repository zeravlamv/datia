import unittest
from datia.services.security.sql_guard import SQLGuard
from datia.services.builders.evolution import EvolutionBuilder

class TestSQLGuardRestrictions(unittest.TestCase):
    def test_allowed_tables_orders_and_deliveries(self):
        allowed_sqls = [
            'SELECT 1 FROM "datiadb_cabecerapedidocliente" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM "datiadb_lineaspedidocliente" JOIN "datiadb_cabecerapedidocliente" ON 1=1',
            'SELECT * FROM "datiadb_cabeceraalbarancliente" WHERE EXTRACT(YEAR FROM "FechaAlbaran")=2025',
            'SELECT * FROM "datiadb_lineasalbarancliente" JOIN "datiadb_cabeceraalbarancliente" ON 1=1',
            'SELECT * FROM "datiadb_cabeceraalbaranproveedor" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM "datiadb_lineasalbaranproveedor" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM "datiadb_order_headers" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM "datiadb_order_lines" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM "datiadb_delivery_notes" WHERE "CodigoEmpresa"=1',
            'SELECT * FROM "datiadb_delivery_lines" WHERE "CodigoEmpresa"=1',
        ]
        for sql in allowed_sqls:
            res = SQLGuard.check_sql(sql)
            self.assertTrue(res['allowed'], f"Should allow: {sql}")

    def test_allowed_tables_metrics(self):
        allowed_sqls = [
            'SELECT * FROM "metrics_totales_empresa_ejercicio" WHERE "empresa"=1 AND "ejercicio"=2025',
            'SELECT * FROM public."metrics_totales_empresa_ejercicio_cliente" WHERE "empresa"=1',
        ]
        for sql in allowed_sqls:
            res = SQLGuard.check_sql(sql)
            self.assertTrue(res['allowed'], f"Should allow: {sql}")

    def test_block_other_schemas_and_tables(self):
        blocked_sqls = [
            'SELECT * FROM information_schema.tables',
            'SELECT * FROM pg_catalog.pg_class',
            'SELECT * FROM "datia_raw_cabecera"',
            'SELECT * FROM "datia_raw_lineas"',
            'SELECT * FROM "any_other_table"',
            'SELECT * FROM "datiadb_financial_acumulados"',
        ]
        for sql in blocked_sqls:
            res = SQLGuard.check_sql(sql)
            self.assertFalse(res['allowed'], f"Should block: {sql}")
            self.assertGreater(len(res['blocked']), 0)

    def test_block_write_operations_even_on_allowed_tables(self):
        blocked_sqls = [
            'DELETE FROM "metrics_totales_empresa_ejercicio" WHERE 1=1',
            'UPDATE "datiadb_cabecerapedidocliente" SET "CodigoEmpresa"=2 WHERE 1=1',
            'TRUNCATE TABLE "metrics_totales_empresa_ejercicio"',
        ]
        for sql in blocked_sqls:
            res = SQLGuard.check_sql(sql)
            self.assertFalse(res['allowed'], f"Should block: {sql}")

    def test_extract_tables_robust(self):
        sql = 'SELECT x FROM public."datiadb_cabecerapedidocliente" c JOIN "datiadb_lineaspedidocliente" l ON c.id=l.cid'
        res = SQLGuard.check_sql(sql)
        self.assertTrue(res['allowed'])
    def test_extract_function_ignored(self):
        sql = 'SELECT EXTRACT(MONTH FROM "FechaPedido") FROM "datiadb_cabecerapedidocliente"'
        res = SQLGuard.check_sql(sql)
        self.assertTrue(res['allowed'])

class TestAmbiguityResolution(unittest.TestCase):
    def test_ambiguous_pedidos_resolves_to_orders(self):
        r = EvolutionBuilder.build("pedidos", empresa=1, ejercicio=2025, is_purchase=False)
        self.assertIn('"datiadb_cabecerapedidocliente"', r.get('sql',''))

    def test_ambiguous_albaranes_resolves_to_deliveries(self):
        r = EvolutionBuilder.build("albaranes 2025", empresa=1, ejercicio=2025, is_purchase=False)
        self.assertIn('"datiadb_cabeceraalbarancliente"', r.get('sql',''))
    
    def test_top_clientes_albaranes_not_ambiguous(self):
        from datia.services.ai.ambiguity_analyzer import AmbiguityAnalyzer
        analyzer = AmbiguityAnalyzer()
        ctx = {'empresa': 1}  # intentionally no 'ejercicio'
        res = analyzer.analyze("top clientes albaranes", ctx)
        self.assertFalse(res.get('ambiguous'), f"Ambiguity should be False. Payload: {res}")

class TestFiftyQueries(unittest.TestCase):
    def test_fifty_queries(self):
        queries = []
        # 25 ped: diversas variantes
        for i in range(1, 26):
            queries.append(f'SELECT * FROM "datiadb_cabecerapedidocliente" WHERE "CodigoEmpresa"=1 AND EXTRACT(YEAR FROM "FechaPedido")=2025 LIMIT {i}')
        # 25 alb: diversas variantes
        for i in range(1, 26):
            queries.append(f'SELECT * FROM "datiadb_cabeceraalbarancliente" WHERE "CodigoEmpresa"=1 AND EXTRACT(YEAR FROM "FechaAlbaran")=2025 LIMIT {i}')
        # Verificación
        for q in queries:
            res = SQLGuard.check_sql(q)
            self.assertTrue(res['allowed'])

class TestTenThousandQueries(unittest.TestCase):
    def test_ten_thousand_queries(self):
        for i in range(1, 10001):
            if i % 3 == 0:
                q = f'SELECT * FROM "metrics_totales_empresa_ejercicio" WHERE "empresa"=1 AND "ejercicio"=2025 LIMIT {i % 100}'
                res = SQLGuard.check_sql(q)
                self.assertTrue(res['allowed'], f"Should allow metrics: {q}")
            elif i % 3 == 1:
                q = f'SELECT * FROM "datiadb_cabecerapedidocliente" c JOIN "datiadb_lineaspedidocliente" l ON 1=1 WHERE c."CodigoEmpresa"=1 LIMIT {i % 100}'
                res = SQLGuard.check_sql(q)
                self.assertTrue(res['allowed'], f"Should allow datiadb pedidos: {q}")
            else:
                q = f'SELECT * FROM "any_other_table_{i}" LIMIT 1'
                res = SQLGuard.check_sql(q)
                self.assertFalse(res['allowed'], f"Should block: {q}")
