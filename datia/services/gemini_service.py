import logging
import os
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("datia")


class GeminiService:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or ""
        self.model = model or os.environ.get("GEMINI_MODEL_TEXT") or "gemini-2.5-flash"
        self.base_url = base_url or os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def _normalize_model_name(name: Optional[str]) -> str:
        s = (name or "").strip()
        if s.startswith("models/"):
            s = s[len("models/") :]
        return s

    def list_models(self, timeout: int = 10) -> list:
        if not self.is_configured():
            return []
        url = f"{self.base_url}/v1beta/models"
        params = {"key": self.api_key}
        res = requests.get(url, params=params, timeout=max(5, int(timeout or 10)))
        if res.status_code != 200:
            return []
        data = res.json() if res.content else {}
        models = data.get("models") or []
        out = []
        for m in models:
            if not isinstance(m, dict):
                continue
            methods = m.get("supportedGenerationMethods") or []
            if methods and "generateContent" not in methods:
                continue
            name = self._normalize_model_name(m.get("name"))
            if name:
                out.append(name)
        return out

    def _pick_best_model(self, requested: str, available: list) -> str:
        req = self._normalize_model_name(requested)
        avail = [self._normalize_model_name(x) for x in (available or []) if x]
        if req in avail:
            return req
        if (req + "-latest") in avail:
            return req + "-latest"
        if req.startswith("gemini-1.5-pro") and "gemini-1.5-pro-latest" in avail:
            return "gemini-1.5-pro-latest"
        if req.startswith("gemini-1.5-flash") and "gemini-1.5-flash-latest" in avail:
            return "gemini-1.5-flash-latest"
        for cand in ("gemini-1.5-pro-latest", "gemini-1.5-flash-latest", "gemini-1.5-pro", "gemini-1.5-flash"):
            if cand in avail:
                return cand
        return avail[0] if avail else req

    def generate_text_with_policy(
        self,
        prompt: str,
        kind: str,
        requested_model: Optional[str] = None,
        force_fallback: bool = False,
        deadline: int = 240,
        req_id: Optional[str] = None,
        prefer_no_stream: bool = True,
        allow_degrade: bool = True,
        **_: Any,
    ) -> Dict[str, Any]:
        if force_fallback:
            return {"status": "fallback", "reason": "force_fallback", "model": "fallback"}
        if not self.is_configured():
            return {"status": "fallback", "reason": "missing_api_key", "model": "fallback"}

        kind_l = (kind or "").strip().lower()
        if kind_l in ("infografia", "infographic", "infografias"):
            default_model = os.environ.get("GEMINI_MODEL_INFOGRAPHIC") or self.model
        elif kind_l in ("financiera", "ventas", "report", "informe", "informes", "ai_report"):
            default_model = os.environ.get("GEMINI_MODEL_REPORT") or self.model
        else:
            default_model = self.model

        model_name = requested_model or default_model
        try:
            text = self.generate_text(prompt=prompt, model=model_name, timeout=deadline)
            if text:
                return {"status": "ok", "text": text, "model": self._normalize_model_name(model_name), "provider": "gemini"}
            return {"status": "fallback", "reason": "empty_response", "model": "fallback"}
        except Exception as e:
            logger.error(f"[Gemini] Error generando texto: {e}")
            return {"status": "fallback", "reason": "exception", "model": "fallback"}

    def generate_text(self, prompt: str, model: Optional[str] = None, timeout: int = 60) -> str:
        if not self.is_configured():
            raise RuntimeError("GEMINI_API_KEY no configurada")

        target_model = self._normalize_model_name(model or self.model)
        url = f"{self.base_url}/v1beta/models/{target_model}:generateContent"
        params = {"key": self.api_key}

        body = {
            "contents": [{"role": "user", "parts": [{"text": str(prompt or "")}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "maxOutputTokens": 2048,
            },
        }

        t0 = time.time()
        res = requests.post(url, params=params, json=body, timeout=max(5, int(timeout or 60)))
        dt = time.time() - t0
        if res.status_code == 404:
            avail = self.list_models(timeout=10)
            alt = self._pick_best_model(target_model, avail)
            if alt and alt != target_model:
                target_model = alt
                url = f"{self.base_url}/v1beta/models/{target_model}:generateContent"
                t0 = time.time()
                res = requests.post(url, params=params, json=body, timeout=max(5, int(timeout or 60)))
                dt = time.time() - t0
        if res.status_code != 200:
            raise RuntimeError(f"Gemini HTTP {res.status_code}: {res.text[:200]}")

        data = res.json() if res.content else {}
        try:
            cand = (data.get("candidates") or [])[0] or {}
            content = cand.get("content") or {}
            parts = content.get("parts") or []
            texts = []
            for p in parts:
                if isinstance(p, dict) and p.get("text"):
                    texts.append(str(p.get("text")))
            out = "\n".join(texts).strip()
            logger.info(f"[Gemini] OK model={target_model} seconds={dt:.2f}")
            return out
        except Exception:
            return ""
