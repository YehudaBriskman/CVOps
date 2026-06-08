import json
from pathlib import Path
from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "auto_label.json") as f:
    _SCHEMA = json.load(f)

class AutoLabelStep(Step):
    type_key = "step.auto_label"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        # Phase 1: E5 — Nati/Yahav
        # inputs: {sample_ids: list[str]}
        # Returns: {annotation_revision_ids: list[str]}
        raise NotImplementedError
