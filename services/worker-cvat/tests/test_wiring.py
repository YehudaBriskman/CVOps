"""Wiring / message-routing tests for worker-cvat — no DB needed.

worker-cvat consumes the ``cvat`` Redis stream via its own consumer-group loop
(``worker.py``), mirroring worker-preprocessing. Two doorbell kinds arrive:
  * run doorbells ``{job_id, step_type}`` — normal step execution; covers
    ``step.human_review`` (push flow, parks at the gate) and ``step.deploy_model``;
  * ``{kind: "cvat_sync", cvat_task_id}`` — the webhook bridge signalling a CVAT
    task is done; routed to the pull handler which resumes the gate.

The generic ConsumerLoop dispatch contract is covered in
``services/api/tests/worker_common/test_consumer.py``; here we assert only the
worker-cvat-specific wiring.
"""

from __future__ import annotations

from worker_cvat import worker


def test_stream_is_cvat():
    assert worker.STREAM == "cvat"


def test_sync_handler_is_wired_into_worker():
    # worker.py folds the CVAT pull handler in alongside run-doorbell handling.
    from worker_cvat.sync import handle_cvat_sync

    assert worker.handle_cvat_sync is handle_cvat_sync


def test_human_review_step_routes_to_cvat_queue_and_is_a_gate():
    # The push step's queue is why its run doorbells land on worker-cvat's stream.
    from cvops_steps.human_review import HumanReviewStep

    assert HumanReviewStep.queue == "cvat"
    assert HumanReviewStep.is_gate is True
    assert HumanReviewStep.type_key == "step.human_review"


def test_deploy_model_step_routes_to_cvat_queue():
    # DeployModelStep is registered locally by worker-cvat; same stream as review.
    from worker_cvat.deploy_step import DeployModelStep

    assert DeployModelStep.queue == "cvat"
    assert DeployModelStep.type_key == "step.deploy_model"
