"""Unit tests for the pluggable split strategies (commit_dataset).

These are pure functions — no DB, no StepContext — so they're tested directly.
The contract that matters: determinism (a commit must be reproducible) and the
source-group invariant (all frames of one clip land in one split).
"""

from __future__ import annotations

import uuid

import pytest

from cvops_steps import split_strategies
from cvops_steps.split_strategies import (
    SPLIT_STRATEGIES,
    _bucket,
    _unit_hash,
    by_source_group,
    get,
    random_seeded,
)


# ── registry get() ───────────────────────────────────────────────────────────


def test_registry_has_both_strategies():
    assert set(SPLIT_STRATEGIES) == {"by_source_group", "random_seeded"}


def test_get_returns_callable():
    assert get("by_source_group") is by_source_group
    assert get("random_seeded") is random_seeded


def test_get_unknown_raises_value_error_listing_known():
    with pytest.raises(ValueError, match="unknown split_strategy 'nope'"):
        get("nope")
    # The error lists what IS registered, to aid the caller.
    with pytest.raises(ValueError, match="by_source_group"):
        get("nope")


# ── _unit_hash / _bucket primitives ──────────────────────────────────────────


def test_unit_hash_is_in_unit_interval_and_stable():
    u = _unit_hash("seed", "abc")
    assert 0.0 <= u < 1.0
    assert _unit_hash("seed", "abc") == u  # deterministic


def test_unit_hash_differs_by_input():
    assert _unit_hash("1", "abc") != _unit_hash("2", "abc")
    assert _unit_hash("1", "abc") != _unit_hash("1", "abd")


def test_bucket_boundaries():
    # train_ratio=0.8, val_ratio=0.2 → test gets the remainder (0 width here).
    assert _bucket(0.0, 0.8, 0.2) == "train"
    assert _bucket(0.79, 0.8, 0.2) == "train"
    assert _bucket(0.8, 0.8, 0.2) == "val"  # boundary is exclusive on train
    assert _bucket(0.99, 0.8, 0.2) == "val"


def test_bucket_assigns_test_remainder():
    assert _bucket(0.95, 0.7, 0.2) == "test"  # 0.9..1.0 is test


# ── by_source_group ──────────────────────────────────────────────────────────


def _samples(n: int) -> list[str]:
    return [str(uuid.uuid4()) for _ in range(n)]


def test_by_source_group_keeps_a_source_in_one_split():
    sids = _samples(20)
    # All from the SAME source → must all share a split.
    src = "source-A"
    source_of = {s: src for s in sids}
    result = by_source_group(sids, source_of, 0.8, 0.2, seed=42)
    assert len(set(result.values())) == 1


def test_by_source_group_two_sources_may_differ_but_each_is_uniform():
    sids_a = _samples(10)
    sids_b = _samples(10)
    source_of = {s: "A" for s in sids_a} | {s: "B" for s in sids_b}
    result = by_source_group(sids_a + sids_b, source_of, 0.8, 0.2, seed=7)
    splits_a = {result[s] for s in sids_a}
    splits_b = {result[s] for s in sids_b}
    assert len(splits_a) == 1
    assert len(splits_b) == 1


def test_by_source_group_is_deterministic():
    sids = _samples(15)
    source_of = {s: f"src-{i % 3}" for i, s in enumerate(sids)}
    r1 = by_source_group(sids, source_of, 0.7, 0.2, seed=99)
    r2 = by_source_group(sids, source_of, 0.7, 0.2, seed=99)
    assert r1 == r2


def test_by_source_group_seed_changes_assignment():
    # Enough distinct sources that at least one moves between seeds.
    sids = _samples(30)
    source_of = {s: f"src-{i}" for i, s in enumerate(sids)}
    r1 = by_source_group(sids, source_of, 0.6, 0.2, seed=1)
    r2 = by_source_group(sids, source_of, 0.6, 0.2, seed=2)
    assert r1 != r2


# ── random_seeded ────────────────────────────────────────────────────────────


def test_random_seeded_is_deterministic():
    sids = _samples(50)
    source_of = {s: "ignored" for s in sids}
    r1 = random_seeded(sids, source_of, 0.8, 0.2, seed=5)
    r2 = random_seeded(sids, source_of, 0.8, 0.2, seed=5)
    assert r1 == r2


def test_random_seeded_ignores_source():
    sids = _samples(20)
    # Same samples + seed but different source mapping → identical (source unused).
    r_a = random_seeded(sids, {s: "A" for s in sids}, 0.8, 0.2, seed=3)
    r_b = random_seeded(sids, {s: "B" for s in sids}, 0.8, 0.2, seed=3)
    assert r_a == r_b


def test_random_seeded_roughly_respects_ratios():
    sids = _samples(2000)
    source_of = {s: "x" for s in sids}
    result = random_seeded(sids, source_of, 0.8, 0.1, seed=11)
    counts = {"train": 0, "val": 0, "test": 0}
    for split in result.values():
        counts[split] += 1
    n = len(sids)
    # Hashing is uniform; allow generous tolerance for a finite sample.
    assert abs(counts["train"] / n - 0.8) < 0.05
    assert abs(counts["val"] / n - 0.1) < 0.05
    assert abs(counts["test"] / n - 0.1) < 0.05


def test_random_seeded_seed_changes_assignment():
    sids = _samples(100)
    source_of = {s: "x" for s in sids}
    r1 = random_seeded(sids, source_of, 0.5, 0.25, seed=1)
    r2 = random_seeded(sids, source_of, 0.5, 0.25, seed=2)
    assert r1 != r2


def test_register_decorator_adds_to_registry():
    @split_strategies.register("_tmp_test_strategy")
    def _strat(sample_ids, source_of, tr, vr, seed):
        return {s: "train" for s in sample_ids}

    try:
        assert get("_tmp_test_strategy") is _strat
    finally:
        SPLIT_STRATEGIES.pop("_tmp_test_strategy", None)
