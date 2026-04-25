from harness.config import ProviderConfig
from harness.llm.base import LLMConfig, LLMProvider


def build_provider(cfg: ProviderConfig) -> LLMProvider:
    """Factory: instantiate the correct LLMProvider for the given config."""
    llm_cfg = LLMConfig(
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        timeout=cfg.timeout,
        max_tokens=cfg.max_tokens,
        temperature=cfg.temperature,
        extra=cfg.extra,
    )
    name = cfg.name.lower()
    if name == "anthropic":
        from harness.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(llm_cfg)
    elif name in ("openai", "openai-compatible"):
        from harness.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(llm_cfg)
    else:
        raise ValueError(
            f"Unknown provider name: {cfg.name!r}. "
            f"Use 'openai', 'openai-compatible', or 'anthropic'."
        )
