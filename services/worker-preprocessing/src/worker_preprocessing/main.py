import asyncio
import logging

from cvops_worker_common import ConsumerLoop
from cvops_steps import register_all

logging.basicConfig(level=logging.INFO)


def main() -> None:
    register_all()
    loop = ConsumerLoop(
        stream="preprocessing",
        step_types=["step.extract_frames", "step.commit_dataset"],
    )
    asyncio.run(loop.run_forever())


if __name__ == "__main__":
    main()
