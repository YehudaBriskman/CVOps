import json
from pathlib import Path
from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "extract_frames.json") as f:
    _SCHEMA = json.load(f)

class ExtractFramesStep(Step):
    type_key = "step.extract_frames"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        # Phase 1: E4 — Nati/Yahav
        # inputs: {source_id: str}
        # Returns: {sample_ids: list[str]}
        raise NotImplementedError
