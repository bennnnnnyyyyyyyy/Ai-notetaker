"""
Ollama LLM adapter.

Calls the local Ollama HTTP API (http://localhost:11434).
The model (e.g. phi3:mini) must be pulled before use:
    ollama pull phi3:mini
"""

import logging
import httpx

from backend.adapters.base_llm import BaseLLMAdapter
from backend.config import settings

logger = logging.getLogger(__name__)


class OllamaLLMAdapter(BaseLLMAdapter):

    def __init__(self):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a chat completion request to Ollama and return the assistant's text.
        Uses the /api/chat endpoint with stream=False.
        """
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        logger.debug("Calling Ollama model=%s", self._model)
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=300,  # long timeout for CPU inference
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
        except httpx.HTTPError as exc:
            logger.error("Ollama request failed: %s", exc)
            raise RuntimeError(
                f"Ollama is not reachable at {self._base_url}. "
                "Ensure Ollama is running: 'ollama serve'"
            ) from exc

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self._base_url}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            available = any(self._model in m for m in models)
            if not available:
                logger.warning(
                    "Model '%s' not found in Ollama. Run: ollama pull %s",
                    self._model, self._model,
                )
            return available
        except Exception:
            return False
