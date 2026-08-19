from typing import Protocol


class HealthChecker(Protocol):
    async def check(self) -> bool: ...

    async def close(self) -> None: ...
