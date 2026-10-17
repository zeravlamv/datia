from django.test import TestCase
from datia.services.ai.reports.financial import FinancialReportGenerator

class InfografiaCafeHTMLTest(TestCase):
    def test_generate_fallback_contains_stage_and_graphics(self):
        context = {
            "kpis_globales": {
                "ventas": 3192291.24,
                "ebitda": -372506.83,
                "margen_op_pct": -11.67,
                "yoy_pct_global": -0.5,
            },
            "balance_situacion": {
                "ratios": {
                    "liquidez": 4.78,
                    "solvencia": 10.02
                },
                "totales": {
                    "patrimonio": 4454837.81
                }
            },
            "estacionalidad": [
                {"share_pct": 7.18, "yoy_pct": -5.05},
                {},{},{"share_pct": 9.30, "yoy_pct": 16.61},
                {},{},{"share_pct": 8.66, "yoy_pct": 11.13},
                {},{},{"share_pct": 9.66, "yoy_pct": -4.97},
                {},{},{"share_pct": 9.66, "yoy_pct": 19.94}
            ],
            "pl_analisis": []
        }
        gen = FinancialReportGenerator()
        res = gen.generate(context=context, ejercicio=2025, force_fallback=True, role="Controller Financiero / CFO")
        html = res.get("html") or ""
        self.assertIn("gauge-grid", html)
        self.assertIn("story-quarter-grid", html)
        self.assertTrue(len(html) > 200)
