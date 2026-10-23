from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    """
    Abstract interface for LLM providers.
    Concrete implementations: OllamaLLMAdapter (local, default).
    Future: OpenAILLMAdapter.
    """

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a prompt to the model and return the raw text response.
        The caller is responsible for parsing structured output.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Return True if the backend (e.g. Ollama) is reachable and the
        configured model is available.
        """
        ...
