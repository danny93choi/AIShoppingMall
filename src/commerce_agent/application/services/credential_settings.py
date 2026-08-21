import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.config.settings import Settings
from commerce_agent.infrastructure.db.models import TenantCredentialModel


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    secret_fields: frozenset[str]
    config_fields: frozenset[str]

    @property
    def fields(self) -> frozenset[str]:
        return self.secret_fields | self.config_fields


PROVIDER_SPECS = {
    "openai": ProviderSpec(frozenset({"api_key"}), frozenset({"model", "active"})),
    "anthropic": ProviderSpec(frozenset({"api_key"}), frozenset({"model", "active"})),
    "gemini": ProviderSpec(frozenset({"api_key"}), frozenset({"model", "active"})),
    "gateway": ProviderSpec(
        frozenset({"api_key"}),
        frozenset({"base_url", "model", "active", "fallback_provider"}),
    ),
    "naver_api_hub": ProviderSpec(
        frozenset({"client_id", "client_secret"}), frozenset({"base_url"})
    ),
    "naver_search": ProviderSpec(
        frozenset({"client_id", "client_secret"}), frozenset({"base_url"})
    ),
    "naver_search_ad": ProviderSpec(
        frozenset({"api_key", "secret_key", "customer_id"}), frozenset({"base_url"})
    ),
}


class CredentialConfigurationError(ValueError):
    pass


