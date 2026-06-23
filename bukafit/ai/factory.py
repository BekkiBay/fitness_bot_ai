from bukafit.ai.codex import CodexProvider
from bukafit.ai.mock import MockProvider
from bukafit.ai.provider import ModelProvider
from bukafit.config import settings


def get_provider() -> ModelProvider:
    if settings.ai_provider == "codex":
        return CodexProvider()
    return MockProvider()
