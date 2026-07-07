"""Smoke test — verifies config loads from environment."""


def test_config_loads():
    from ragcore.config import get_settings

    settings = get_settings()
    assert settings.default_provider is not None
    assert settings.top_k > 0
    assert settings.query_budget_usd > 0
