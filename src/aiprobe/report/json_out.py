"""JSON report renderer."""

from __future__ import annotations

import json

from aiprobe.models.profile import Profile


def render_json(profile: Profile) -> str:
    """Render a Profile as a JSON string."""
    return json.dumps(profile.model_dump(mode="json"), indent=2)
