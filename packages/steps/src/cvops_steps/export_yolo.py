import json
from pathlib import Path
from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "export_yolo.json") as f:
    _SCHEMA = json.load(f)

class ExportYoloStep(Step):
    type_key = "step.export_yolo"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        # Phase 1: E7 — Nati/Yahav
        # inputs: {commit_id: str}
        # Returns: {export_blob_hash: str, commit_id: str}
        # Idempotent: same (commit_id, ontology_id) = same export hash
        raise NotImplementedError
