import os
from collections.abc import Mapping
from dataclasses import dataclass

PROVIDERS = ("fake", "foundry")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    foundry_api_key: str
    foundry_resource: str
    model_fast: str
    model_smart: str
    db_path: str


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Read settings from the environment. With no API key the app runs on the fake model."""
    env = os.environ if env is None else env
    api_key = env.get("ANTHROPIC_FOUNDRY_API_KEY", "").strip()
    provider = env.get("LLM_PROVIDER", "").strip().lower() or ("foundry" if api_key else "fake")

    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    if provider == "foundry" and not api_key:
        raise ValueError("LLM_PROVIDER=foundry requires ANTHROPIC_FOUNDRY_API_KEY")

    model_fast = env.get("MODEL_FAST", "").strip() or "claude-haiku-5-5"
    model_smart = env.get("MODEL_SMART", "").strip() or "claude-sonnet-5-5"
    if model_fast == model_smart:
        # Cost is looked up by deployment name, so a shared name would bill one model's calls at the other's rate.
        raise ValueError("MODEL_FAST and MODEL_SMART must name different deployments")

    return Settings(
        llm_provider=provider,
        foundry_api_key=api_key,
        foundry_resource=env.get("ANTHROPIC_FOUNDRY_RESOURCE", "").strip(),
        model_fast=model_fast,
        model_smart=model_smart,
        db_path=env.get("DB_PATH", "").strip() or "/data/mission.db",
    )
