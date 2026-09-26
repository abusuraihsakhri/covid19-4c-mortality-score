"""Deterministic local response adapter used by the legacy supervisory interface."""

from .base import PHIGuard


class MockLLM:
    def __init__(self, system_name: str = "Covid19 4C Mortality Score"):
        self.system_name = system_name

    def invoke(self, prompt: str) -> str:
        PHIGuard.assert_no_phi(prompt)
        return (
            f"[{self.system_name} Deterministic Verification Engine]: "
            f"Static verification response for query: '{prompt[:60]}...'."
        )


class LLMFactory:
    """Create only the providers implemented by this repository."""

    @staticmethod
    def create(provider: str = "mock", system_name: str = "Covid19 4C Mortality Score"):
        normalized = str(provider).strip().lower()
        if normalized in {"mock", "deterministic", "test"}:
            return MockLLM(system_name)
        raise ValueError(
            f"Unsupported MODEL_PROVIDER {provider!r}; only the deterministic mock provider is implemented"
        )
