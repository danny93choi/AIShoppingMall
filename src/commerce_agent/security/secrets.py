from typing import Protocol

from pydantic import SecretStr


class SecretStore(Protocol):
    async def put(self, reference: str, value: SecretStr) -> None: ...

    async def get(self, reference: str) -> SecretStr: ...


class InMemorySecretStore(SecretStore):
    """Development/test store. Production must inject a KMS-backed implementation."""

    def __init__(self) -> None:
        self._values: dict[str, SecretStr] = {}

    async def put(self, reference: str, value: SecretStr) -> None:
        self._values[reference] = value

    async def get(self, reference: str) -> SecretStr:
        try:
            return self._values[reference]
        except KeyError as error:
            raise KeyError("secret reference not found") from error
