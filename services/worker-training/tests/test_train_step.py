import pytest
from worker_training.steps.train import TrainStep


@pytest.mark.asyncio
async def test_train_step_raises_not_implemented(ctx, base_config, base_inputs):
    step = TrainStep()
    with pytest.raises(NotImplementedError):
        await step.run(ctx, base_config, base_inputs)
