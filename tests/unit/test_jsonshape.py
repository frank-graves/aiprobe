"""Offline tests for JSON shape inference."""

from __future__ import annotations

from aiprobe.utils.jsonshape import (
    ShapeNode,
    infer_shape,
    is_compatible,
    merge_shapes,
    to_json_schema,
)


def test_infer_shape_nested() -> None:
    obj = {"a": 1, "b": {"c": True, "d": [1, 2]}, "e": None}
    shape = infer_shape(obj)

    assert shape.type == "object"
    assert shape.properties["a"].type == "number"
    assert shape.properties["b"].type == "object"
    assert shape.properties["b"].properties["c"].type == "boolean"
    assert shape.properties["b"].properties["d"].type == "array"
    assert shape.properties["b"].properties["d"].items.type == "number"
    assert shape.properties["e"].type == "null"


def test_merge_shapes_mixed() -> None:
    a = ShapeNode(type="string")
    b = ShapeNode(type="number")
    merged = merge_shapes(a, b)
    assert merged.type == "mixed"


def test_merge_shapes_optional() -> None:
    a = infer_shape({"x": 1, "y": "test"})
    b = infer_shape({"x": 2})
    merged = merge_shapes(a, b)

    assert merged.properties["x"].type == "number"
    assert "y" in merged.optional_keys


def test_to_json_schema() -> None:
    shape = infer_shape({"name": "test", "age": 30})
    shape = shape.model_copy(update={"optional_keys": ["age"]})
    schema = to_json_schema(shape)

    assert schema["type"] == "object"
    assert schema["properties"]["name"]["type"] == "string"
    assert schema["required"] == ["name"]


def test_is_compatible() -> None:
    ref = infer_shape({"id": 1, "name": "x"})
    good = infer_shape({"id": 2, "name": "y", "extra": True})
    bad = infer_shape({"id": 3})

    assert is_compatible(good, ref)[0] is True
    comp, diffs = is_compatible(bad, ref)
    assert comp is False
    assert "missing keys: {'name'}" in diffs[0]
