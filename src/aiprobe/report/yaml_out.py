"""YAML report renderer."""

from __future__ import annotations

from typing import cast

import yaml

from aiprobe.models.profile import Profile


def render_yaml(profile: Profile) -> str:
    """Render a Profile as a YAML string."""
    payload = profile.model_dump(mode="json")
    return cast(
        str,
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        ),
    )
