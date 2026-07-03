from __future__ import annotations

from harness.config import HarnessConfig


def test_provider_api_key_env_aliases(tmp_path, monkeypatch):
    monkeypatch.delenv("THREE_SIX_ONE_API_KEY", raising=False)
    monkeypatch.delenv("THREESIXONE_API_KEY", raising=False)
    monkeypatch.delenv("API_361_KEY", raising=False)
    monkeypatch.delenv("361API_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
default_provider: 361api-openai
providers:
  361api-openai:
    name: openai-compatible
    model: gpt-4o
    api_key: "${THREE_SIX_ONE_API_KEY}"
    api_key_env:
      - THREE_SIX_ONE_API_KEY
      - OPENAI_API_KEY
    base_url: "https://www.361api.com/v1"
""",
        encoding="utf-8",
    )

    cfg = HarnessConfig.from_yaml(str(config_path))

    assert cfg.default_provider == "361api-openai"
    assert cfg.providers["361api-openai"].api_key == "sk-test"
    assert cfg.providers["361api-openai"].base_url == "https://www.361api.com/v1"


def test_from_yaml_honors_env_default_provider_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_DEFAULT_PROVIDER", "my-361api")
    monkeypatch.delenv("THREE_SIX_ONE_API_KEY", raising=False)
    monkeypatch.delenv("THREESIXONE_API_KEY", raising=False)
    monkeypatch.delenv("API_361_KEY", raising=False)
    monkeypatch.delenv("361API_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("BLTCY_API_KEY", "sk-compat")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
default_provider: hub-openai
compression:
  summary_provider: 361api-mini
providers:
  361api-openai:
    name: openai-compatible
    model: gpt-4o
    api_key: "${THREE_SIX_ONE_API_KEY}"
    api_key_env:
      - BLTCY_API_KEY
    base_url: "https://www.361api.com/v1"
  361api-mini:
    name: openai-compatible
    model: gpt-4o-mini
    api_key: "${THREE_SIX_ONE_API_KEY}"
    api_key_env:
      - BLTCY_API_KEY
    base_url: "https://www.361api.com/v1"
""",
        encoding="utf-8",
    )

    cfg = HarnessConfig.from_yaml(str(config_path))

    assert cfg.default_provider == "361api-openai"
    assert cfg.compression.summary_provider == "361api-mini"
    assert cfg.providers["361api-openai"].api_key == "sk-compat"


def test_from_env_adds_361api_provider(monkeypatch):
    monkeypatch.delenv("HARNESS_DEFAULT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("THREE_SIX_ONE_API_KEY", "sk-361")

    cfg = HarnessConfig.from_env()

    assert cfg.default_provider == "361api-openai"
    assert cfg.providers["361api-openai"].name == "openai-compatible"
    assert cfg.providers["361api-openai"].api_key == "sk-361"
    assert cfg.providers["361api-openai"].base_url == "https://www.361api.com/v1"


def test_from_env_accepts_bltcy_key_and_provider_alias(monkeypatch):
    monkeypatch.setenv("HARNESS_DEFAULT_PROVIDER", "my-361api")
    monkeypatch.delenv("THREE_SIX_ONE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("BLTCY_API_KEY", "sk-bcompat")

    cfg = HarnessConfig.from_env()

    assert cfg.default_provider == "361api-openai"
    assert cfg.providers["361api-openai"].api_key == "sk-bcompat"
