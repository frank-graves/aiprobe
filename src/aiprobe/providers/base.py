"""Declarative provider spec."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from aiprobe.models.profile import AntibotType


class ProviderSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    domains: list[str]
    candidate_endpoints: dict[str, str] = Field(default_factory=dict)
    expected_antibot: AntibotType


class Provider(ABC):
    @classmethod
    @abstractmethod
    def get_spec(cls) -> ProviderSpec: ...


PROVIDERS: dict[str, type[Provider]] = {}


def register_provider[P: type[Provider]](provider_cls: P) -> P:
    spec = provider_cls.get_spec()
    PROVIDERS[spec.name] = provider_cls
    return provider_cls
