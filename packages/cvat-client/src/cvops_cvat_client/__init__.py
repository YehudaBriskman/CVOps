"""Shared CVAT client for the CVOps workers.

``geometry`` is pure and import-safe. ``client`` lazily imports ``cvat_sdk``, so
re-exporting its callables here does not require the SDK at import time (the
names resolve, the SDK is only touched when a function runs).
"""

from cvops_cvat_client.client import (
    ReviewImage,
    annotate,
    list_models,
    pull_review_task,
    push_review_task,
    register_webhook,
)
from cvops_cvat_client.geometry import cvat_rect_to_norm_bbox, norm_bbox_to_cvat_rect

__all__ = [
    "ReviewImage",
    "annotate",
    "cvat_rect_to_norm_bbox",
    "list_models",
    "norm_bbox_to_cvat_rect",
    "pull_review_task",
    "push_review_task",
    "register_webhook",
]
