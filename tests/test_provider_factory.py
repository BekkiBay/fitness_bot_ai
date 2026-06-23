from bukafit.ai.factory import get_provider
from bukafit.ai.mock import MockProvider
from bukafit.ai.codex import CodexProvider
from bukafit.config import settings


def test_default_is_mock(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    assert isinstance(get_provider(), MockProvider)


def test_codex_selected(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "codex")
    assert isinstance(get_provider(), CodexProvider)


def test_unknown_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "whatever")
    assert isinstance(get_provider(), MockProvider)
