from __future__ import annotations

from typing import Any

from cvops_api.engine.step import Step, StepContext


class TrainStep(Step):
    type_key = "step.train"
    config_schema = {
        "type": "object",
        "properties": {
            "training_container_id": {"type": "string"},
            "git_url": {"type": "string"},
            "branch": {"type": "string"},
            "entry_point": {"type": "string"},
            "hyperparams": {"type": "object"},
            "commit_id": {"type": "string"},
        },
        "required": ["training_container_id", "git_url", "commit_id"],
    }

    async def run(
        self, ctx: StepContext, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError
