"""Generic JSON schema inference utility."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ShapeNode(BaseModel):
    """Recursive representation of a JSON value's shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str
    properties: dict[str, ShapeNode] = Field(default_factory=dict)
    items: ShapeNode | None = None
    optional_keys: list[str] = Field(default_factory=list)
    samples: int = 1


def infer_shape(obj: Any) -> ShapeNode:
    """Infer the shape of a single JSON-serializable object."""
    if obj is None:
        return ShapeNode(type="null")
    if isinstance(obj, bool):
        return ShapeNode(type="boolean")
    if isinstance(obj, (int, float)):
        return ShapeNode(type="number")
    if isinstance(obj, str):
        return ShapeNode(type="string")
    if isinstance(obj, list):
        if not obj:
            return ShapeNode(type="array")
        items_shape = infer_shape(obj[0])
        for item in obj[1:]:
            items_shape = merge_shapes(items_shape, infer_shape(item))
        return ShapeNode(type="array", items=items_shape)
    if isinstance(obj, dict):
        props = {k: infer_shape(v) for k, v in obj.items()}
        return ShapeNode(type="object", properties=props)

    return ShapeNode(type="unknown")


def merge_shapes(a: ShapeNode, b: ShapeNode) -> ShapeNode:
    """Merge two shapes. Differing types become 'mixed'."""
    if (
        a.type != b.type
        and a.type not in ("mixed", "unknown")
        and b.type not in ("mixed", "unknown")
    ):
        return ShapeNode(type="mixed", samples=a.samples + b.samples)

    if a.type == "object" or b.type == "object":
        all_keys = set(a.properties.keys()) | set(b.properties.keys())
        merged_props = {}
        optional = set(a.optional_keys) | set(b.optional_keys)

        for k in all_keys:
            if k in a.properties and k in b.properties:
                merged_props[k] = merge_shapes(a.properties[k], b.properties[k])
            elif k in a.properties:
                merged_props[k] = a.properties[k]
                optional.add(k)
            else:
                merged_props[k] = b.properties[k]
                optional.add(k)

        return ShapeNode(
            type="object",
            properties=merged_props,
            optional_keys=list(optional),
            samples=a.samples + b.samples,
        )

    if a.type == "array" and b.type == "array":
        items = merge_shapes(a.items, b.items) if a.items and b.items else a.items or b.items
        return ShapeNode(type="array", items=items, samples=a.samples + b.samples)

    return ShapeNode(type=a.type, samples=a.samples + b.samples)


def to_json_schema(node: ShapeNode) -> dict[str, Any]:
    """Convert a ShapeNode to a standard JSON Schema dictionary."""
    schema: dict[str, Any] = {"type": node.type}

    if node.type == "object":
        schema["properties"] = {k: to_json_schema(v) for k, v in node.properties.items()}
        req = list(set(node.properties.keys()) - set(node.optional_keys))
        if req:
            schema["required"] = req

    elif node.type == "array" and node.items:
        schema["items"] = to_json_schema(node.items)

    return schema


def is_compatible(observed: ShapeNode, reference: ShapeNode) -> tuple[bool, list[str]]:
    """Check if observed shape contains all fields/types of the reference."""
    diffs: list[str] = []

    if observed.type != reference.type and observed.type != "mixed":
        diffs.append(f"type mismatch: expected {reference.type}, got {observed.type}")
        return False, diffs

    if reference.type == "object" and observed.type == "object":
        ref_keys = set(reference.properties.keys())
        obs_keys = set(observed.properties.keys())

        missing = ref_keys - obs_keys
        if missing:
            diffs.append(f"missing keys: {missing}")

        for k in ref_keys & obs_keys:
            comp, d = is_compatible(observed.properties[k], reference.properties[k])
            if not comp:
                diffs.extend([f"{k}.{x}" for x in d])

    elif reference.type == "array" and observed.type == "array":
        if reference.items and observed.items:
            comp, d = is_compatible(observed.items, reference.items)
            if not comp:
                diffs.extend([f"items.{x}" for x in d])

    return len(diffs) == 0, diffs
