"""Pure-logic tests for the pluggable split strategies.

split_strategies has no DB/S3 dependency — every strategy is a plain function
`assign(sample_ids, source_of, train_ratio, val_ratio, seed) -> {id: split}`.
These tests pin the two registered strategies' determinism, ratio honoring,
the by_source_group "whole source in one split" invariant, and edge cases.
"""

from __future__ import annotations

import uuid

import pytest

from cvops_steps.split_strategies import (
    SPLIT_STRATEGIES,
    by_source_group,
    get,
    random_seeded,
)

VALID_SPLITS = {"train", "val", "test"}


def _samples(n: int) -> list[str]:
    """n stable sample-id strings (stable across the test, unique per call)."""
    return [str(uuid.uuid4()) for _ in range(n)]


# --------------------------------------------------------------------------- #
# Registry surface                                                            #
# --------------------------------------------------------------------------- #


def test_both_strategies_registered() -> None:
    assert SPLIT_STRATEGIES["by_source_group"] is by_source_group
    assert SPLIT_STRATEGIES["random_seeded"] is random_seeded


def test_get_resolves_registered_keys() -> None:
    assert get("by_source_group") is by_source_group
    assert get("random_seeded") is random_seeded


def test_get_unknown_key_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown split_strategy"):
        get("does_not_exist")


# --------------------------------------------------------------------------- #
# random_seeded                                                               #
# --------------------------------------------------------------------------- #


def test_random_seeded_assigns_every_sample_a_valid_split() -> None:
    sample_ids = _samples(50)
    out = random_seeded(sample_ids, {}, 0.8, 0.1, 42)

    assert set(out) == set(sample_ids)
    assert all(split in VALID_SPLITS for split in out.values())


def test_random_seeded_is_deterministic_same_seed() -> None:
    sample_ids = _samples(40)
    a = random_seeded(sample_ids, {}, 0.7, 0.2, 123)
    b = random_seeded(sample_ids, {}, 0.7, 0.2, 123)
    assert a == b


def test_random_seeded_independent_of_input_order() -> None:
    """Per-item hashing means a sample's split never depends on its neighbours."""
    sample_ids = _samples(30)
    forward = random_seeded(sample_ids, {}, 0.7, 0.2, 9)
    reverse = random_seeded(list(reversed(sample_ids)), {}, 0.7, 0.2, 9)
    assert forward == reverse


def test_random_seeded_seed_changes_assignment() -> None:
    """Different seeds should generally produce a different partition."""
    sample_ids = _samples(200)
    a = random_seeded(sample_ids, {}, 0.7, 0.2, 1)
    b = random_seeded(sample_ids, {}, 0.7, 0.2, 2)
    assert a != b


def test_random_seeded_honors_ratios_approximately() -> None:
    """With many uniform-hash samples the split sizes track the ratios."""
    sample_ids = _samples(2000)
    train_ratio, val_ratio = 0.7, 0.2
    out = random_seeded(sample_ids, {}, train_ratio, val_ratio, 7)

    counts = {"train": 0, "val": 0, "test": 0}
    for split in out.values():
        counts[split] += 1
    n = len(sample_ids)

    # Hashing is uniform; 5% tolerance is comfortably wide for 2000 samples.
    assert abs(counts["train"] / n - train_ratio) < 0.05
    assert abs(counts["val"] / n - val_ratio) < 0.05
    assert abs(counts["test"] / n - (1 - train_ratio - val_ratio)) < 0.05


def test_random_seeded_all_train_when_train_ratio_one() -> None:
    sample_ids = _samples(100)
    out = random_seeded(sample_ids, {}, 1.0, 0.0, 5)
    assert set(out.values()) == {"train"}


def test_random_seeded_no_test_when_remainder_zero() -> None:
    """train + val == 1.0 → the test bucket is never reached."""
    sample_ids = _samples(300)
    out = random_seeded(sample_ids, {}, 0.6, 0.4, 11)
    assert "test" not in set(out.values())


# --------------------------------------------------------------------------- #
# by_source_group                                                             #
# --------------------------------------------------------------------------- #


def test_by_source_group_keeps_each_source_in_one_split() -> None:
    """The core invariant: all samples of a source land in the same split."""
    src_a, src_b, src_c = (str(uuid.uuid4()) for _ in range(3))
    sample_ids: list[str] = []
    source_of: dict[str, str] = {}
    for src in (src_a, src_b, src_c):
        for _ in range(10):
            sid = str(uuid.uuid4())
            sample_ids.append(sid)
            source_of[sid] = src

    out = by_source_group(sample_ids, source_of, 0.6, 0.2, 3)

    for src in (src_a, src_b, src_c):
        splits = {out[sid] for sid, s in source_of.items() if s == src}
        assert len(splits) == 1, f"source {src} spans splits {splits}"


def test_by_source_group_is_deterministic_same_seed() -> None:
    src = str(uuid.uuid4())
    sample_ids = _samples(20)
    source_of = {sid: src for sid in sample_ids}
    a = by_source_group(sample_ids, source_of, 0.7, 0.2, 99)
    b = by_source_group(sample_ids, source_of, 0.7, 0.2, 99)
    assert a == b


def test_by_source_group_split_depends_only_on_source_not_sample() -> None:
    """Two samples sharing a source get the same split regardless of their id."""
    src = str(uuid.uuid4())
    sample_ids = _samples(15)
    source_of = {sid: src for sid in sample_ids}
    out = by_source_group(sample_ids, source_of, 0.5, 0.3, 4)
    assert len(set(out.values())) == 1


def test_by_source_group_honors_ratios_across_many_sources() -> None:
    sources = [str(uuid.uuid4()) for _ in range(1000)]
    sample_ids: list[str] = []
    source_of: dict[str, str] = {}
    for src in sources:
        sid = str(uuid.uuid4())
        sample_ids.append(sid)
        source_of[sid] = src

    out = by_source_group(sample_ids, source_of, 0.7, 0.2, 13)
    counts = {"train": 0, "val": 0, "test": 0}
    for split in out.values():
        counts[split] += 1
    n = len(sample_ids)
    assert abs(counts["train"] / n - 0.7) < 0.06
    assert abs(counts["val"] / n - 0.2) < 0.06


# --------------------------------------------------------------------------- #
# Edge cases (both strategies)                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("strategy", [by_source_group, random_seeded])
def test_empty_sample_list_returns_empty_mapping(strategy) -> None:
    assert strategy([], {}, 0.8, 0.1, 0) == {}


def test_single_sample_random_seeded() -> None:
    sid = str(uuid.uuid4())
    out = random_seeded([sid], {}, 0.8, 0.1, 0)
    assert set(out) == {sid}
    assert out[sid] in VALID_SPLITS


def test_single_sample_by_source_group() -> None:
    sid, src = str(uuid.uuid4()), str(uuid.uuid4())
    out = by_source_group([sid], {sid: src}, 0.8, 0.1, 0)
    assert set(out) == {sid}
    assert out[sid] in VALID_SPLITS


@pytest.mark.parametrize("strategy", [by_source_group, random_seeded])
def test_zero_train_ratio_assigns_no_train(strategy) -> None:
    sample_ids = _samples(100)
    source_of = {sid: str(uuid.uuid4()) for sid in sample_ids}
    out = strategy(sample_ids, source_of, 0.0, 0.0, 7)
    assert set(out.values()) == {"test"}
