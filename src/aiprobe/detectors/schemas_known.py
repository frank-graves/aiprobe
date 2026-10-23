"""Declarative reference schemas for known API formats."""

from __future__ import annotations

from typing import Any

from aiprobe.models.profile import SchemaCompat
from aiprobe.utils.jsonshape import ShapeNode, infer_shape

OPENAI_CHAT_REQUEST = {
    "model": "string",
    "messages": [{"role": "string", "content": "string"}],
    "stream": "boolean",
    "temperature": "number",
    "tools": "array",
    "tool_choice": "string",
}

OPENAI_CHAT_RESPONSE = {
    "id": "string",
    "object": "string",
    "created": "number",
    "model": "string",
    "choices": [
        {
            "message": {"role": "string", "content": "string", "tool_calls": "array"},
            "finish_reason": "string",
        }
    ],
    "usage": {
        "prompt_tokens": "number",
        "completion_tokens": "number",
        "total_tokens": "number",
    },
}

OPENAI_STREAM_CHUNK = {
    "id": "string",
    "object": "string",
    "choices": [{"delta": {"role": "string", "content": "string"}, "finish_reason": "string"}],
}


def _reference_to_shape(d: dict[str, Any]) -> ShapeNode:
    """Internal helper to convert the reference dictionaries to ShapeNodes."""
    if isinstance(d, dict):
        props = {}
        for k, v in d.items():
            if isinstance(v, dict):
                props[k] = _reference_to_shape(v)
            elif isinstance(v, list) and v:
                props[k] = ShapeNode(type="array", items=_reference_to_shape(v[0]))
            elif isinstance(v, str):
                props[k] = ShapeNode(type=v)
            else:
                props[k] = infer_shape(v)
        return ShapeNode(type="object", properties=props)
    return infer_shape(d)


REF_RESPONSE_SHAPE = _reference_to_shape(OPENAI_CHAT_RESPONSE)


def classify_compat(observed: ShapeNode, reference: ShapeNode) -> SchemaCompat:
    """Determine if the observed shape matches the OpenAI reference."""
    if not observed.properties:
        return SchemaCompat.UNKNOWN

    ref_keys = set(reference.properties.keys())
    if not ref_keys:
        return SchemaCompat.UNKNOWN

    obs_keys = set(observed.properties.keys())
    overlap = ref_keys & obs_keys
    ratio = len(overlap) / len(ref_keys)

    if ratio >= 0.8:
        return SchemaCompat.OPENAI
    elif ratio > 0:
        return SchemaCompat.CUSTOM
    return SchemaCompat.UNKNOWN
