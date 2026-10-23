"""Provider definition for chat.qwen.ai."""

from __future__ import annotations

from aiprobe.models.profile import AntibotType
from aiprobe.providers.base import Provider, ProviderSpec, register_provider


@register_provider
class QwenProvider(Provider):
    """Qwen (chat.qwen.ai) provider specification."""

    @classmethod
    def get_spec(cls) -> ProviderSpec:
        return ProviderSpec(
            name="qwen",
            domains=["chat.qwen.ai"],
            candidate_endpoints={
                "chat": "/api/v2/chat/completions",
                "models": "/api/v2/models",
            },
            expected_antibot=AntibotType.CF_TLS,
        )
