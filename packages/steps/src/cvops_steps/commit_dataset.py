import json
from pathlib import Path
from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "commit_dataset.json") as f:
    _SCHEMA = json.load(f)

class CommitDatasetStep(Step):
    type_key = "step.commit_dataset"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        # Phase 1: E6 — Yehuda
        # inputs: {sample_ids: list[str], annotation_revision_ids: list[str]}
        # Returns: {commit_id: str, ref_id: str}
        # Critical: CAS branch-head advance
        raise NotImplementedError
