import pytest

from app.config import load_settings


def test_provider_is_fake_when_no_api_key():
    settings = load_settings({})

    assert settings.llm_provider == "fake"


def test_provider_is_foundry_when_api_key_is_set():
    settings = load_settings({"ANTHROPIC_FOUNDRY_API_KEY": "test-key", "ANTHROPIC_FOUNDRY_RESOURCE": "mc-test"})

    assert settings.llm_provider == "foundry"


def test_explicit_fake_wins_over_api_key():
    settings = load_settings(
        {"LLM_PROVIDER": "fake", "ANTHROPIC_FOUNDRY_API_KEY": "test-key"}
    )

    assert settings.llm_provider == "fake"


def test_explicit_foundry_without_key_is_rejected():
    with pytest.raises(ValueError, match="ANTHROPIC_FOUNDRY_API_KEY"):
        load_settings({"LLM_PROVIDER": "foundry"})


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        load_settings({"LLM_PROVIDER": "openai"})


def test_deployment_names_come_from_env():
    settings = load_settings({"MODEL_FAST": "my-haiku", "MODEL_SMART": "my-sonnet"})

    assert settings.model_fast == "my-haiku"
    assert settings.model_smart == "my-sonnet"


def test_defaults_for_models_and_db_path():
    settings = load_settings({})

    assert settings.model_fast == "claude-haiku-5-5"
    assert settings.model_smart == "claude-sonnet-5-5"
    assert settings.db_path == "/data/mission.db"


def test_one_deployment_may_serve_both_roles():
    settings = load_settings({"MODEL_FAST": "mc-shared", "MODEL_SMART": "mc-shared"})

    assert settings.model_fast == settings.model_smart == "mc-shared"


def test_foundry_needs_a_resource_name():
    with pytest.raises(ValueError, match="ANTHROPIC_FOUNDRY_RESOURCE"):
        load_settings({"ANTHROPIC_FOUNDRY_API_KEY": "test-key"})
