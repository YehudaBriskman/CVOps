"""Unit tests for the $-reference resolver (engine/ref_resolver.py).

Pure functions over plain dicts/lists — no DB, no Redis. Verifies the two
reference grammars ($steps.<id>.outputs.<name>, $run.params.<name>),
recursion into nested containers, non-string passthrough, and the exact
ResolutionError raised on each missing-target path.
"""

from __future__ import annotations

import pytest

from cvops_api.engine.ref_resolver import ResolutionError, resolve_refs


def test_resolves_step_output_ref() -> None:
    outputs = {"s1": {"frames": ["a", "b"]}}
    assert resolve_refs("$steps.s1.outputs.frames", outputs, {}) == ["a", "b"]


def test_resolves_run_param_ref() -> None:
    params = {"source_id": "src-123"}
    assert resolve_refs("$run.params.source_id", {}, params) == "src-123"


def test_output_name_may_contain_dots() -> None:
    # The output-name capture group is greedy (.+), so dotted names work.
    outputs = {"s1": {"a.b.c": 42}}
    assert resolve_refs("$steps.s1.outputs.a.b.c", outputs, {}) == 42


def test_param_name_may_contain_dots() -> None:
    params = {"nested.key": "v"}
    assert resolve_refs("$run.params.nested.key", {}, params) == "v"


def test_plain_string_passthrough() -> None:
    assert resolve_refs("just a string", {}, {}) == "just a string"


def test_dollar_string_that_is_not_a_ref_passes_through() -> None:
    # Starts with $ but matches neither grammar → returned verbatim.
    assert resolve_refs("$notaref", {}, {}) == "$notaref"
    assert resolve_refs("$steps.s1.frames", {}, {}) == "$steps.s1.frames"


@pytest.mark.parametrize("value", [42, 3.14, True, False, None])
def test_non_string_scalars_pass_through(value: object) -> None:
    assert resolve_refs(value, {}, {}) == value


def test_recurses_into_dict() -> None:
    outputs = {"s1": {"frames": "F"}}
    params = {"p": "P"}
    template = {
        "a": "$steps.s1.outputs.frames",
        "b": "$run.params.p",
        "c": "literal",
        "d": 7,
    }
    assert resolve_refs(template, outputs, params) == {
        "a": "F",
        "b": "P",
        "c": "literal",
        "d": 7,
    }


def test_recurses_into_list() -> None:
    outputs = {"s1": {"frames": "F"}}
    template = ["$steps.s1.outputs.frames", "literal", 9]
    assert resolve_refs(template, outputs, {}) == ["F", "literal", 9]


def test_recurses_into_deeply_nested_structure() -> None:
    outputs = {"s1": {"out": "VAL"}}
    params = {"name": "NM"}
    template = {
        "level1": {
            "list": [
                {"ref": "$steps.s1.outputs.out"},
                ["$run.params.name", "plain"],
            ]
        }
    }
    assert resolve_refs(template, outputs, params) == {
        "level1": {"list": [{"ref": "VAL"}, ["NM", "plain"]]}
    }


def test_empty_containers_pass_through() -> None:
    assert resolve_refs({}, {}, {}) == {}
    assert resolve_refs([], {}, {}) == []


# ── Error paths: exact exception class + message fragments ──────────────────


def test_missing_step_raises_resolution_error() -> None:
    with pytest.raises(ResolutionError) as exc:
        resolve_refs("$steps.missing.outputs.frames", {}, {})
    assert "Step 'missing' has no recorded outputs" in str(exc.value)


def test_missing_output_name_raises_resolution_error() -> None:
    outputs = {"s1": {"other": 1}}
    with pytest.raises(ResolutionError) as exc:
        resolve_refs("$steps.s1.outputs.frames", outputs, {})
    assert "Step 's1' output 'frames' not found" in str(exc.value)


def test_missing_run_param_raises_resolution_error() -> None:
    with pytest.raises(ResolutionError) as exc:
        resolve_refs("$run.params.source_id", {}, {})
    assert "Run param 'source_id' not found" in str(exc.value)


def test_error_propagates_from_nested_position() -> None:
    template = {"deep": ["$run.params.nope"]}
    with pytest.raises(ResolutionError):
        resolve_refs(template, {}, {})
