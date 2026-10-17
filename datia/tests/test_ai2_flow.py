import unittest
from unittest.mock import patch, MagicMock

from datia.services.ai.reports.financial import FinancialReportGenerator
from datia.services.ollama_service import OllamaService
from datia.services.dashboard_service import AI_PROGRESS
import requests


class TestFinancialReportGenerator(unittest.TestCase):
    def setUp(self):
        self.context = {
            "kpis_globales": {"ventas": 1000000, "ebitda": 50000, "margen_op_pct": 12.3},
            "balance_situacion": {"ratios": {"liquidez": 1.8, "solvencia": 2.1}},
            "meta": {"empresa_id": 1}
        }

    @patch.object(OllamaService, "generate_text_with_policy")
    @patch.object(OllamaService, "list_models")
    @patch.object(OllamaService, "check_connection", return_value=True)
    def test_llm_ok(self, _conn, _list, _gen):
        _list.return_value = ["qwen2.5:14b-instruct-q4_k_m"]
        _gen.return_value = {"status": "ok", "text": "<div>AI Report</div>", "model": "qwen2.5:14b-instruct-q4_k_m"}
        gen = FinancialReportGenerator()
        res = gen.generate(self.context, ejercicio=2025, model=None, role="Controller Financiero / CFO")
        self.assertEqual(res["status"], "success")
        self.assertIn("AI Report", res["html"])
        self.assertNotIn("Modo Fallback", res["html"])
        self.assertEqual(res["model_used"], "qwen2.5:14b-instruct-q4_k_m")

    @patch.object(OllamaService, "generate_text_with_policy", return_value={"status": "fallback"})
    @patch.object(OllamaService, "list_models", return_value=["qwen2.5:14b-instruct-q4_k_m"])
    @patch.object(OllamaService, "check_connection", return_value=True)
    def test_llm_fallback(self, _conn, _list, _gen):
        gen = FinancialReportGenerator()
        res = gen.generate(self.context, ejercicio=2025, model=None, role="Controller Financiero / CFO")
        self.assertEqual(res["status"], "success")
        self.assertIn("Modo Fallback", res["html"])
        self.assertEqual(res["model_used"], "fallback_algorithm")

    @patch.object(OllamaService, "generate_text_with_policy")
    @patch("datia.services.ai.reports.financial.ServiceFactory.get_embedding_service")
    def test_vectorized_summary_used(self, mock_emb_service, _gen):
        class _EmbMock:
            def embed_text(self, t): return [0.1] * 16
            def add_embedding(self, **kwargs): return True
            def ensure_cfo_guide_indexed(self): return True
            def get_cfo_guides(self): return [{"key":"cfo_solvencia","text":"Solvencia","vector":[0.2]*16}]
        mock_emb_service.return_value = _EmbMock()
        _gen.return_value = {"status": "ok", "text": "<div>AI Report</div>", "model": "qwen2.5:14b-instruct-q4_k_m"}
        gen = FinancialReportGenerator()
        res = gen.generate(self.context, ejercicio=2025, model="qwen2.5:14b-instruct-q4_k_m", role="Controller Financiero / CFO")
        self.assertEqual(res["status"], "success")
        args, kwargs = _gen.call_args
        prompt = kwargs.get("prompt") or args[0]
        self.assertTrue(len(prompt) > 0)
        self.assertIn("Solvencia", prompt)

    @patch.object(OllamaService, "generate_text_with_policy")
    def test_prompt_contains_sections(self, _gen):
        _gen.return_value = {"status": "ok", "text": "<div>AI Report</div>", "model": "qwen2.5:14b-instruct-q4_k_m"}
        gen = FinancialReportGenerator()
        res = gen.generate(self.context, ejercicio=2025, model=None, role="Controller Financiero / CFO")
        args, kwargs = _gen.call_args
        prompt = kwargs.get("prompt") or args[0]
        for s in ["Diagnóstico Rápido", "Desempeño Operativo", "Solidez Estructural", "Recomendaciones Básicas", "Evidencia cuantitativa", "Ratios ampliados", "Resultados Trimestrales"]:
            self.assertIn(s, prompt)


class TestOllamaPolicy(unittest.TestCase):
    @patch.object(OllamaService, "check_connection", return_value=True)
    @patch.object(OllamaService, "list_models", return_value=[])
    def test_requested_model_when_no_tags(self, _list, _conn):
        svc = OllamaService()
        with patch.object(OllamaService, "generate_text") as gen_text:
            gen_text.return_value = "<div>LLM OK</div>"
            res = svc.generate_text_with_policy(
                prompt="test",
                kind="financiera",
                requested_model="qwen2.5:14b-instruct-q4_k_m",
                force_fallback=False,
                deadline=30
            )
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["model"], "qwen2.5:14b-instruct-q4_k_m")

    @patch.object(OllamaService, "check_connection", return_value=True)
    @patch.object(OllamaService, "list_models", return_value=[])
    def test_requested_model_qwen3_30b(self, _list, _conn):
        svc = OllamaService()
        with patch.object(OllamaService, "generate_text") as gen_text:
            gen_text.return_value = "<div>LLM OK</div>"
            res = svc.generate_text_with_policy(
                prompt="test",
                kind="financiera",
                requested_model="qwen3:30b",
                force_fallback=False,
                deadline=600
            )
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["model"], "qwen3:30b")
            # Ensure large timeout passed to generator
            args, kwargs = gen_text.call_args

    @patch.object(requests, "post")
    def test_progress_events_streaming(self, mock_post):
        class _Resp:
            status_code = 200
            def iter_lines(self, decode_unicode=True):
                lines = [
                    json.dumps({"response": "A", "done": False}),
                    json.dumps({"response": "B", "done": False}),
                    json.dumps({"response": "", "done": False}),
                    json.dumps({"response": "C", "done": True})
                ]
                for l in lines:
                    yield l
        mock_post.return_value = _Resp()
        req_id = "req_stream_1"
        try:
            AI_PROGRESS.pop(req_id, None)
        except Exception:
            pass
        svc = OllamaService()
        txt = svc.generate_text("prompt", timeout=20, model="mistral", options=None, req_id=req_id)
        self.assertEqual(txt, "ABC")
        self.assertIn(req_id, AI_PROGRESS)
        steps = [e.get("step") for e in AI_PROGRESS.get(req_id, [])]
        self.assertIn("OLLAMA_START", steps)
        self.assertIn("OLLAMA_STREAM", steps)
        self.assertIn("OLLAMA_DONE", steps)
