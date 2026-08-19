import asyncio
import logging

from commerce_agent.config.settings import get_settings


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logging.getLogger(__name__).info("Worker placeholder started in %s", settings.environment)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run_worker())
