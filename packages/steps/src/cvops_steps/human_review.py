from cvops_api.engine.step import Step, StepContext, GateException

class HumanReviewStep(Step):
    type_key = "step.human_review"
    is_gate = True
    config_schema = {
        "type": "object",
        "properties": {
            "labeling_backend": {"type": "string", "default": "cvat"},
            "assignees": {"type": "array", "items": {"type": "string"}}
        }
    }

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        # Phase 2 — Yehuda
        # Push task to CVAT, insert labeling_job row, raise GateException
        raise NotImplementedError
