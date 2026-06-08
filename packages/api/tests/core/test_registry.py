"""
Tests for cvops_api.core.registry.Registry and the module-level `registry` singleton.

Registry is a synchronous, in-memory data structure. These tests do NOT use the
async `session` fixture and are NOT async — plain sync pytest functions throughout.
"""
from __future__ import annotations

import pytest
import jsonschema

from cvops_api.core.registry import Registry
from cvops_api.engine.step import Step, StepContext


# ---------------------------------------------------------------------------
# Minimal concrete Step implementation used across all tests
# ---------------------------------------------------------------------------

class MockStep(Step):
    type_key = "test.mock"
    config_schema = {
        "type": "object",
        "properties": {
            "threshold": {"type": "number"},
        },
        "required": ["threshold"],
    }
    category = "step"

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:  # type: ignore[override]
        return {}


class AnotherMockStep(Step):
    """Second step with same category, used for list_by_category tests."""
    type_key = "test.another"
    config_schema = {
        "type": "object",
        "properties": {
            "epochs": {"type": "integer"},
        },
        "required": ["epochs"],
    }
    category = "step"

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:  # type: ignore[override]
        return {}


class OtherCategoryStep(Step):
    """Step in a different category to verify list_by_category filtering."""
    type_key = "test.other_category"
    config_schema = {"type": "object"}
    category = "gate"

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:  # type: ignore[override]
        return {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_and_resolve() -> None:
    """Registering a step and resolving it by type_key should return the same step."""
    reg = Registry()
    step = MockStep()

    reg.register(step)
    registration = reg.resolve("test.mock")

    assert registration.type_key == "test.mock"
    assert registration.impl is step


def test_resolve_unknown_raises_key_error() -> None:
    """Resolving a type_key that was never registered must raise KeyError."""
    reg = Registry()

    with pytest.raises(KeyError):
        reg.resolve("does.not.exist")


def test_list_by_category() -> None:
    """list_by_category should return all registrations matching the given category."""
    reg = Registry()
    reg.register(MockStep())
    reg.register(AnotherMockStep())
    reg.register(OtherCategoryStep())

    results = reg.list_by_category("step")

    type_keys = {r.type_key for r in results}
    assert "test.mock" in type_keys
    assert "test.another" in type_keys
    # The gate category step must NOT appear in "step" results
    assert "test.other_category" not in type_keys


def test_list_by_category_empty() -> None:
    """list_by_category on a category with no registrations should return an empty list."""
    reg = Registry()
    reg.register(MockStep())

    results = reg.list_by_category("nonexistent")

    assert results == []


def test_validate_config_valid() -> None:
    """validate_config should raise nothing when the config satisfies the JSON schema."""
    reg = Registry()
    reg.register(MockStep())

    # Should not raise
    reg.validate_config("test.mock", {"threshold": 0.5})


def test_validate_config_invalid_raises() -> None:
    """validate_config should raise jsonschema.ValidationError when a required field is absent."""
    reg = Registry()
    reg.register(MockStep())

    with pytest.raises(jsonschema.ValidationError):
        # "threshold" is required but omitted
        reg.validate_config("test.mock", {})
