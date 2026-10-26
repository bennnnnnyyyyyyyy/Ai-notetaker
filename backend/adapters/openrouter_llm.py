"""OpenRouter chat-completions adapter.

Opt-in through ``LLM_PROVIDER=openrouter``. The API key is never logged.
"""

import logging

import httpx

from backend.adapters.base_llm import BaseLLMAdapter
from backend.config import settings

logger = logging.getLogger(__name__)


class OpenRouterLLMAdapter(BaseLLMAdapter):
    def __init__(self):
        self._api_key = settings.openrouter_key
        self._model = settings.openrouter_model
        self._url = settings.openrouter_base_url.rstrip("/") + "/chat/completions"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self._api_key:
            raise RuntimeError("OpenRouter is not configured: set OPENROUTER_KEY in .env")
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = httpx.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=settings.openrouter_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                raise RuntimeError("OpenRouter returned no text")
            return content.strip()
        except httpx.HTTPStatusError as exc:
            logger.error("OpenRouter request failed with HTTP %s", exc.response.status_code)
            raise RuntimeError(f"OpenRouter request failed with HTTP {exc.response.status_code}") from None
        except httpx.HTTPError:
            logger.error("OpenRouter request failed")
            raise RuntimeError("OpenRouter request failed; check connectivity and API configuration") from None

    def is_available(self) -> bool:
        return bool(self._api_key and self._model)
