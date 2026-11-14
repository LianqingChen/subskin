"""OpenAI-compatible multimodal client — the only place that knows about providers.

Any vision model works if it speaks ``/chat/completions`` with ``image_url`` parts.  Provider is
picked from the model name unless ``VLM_BASE_URL``/``VLM_API_KEY`` are set explicitly.
Every exchange (prompt text, response, usage — never image bytes) is appended to the run log.
"""

import base64
import hashlib
import io
import json
import os
import re
import time
from threading import Event
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
QUOTA_EXIT_CODE = 75


def _env() -> Dict[str, str]:
    env = dict(os.environ)
    f = REPO / "web" / "backend" / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
            if m and m.group(1) not in env:
                env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def provider_for(model: str) -> Dict[str, str]:
    env = _env()
    if env.get("VLM_BASE_URL") and env.get("VLM_API_KEY"):
        return {"base_url": env["VLM_BASE_URL"], "api_key": env["VLM_API_KEY"], "name": "custom"}
    # Bailian token-plan endpoint serves qwen*/deepseek*/glm* under one key
    return {"base_url": env["DASHSCOPE_BASE_URL"], "api_key": env["DASHSCOPE_API_KEY"], "name": "dashscope"}


def image_part(im: Image.Image, quality: int = 90) -> Dict[str, Any]:
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=quality)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()}}


def extract_json(text: str) -> Optional[Any]:
    """Last JSON object in the reply (models wrap JSON in prose / code fences)."""
    if not text:
        return None
    fences = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cands = fences + [text[i:] for i in [m.start() for m in re.finditer(r"\{", text)][:3]]
    for c in cands:
        depth, end = 0, None
        for j, ch in enumerate(c):
            depth += ch == "{"
            depth -= ch == "}"
            if depth == 0 and ch == "}":
                end = j + 1
                break
        if end:
            try:
                return json.loads(c[:end])
            except json.JSONDecodeError:
                continue
    return None


class ProviderQuotaExhausted(RuntimeError):
    """The current provider subscription has no inference quota left."""


class VLM:
    def __init__(self, model: str, log_path: Path, temperature: float = 0.1, max_tokens: int = 16000):
        from openai import OpenAI

        p = provider_for(model)
        self.model, self.provider = model, p["name"]
        self.client = OpenAI(api_key=p["api_key"], base_url=p["base_url"], timeout=300, max_retries=0)
        self.endpoint_fingerprint = hashlib.sha256(p["base_url"].encode()).hexdigest()
        self.log_path = log_path
        self.quota_exhausted = Event()
        self.temperature, self.max_tokens = temperature, max_tokens
        # Resume only replies bound to the same image and prompt payload.
        self.cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        if log_path.exists():
            for line in log_path.read_text().splitlines():
                rec = json.loads(line)
                fingerprint = rec.get("request_sha256")
                if (rec.get("parsed") and rec.get("model") == model and fingerprint
                        and rec.get("response_id") and rec.get("finish_reason") == "stop"):
                    data = extract_json(rec["reply"])
                    if data is not None:
                        self.cache[(rec["step"], fingerprint)] = {
                            "data": data, "response_id": rec["response_id"],
                            "model_returned": rec.get("model_returned"), "finish_reason": "stop",
                        }

    def ask(self, step: str, system: str, parts: List[Dict[str, Any]], retries: int = 3) -> Dict[str, Any]:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": parts}]
        request = {"model": self.model, "endpoint": self.endpoint_fingerprint, "messages": msgs,
                   "temperature": self.temperature, "max_tokens": self.max_tokens}
        encoded = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        fingerprint = hashlib.sha256(encoded).hexdigest()
        cached = self.cache.get((step, fingerprint))
        if cached is not None:
            return {**cached, "raw": "", "secs": 0, "cached": True, "request_sha256": fingerprint}
        text_only = [p["text"] for p in parts if p["type"] == "text"]
        last_err = None
        for attempt in range(retries):
            if self.quota_exhausted.is_set():
                raise ProviderQuotaExhausted(f"{self.model} quota exhausted at {step}")
            t0 = time.time()
            try:
                r = self.client.chat.completions.create(model=self.model, messages=msgs,
                                                        temperature=self.temperature, max_tokens=self.max_tokens)
                msg = r.choices[0].message
                content = msg.content or ""
                data = extract_json(content)
                rec = {"step": step, "model": self.model, "attempt": attempt, "secs": round(time.time() - t0, 1),
                       "n_images": sum(p["type"] == "image_url" for p in parts), "prompt": text_only,
                       "reply": content, "usage": r.usage.model_dump() if r.usage else None, "parsed": data is not None,
                       "request_sha256": fingerprint, "response_id": getattr(r, "id", None),
                       "model_returned": getattr(r, "model", None),
                       "finish_reason": r.choices[0].finish_reason}
                self._log(rec)
                if data is not None:
                    return {"data": data, "raw": content, "secs": rec["secs"], "cached": False,
                            "request_sha256": fingerprint, "response_id": rec["response_id"],
                            "model_returned": rec["model_returned"], "finish_reason": rec["finish_reason"]}
                last_err = "unparseable reply" if content else "empty reply (reasoning used the whole max_tokens, or no image support)"
            except Exception as e:  # noqa: BLE001 — provider errors are logged and retried
                error = str(e)
                key = self.client.api_key
                if key:
                    error = error.replace(key, "[key omitted]")
                error = re.sub(r"data:[^,\s]+;base64,[A-Za-z0-9+/=_-]+", "[image omitted]", error)
                last_err = error[:500]
                status = getattr(e, "status_code", None)
                code = getattr(e, "code", None)
                self._log({"step": step, "model": self.model, "attempt": attempt, "error": last_err,
                           "http_status": status, "provider_error_code": code, "request_sha256": fingerprint})
                if status == 429 and code == "insufficient_quota":
                    self.quota_exhausted.set()
                    raise ProviderQuotaExhausted(f"{self.model} quota exhausted at {step}") from None
                if isinstance(status, int) and 400 <= status < 500 and status not in (408, 409, 429):
                    break
                time.sleep(3 * (attempt + 1))
        raise RuntimeError(f"{self.model} failed at {step}: {last_err}")

    def _log(self, rec: Dict[str, Any]) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
