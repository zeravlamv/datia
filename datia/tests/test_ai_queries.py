import re
import unittest
from unittest.mock import patch
from datia.services.query_builder import QueryBuilder


class TestAIQueries(unittest.TestCase):
    def setUp(self):
        self.empresa = 1
        self.ejercicio = 2025
        self.context = {'empresa': self.empresa, 'ejercicio': self.ejercicio, 'training_enabled': False}

    def _mock_validate_columns(self, table_name: str, candidates):
        # Simula presencia de columnas estándar en cabecera de pedido cliente
        cols = {
            'codigoempresa': 'CodigoEmpresa',
            'ejerciciopedido': 'EjercicioPedido',
            'numeropedido': 'NumeroPedido',
            'fechapedido': 'FechaPedido',
            'importebruto': 'ImporteBruto',
            'importecoste': 'ImporteCoste',
            'cantidad': 'Cantidad',
            'nombre': 'Nombre',
        }
        # Si se piden candidatos, devolver el primero que exista
        best = None
        for c in candidates or []:
            lc = c.lower()
            if lc in cols:
                best = cols[lc]
                break
        return best, cols

    def _mock_audit_cols(self, table_name: str):
        return {'company': 'CodigoEmpresa', 'year': 'EjercicioPedido', 'count': 'NumeroPedido'}

    @patch.object(QueryBuilder, '_resolve_audit_cols')
    @patch.object(QueryBuilder, '_validate_table_columns')
    def test_ranking_top_20_clientes_mayo(self, m_validate, m_audit):
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols

        q = "Top 20 clientes en mayo 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertIn('LIMIT 20', sql)
        self.assertIn('metrics_totales_empresa_ejercicio_cliente_mes', sql)
        self.assertIn('mes BETWEEN 5 AND 5', sql)
        self.assertRegex(sql, r'ORDER BY 2 DESC')

    @patch.object(QueryBuilder, '_resolve_audit_cols')
    @patch.object(QueryBuilder, '_validate_table_columns')
    def test_cliente_compra_menos_asc(self, m_validate, m_audit):
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols

        q = "Qué cliente compra menos en 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        self.assertRegex(sql, r'ORDER BY 2 ASC')
        self.assertIn('metrics_totales_empresa_ejercicio_cliente', sql)
        self.assertIn('ejercicio = 2025', sql)

    @patch.object(QueryBuilder, '_resolve_audit_cols')
    @patch.object(QueryBuilder, '_validate_table_columns')
    def test_margen_por_cliente_ultimo_trimestre(self, m_validate, m_audit):
        m_validate.side_effect = self._mock_validate_columns
        m_audit.side_effect = self._mock_audit_cols

        q = "Margen por cliente del último trimestre 2025"
        res = QueryBuilder.build_from_nl(q, self.context)
        self.assertIsInstance(res, dict)
        sql = res.get('sql') or ''
        # Debe aplicar filtro de trimestre 4 si se indica "último trimestre"
        self.assertRegex(sql, r'EXTRACT\(QUARTER FROM .*?\) = 4')
        # Métrica en meta: margin
        im = res.get('intent_meta') or {}
        self.assertEqual(im.get('metric'), 'margin')


if __name__ == '__main__':
    unittest.main()
