"""step.deploy_model — download model weights from storage and deploy to CVAT via Nuclio."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from cvops_api.db.models.models import ModelVersion
from cvops_api.engine.step import Step, StepContext

from worker_cvat import deployer


class DeployModelStep(Step):
    type_key = "step.deploy_model"
    queue    = "cvat"
    config_schema = {
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string",
                "description": "Display name for the Nuclio function in CVAT",
            },
        },
        "required": ["model_name"],
    }

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        model_version_id: str = inputs["model_version_id"]
        model_name: str       = config["model_name"]

        result = await ctx.session.execute(
            select(ModelVersion).where(ModelVersion.id == UUID(model_version_id))
        )
        mv = result.scalar_one_or_none()
        if mv is None:
            raise RuntimeError(f"ModelVersion {model_version_id!r} not found")

        weights_bytes = await ctx.storage.get_bytes(mv.blob_hash)

        loop = asyncio.get_running_loop()
        with tempfile.TemporaryDirectory() as tmp:
            pt_path = Path(tmp) / "model.pt"
            pt_path.write_bytes(weights_bytes)
            function_name = await loop.run_in_executor(
                None, deployer.deploy, pt_path, model_name
            )

        return {"function_name": function_name, "function_id": function_name}
