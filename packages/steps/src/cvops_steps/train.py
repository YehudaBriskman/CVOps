import json
from pathlib import Path
from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "train.json") as f:
    _SCHEMA = json.load(f)

class TrainStep(Step):
    type_key = "step.train"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        # Phase 1: E8 — Nati/Yahav
        # inputs: {export_blob_hash: str}
        # Returns: {model_version_id: str}
        # Uses Docker Python SDK + ICD config from training_containers table
        raise NotImplementedError