class CredentialCipher:
    def __init__(self, master_key: SecretStr | None) -> None:
        if master_key is None or len(master_key.get_secret_value()) < 32:
            raise CredentialConfigurationError(
                "SETTINGS_MASTER_KEY must contain at least 32 characters"
            )
        derived = sha256(master_key.get_secret_value().encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(derived))

    def encrypt(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        return self._fernet.encrypt(serialized).decode()

    def decrypt(self, token: str) -> dict[str, Any]:
        try:
            value = json.loads(self._fernet.decrypt(token.encode()))
        except (InvalidToken, json.JSONDecodeError) as error:
            raise CredentialConfigurationError("stored credential cannot be decrypted") from error
        if not isinstance(value, dict):
            raise CredentialConfigurationError("stored credential payload is invalid")
        return value


def _masked_payload(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    spec = PROVIDER_SPECS[provider]
    masked: dict[str, Any] = {}
    for key in spec.config_fields:
        if key in payload:
            masked[key] = payload[key]
    for key in spec.secret_fields:
        value = str(payload.get(key, ""))
        masked[key] = f"••••{value[-4:]}" if value else None
    return masked


async def save_tenant_credential(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider: str,
    values: dict[str, Any],
    cipher: CredentialCipher,
) -> TenantCredentialModel:
    spec = PROVIDER_SPECS.get(provider)
    if spec is None:
        raise CredentialConfigurationError(f"unsupported provider: {provider}")
    unknown = set(values) - spec.fields
    if unknown:
        raise CredentialConfigurationError(f"unsupported fields: {', '.join(sorted(unknown))}")
    model = await session.scalar(
        select(TenantCredentialModel).where(
            TenantCredentialModel.tenant_id == tenant_id,
            TenantCredentialModel.provider == provider,
        )
    )
    existing = cipher.decrypt(model.encrypted_payload) if model is not None else {}
    supplied = {key: value for key, value in values.items() if value not in (None, "")}
    merged = {**existing, **supplied}
    missing = [key for key in spec.secret_fields if not merged.get(key)]
    if missing:
        raise CredentialConfigurationError(
            f"required credential fields are missing: {', '.join(sorted(missing))}"
        )
    if provider in {"openai", "anthropic", "gemini", "gateway"} and values.get("active"):
        other_models = list(
            (
                await session.scalars(
                    select(TenantCredentialModel).where(
                        TenantCredentialModel.tenant_id == tenant_id,
                        TenantCredentialModel.provider != provider,
                        TenantCredentialModel.provider.in_(
                            ["openai", "anthropic", "gemini", "gateway"]
                        ),
                    )
                )
            ).all()
        )
        for other in other_models:
            other_payload = cipher.decrypt(other.encrypted_payload)
            other_payload["active"] = False
            other.encrypted_payload = cipher.encrypt(other_payload)
            other.masked_json = _masked_payload(other.provider, other_payload)
            other.updated_at = datetime.now(UTC)
    now = datetime.now(UTC)
    if model is None:
        model = TenantCredentialModel(
            tenant_id=tenant_id,
            provider=provider,
            encrypted_payload=cipher.encrypt(merged),
            masked_json=_masked_payload(provider, merged),
            status="configured",
            last_tested_at=None,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        session.add(model)
    else:
        model.encrypted_payload = cipher.encrypt(merged)
        model.masked_json = _masked_payload(provider, merged)
        model.status = "configured"
        model.last_error = None
        model.updated_at = now
    await session.flush()
    return model


async def tenant_credential_payloads(
    session: AsyncSession, tenant_id: UUID, cipher: CredentialCipher
) -> dict[str, dict[str, Any]]:
    models = list(
        (
            await session.scalars(
                select(TenantCredentialModel).where(TenantCredentialModel.tenant_id == tenant_id)
            )
        ).all()
    )
    return {model.provider: cipher.decrypt(model.encrypted_payload) for model in models}


async def effective_tenant_settings(
    session: AsyncSession, *, tenant_id: UUID, base: Settings
) -> Settings:
    if base.settings_master_key is None:
        return base
    credentials = await tenant_credential_payloads(
        session, tenant_id, CredentialCipher(base.settings_master_key)
    )
    updates: dict[str, Any] = {}
    openai = credentials.get("openai")
    anthropic = credentials.get("anthropic")
    gemini = credentials.get("gemini")
    gateway = credentials.get("gateway")
    active_provider = next(
        (
            name
            for name, payload in (
                ("gemini", gemini),
                ("anthropic", anthropic),
                ("openai", openai),
                ("gateway", gateway),
            )
            if payload and payload.get("active")
        ),
        base.llm_provider,
    )
    if openai:
        updates["openai_api_key"] = openai["api_key"]
    if anthropic:
        updates["anthropic_api_key"] = SecretStr(anthropic["api_key"])
    if gemini:
        updates["gemini_api_key"] = SecretStr(gemini["api_key"])
    if gateway:
        updates["llm_gateway_base_url"] = gateway.get("base_url")
        updates["llm_gateway_api_key"] = SecretStr(gateway["api_key"])
    selected = credentials.get(active_provider) or {}
    updates.update(
        {
            "llm_provider": active_provider,
            "llm_default_model": selected.get("model", base.llm_default_model),
            "llm_fallback_provider": selected.get("fallback_provider", base.llm_fallback_provider),
        }
    )
    naver_hub = credentials.get("naver_api_hub")
    if naver_hub:
        updates.update(
            {
                "naver_api_hub_client_id": SecretStr(naver_hub["client_id"]),
                "naver_api_hub_client_secret": SecretStr(naver_hub["client_secret"]),
                "naver_api_hub_base_url": naver_hub.get("base_url", base.naver_api_hub_base_url),
            }
        )
    naver_search = credentials.get("naver_search")
    if naver_search:
        updates.update(
            {
                "naver_search_client_id": SecretStr(naver_search["client_id"]),
                "naver_search_client_secret": SecretStr(naver_search["client_secret"]),
                "naver_search_base_url": naver_search.get("base_url", base.naver_search_base_url),
            }
        )
    search_ad = credentials.get("naver_search_ad")
    if search_ad:
        updates.update(
            {
                "naver_search_ad_api_key": SecretStr(search_ad["api_key"]),
                "naver_search_ad_secret_key": SecretStr(search_ad["secret_key"]),
                "naver_search_ad_customer_id": search_ad["customer_id"],
                "naver_search_ad_base_url": search_ad.get(
                    "base_url", base.naver_search_ad_base_url
                ),
            }
        )
    return base.model_copy(update=updates)
