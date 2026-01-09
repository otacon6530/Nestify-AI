import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATHS = [
    Path.cwd() / "config.yaml",
]


def load_config() -> dict:
    data: dict = {}
    for p in DEFAULT_CONFIG_PATHS:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    data.update(loaded)
            break
    # Environment overrides
    provider = os.environ.get("NESTIFY_PROVIDER")
    model = os.environ.get("NESTIFY_MODEL")
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")

    if provider:
        data.setdefault("llm", {})
        data["llm"]["provider"] = provider
    if model:
        data.setdefault("llm", {})
        data["llm"]["model"] = model
    if api_key:
        data.setdefault("llm", {})
        data["llm"]["api_key"] = api_key
    if base_url:
        data.setdefault("llm", {})
        data["llm"]["base_url"] = base_url

    # Defaults
    data.setdefault("llm", {}).setdefault("provider", "echo")
    data.setdefault("llm", {}).setdefault("model", "local-echo")
    data.setdefault("probe", {}).setdefault("timeout_seconds", 5)
    data.setdefault("probe", {}).setdefault("retry", True)
    return data
