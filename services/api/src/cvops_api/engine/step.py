"""
Step contract — the interface every workflow step implements.
Core is stable; steps grow freely as plugins.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from cvops_api.core.storage import StorageBackend


@dataclass
class StepContext:
    """Injected into every step.run() call by the executor."""

    session: "AsyncSession"
    storage: "StorageBackend"
    project_id: str
    run_id: str  # UUID of the step's own runs row
    actor_id: str  # UUID of the user who started the workflow run
    emit_event: Callable[..., Any] = field(repr=False)  # bound audit.emit_event


class GateException(Exception):
    """
    Raised by gate steps (e.g. human_review) to park the workflow
    run in the 'waiting' state until an external condition is met.
    gate_data is persisted in runs.output_refs for resume.
    """

    def __init__(self, gate_data: dict[str, Any]) -> None:
        super().__init__("gate")
        self.gate_data = gate_data


class Step(ABC):
    """
    Base class for all workflow step implementations.

    Subclasses MUST set type_key and config_schema, and implement run().
    They MUST NOT import from cvops_api.routers or cvops_api.db.models
    directly — only from cvops_api.core (storage, registry, audit).
    """

    # Override in every subclass
    type_key: str = ""
    config_schema: dict[str, Any] = {}
    is_gate: bool = False
    # Redis Stream this step is dispatched to. Empty → coordinator's default
    # ("preprocessing"). Steps that need a domain-specific worker (e.g. CVAT
    # gates → "labeling", training → "training") override this.
    queue: str = ""

    @abstractmethod
    async def run(
        self,
        ctx: StepContext,
        config: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute this step.
        - inputs: artifact references resolved from prior step outputs.
        - Returns: artifact references to be stored in runs.output_refs.
        - May raise GateException to park the workflow.
        - Must be idempotent when called with the same idempotency_key result.
        """

    def idempotency_key(self, config: dict[str, Any], inputs: dict[str, Any]) -> str:
        """
        Stable key for deduplication: same type + config + inputs = same output.
        The executor reuses existing outputs when this key matches a succeeded run.
        """
        payload = json.dumps(
            {"type": self.type_key, "config": config, "inputs": inputs},
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(payload).hexdigest()
