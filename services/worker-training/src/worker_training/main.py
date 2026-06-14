from __future__ import annotations

import asyncio
import logging

from cvops_api.core.registry import registry
from cvops_worker_common import ConsumerLoop

from worker_training.steps.train import TrainStep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


def main() -> None:
    registry.register(TrainStep())
    loop = ConsumerLoop(
        stream="training",
        step_types=["step.train"],
    )
    asyncio.run(loop.run_forever())


if __name__ == "__main__":
    main()
