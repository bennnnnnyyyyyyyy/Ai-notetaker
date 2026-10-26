"""Google Gemini API adapter.

The adapter is opt-in through ``LLM_PROVIDER=gemini``. API keys are read from
the local environment and are never included in logs or error messages.
"""

import logging

import httpx

from backend.adapters.base_llm import BaseLLMAdapter
from backend.config import settings

logger = logging.getLogger(__name__)


class GeminiLLMAdapter(BaseLLMAdapter):
    def __init__(self):
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model
        self._base_url = settings.gemini_base_url.rstrip("/")

    def _url(self) -> str:
        return f"{self._base_url}/models/{self._model}:generateContent"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise RuntimeError("Gemini is not configured: set GEMINI_API_KEY in .env")

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        try:
            response = httpx.post(
                self._url(),
                params={"key": self._api_key},
                json=payload,
                timeout=settings.gemini_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            if not text:
                raise RuntimeError("Gemini returned no text")
            return text
        except httpx.HTTPStatusError as exc:
            logger.error("Gemini request failed with HTTP %s", exc.response.status_code)
            raise RuntimeError(f"Gemini request failed with HTTP {exc.response.status_code}") from None
        except httpx.HTTPError as exc:
            logger.error("Gemini request failed: %s", type(exc).__name__)
            raise RuntimeError("Gemini request failed; check connectivity and API configuration") from None

    def is_available(self) -> bool:
        return bool(self._api_key and self._model)
