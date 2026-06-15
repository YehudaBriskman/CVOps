"""Wiring / message-routing tests for worker-cvat — no DB needed.

worker-cvat's contract with the shared ConsumerLoop:
  * it listens on the ``cvat`` stream for ``step.human_review`` run doorbells
    (push flow) and routes ``{kind: "cvat_sync"}`` webhook messages to the pull
    handler;
  * ConsumerLoop dispatches by message shape: a ``kind`` field → sync_handler,
    otherwise → the run handler;
  * the push step (cvops_steps.human_review) routes to the ``cvat`` queue and is
    a gate, which is what makes worker-cvat the right consumer for it.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ResponseError

from cvops_worker_common.consumer import ConsumerLoop


# ── main.py wiring contract ──────────────────────────────────────────────────


def test_stream_is_cvat():
    from worker_cvat.main import STREAM

    assert STREAM == "cvat"


def test_human_review_step_routes_to_cvat_queue_and_is_a_gate():
    # The push step's queue is why its run doorbells land on worker-cvat's stream.
    from cvops_steps.human_review import HumanReviewStep

    assert HumanReviewStep.queue == "cvat"
    assert HumanReviewStep.is_gate is True
    assert HumanReviewStep.type_key == "step.human_review"


def test_consumer_loop_built_with_sync_handler():
    from worker_cvat.sync import handle_cvat_sync

    loop = ConsumerLoop(
        stream="cvat",
        step_types=["step.human_review"],
        sync_handler=handle_cvat_sync,
    )
    assert loop.stream == "cvat"
    assert loop.step_types == ["step.human_review"]
    assert loop.sync_handler is handle_cvat_sync
    assert loop.group == "worker-cvat"


# ── ConsumerLoop dispatch by message shape ──────────────────────────────────


class _FakeRedis:
    """Yields one canned xreadgroup batch, then signals the loop to stop."""

    def __init__(self, loop: ConsumerLoop, messages):
        self._loop = loop
        self._batches = [[("cvat", messages)]]
        self.acked: list[str] = []

    async def xreadgroup(self, **kwargs):
        if self._batches:
            return self._batches.pop(0)
        self._loop.stop()  # nothing left → end the loop
        return []

    async def xack(self, stream, group, msg_id):
        self.acked.append(msg_id)


async def test_sync_message_routes_to_sync_handler():
    sync_handler = AsyncMock()
    run_handler = AsyncMock()
    loop = ConsumerLoop(
        stream="cvat",
        step_types=["step.human_review"],
        handler=run_handler,
        sync_handler=sync_handler,
    )
    fields = {"kind": "cvat_sync", "cvat_task_id": "777"}
    redis = _FakeRedis(loop, [("1-0", fields)])

    await loop._consume_loop(redis)

    sync_handler.assert_awaited_once_with(fields)
    run_handler.assert_not_awaited()
    assert redis.acked == ["1-0"]  # message acked after handling


async def test_run_doorbell_routes_to_run_handler():
    sync_handler = AsyncMock()
    run_handler = AsyncMock()
    loop = ConsumerLoop(
        stream="cvat",
        step_types=["step.human_review"],
        handler=run_handler,
        sync_handler=sync_handler,
    )
    fields = {"job_id": "job-abc", "step_type": "step.human_review"}
    redis = _FakeRedis(loop, [("2-0", fields)])

    await loop._consume_loop(redis)

    run_handler.assert_awaited_once_with("job-abc", "step.human_review")
    sync_handler.assert_not_awaited()
    assert redis.acked == ["2-0"]


async def test_handler_exception_still_acks():
    """A failing handler must not block the stream — the message is acked anyway
    (failures are recorded in PG, never auto-requeued)."""
    run_handler = AsyncMock(side_effect=RuntimeError("boom"))
    loop = ConsumerLoop(stream="cvat", step_types=["step.human_review"], handler=run_handler)
    redis = _FakeRedis(loop, [("3-0", {"job_id": "j", "step_type": "step.human_review"})])

    await loop._consume_loop(redis)

    run_handler.assert_awaited_once()
    assert redis.acked == ["3-0"]


async def test_sync_message_without_handler_is_dropped_but_acked():
    """A kind message with no sync_handler configured is logged + acked, not run
    through the run handler."""
    run_handler = AsyncMock()
    loop = ConsumerLoop(
        stream="cvat", step_types=["step.human_review"], handler=run_handler, sync_handler=None
    )
    redis = _FakeRedis(loop, [("4-0", {"kind": "cvat_sync", "cvat_task_id": "1"})])

    await loop._consume_loop(redis)

    run_handler.assert_not_awaited()
    assert redis.acked == ["4-0"]


# ── ConsumerLoop group setup ─────────────────────────────────────────────────


async def test_ensure_group_swallows_busygroup():
    loop = ConsumerLoop(stream="cvat", step_types=["step.human_review"])

    class _R:
        async def xgroup_create(self, *a, **k):
            raise ResponseError("BUSYGROUP Consumer Group name already exists")

    await loop._ensure_group(_R())  # must not raise


async def test_ensure_group_reraises_other_response_errors():
    loop = ConsumerLoop(stream="cvat", step_types=["step.human_review"])

    class _R:
        async def xgroup_create(self, *a, **k):
            raise ResponseError("ERR some other failure")

    with pytest.raises(ResponseError):
        await loop._ensure_group(_R())
