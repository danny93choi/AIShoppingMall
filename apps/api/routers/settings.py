from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.services.credential_settings import (
    PROVIDER_SPECS,
    CredentialCipher,
    CredentialConfigurationError,
    save_tenant_credential,
)
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.config.settings import get_settings
from commerce_agent.infrastructure.db.models import AuditEventModel, TenantCredentialModel
from commerce_agent.security.rbac import Permission, require_permission

router = APIRouter(prefix="/api/v1/admin/settings", tags=["admin-settings"])


class CredentialUpdate(BaseModel):
    values: dict[str, str | bool | None] = Field(default_factory=dict)


class ProviderModelError(RuntimeError):
    pass


def _provider_error(provider: str, response: httpx.Response) -> ProviderModelError:
    message = "공급자 인증 또는 권한을 확인하세요."
    try:
        payload = response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if isinstance(error, dict) and error.get("message"):
            message = str(error["message"])
    except ValueError:
        pass
    return ProviderModelError(f"{provider} API 오류 ({response.status_code}): {message}")


def _cipher() -> CredentialCipher:
    try:
        return CredentialCipher(get_settings().settings_master_key)
    except CredentialConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _payload(model: TenantCredentialModel) -> dict[str, Any]:
    return {
        "provider": model.provider,
        "configured": True,
        "values": model.masked_json,
        "status": model.status,
        "last_tested_at": model.last_tested_at,
        "last_error": model.last_error,
        "updated_at": model.updated_at,
    }


async def _fetch_models(provider: str, values: dict[str, Any]) -> list[str]:
    async with httpx.AsyncClient(timeout=10) as client:
        if provider == "anthropic":
            response = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": str(values["api_key"]),
                    "anthropic-version": "2023-06-01",
                },
            )
        elif provider == "gemini":
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": str(values["api_key"])},
            )
        else:
            base_url = (
                "https://api.openai.com/v1"
                if provider == "openai"
                else str(values["base_url"]).rstrip("/")
            )
            response = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {values['api_key']}"},
            )
        if response.is_error:
            raise _provider_error(provider, response)
    payload = response.json()
    if not isinstance(payload, dict):
        return []
    if provider == "gemini":
        return sorted(
            {
                str(item["name"]).removeprefix("models/")
                for item in payload.get("models", [])
                if isinstance(item, dict)
                and item.get("name")
                and "generateContent" in item.get("supportedGenerationMethods", [])
            }
        )[:500]
    models = payload.get("data", [])
    return sorted(
        {str(item["id"]) for item in models if isinstance(item, dict) and item.get("id")}
    )[:500]


@router.get("")
async def list_settings(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.MANAGE_SECURITY)
    models = list(
        (
            await session.scalars(
                select(TenantCredentialModel)
                .where(TenantCredentialModel.tenant_id == context.tenant_id)
                .order_by(TenantCredentialModel.provider)
            )
        ).all()
    )
    by_provider = {model.provider: _payload(model) for model in models}
    return {
        "encryption_ready": get_settings().settings_master_key is not None,
        "providers": [
            by_provider.get(
                provider,
                {
                    "provider": provider,
                    "configured": False,
                    "values": {},
                    "status": "not_configured",
                    "last_tested_at": None,
                    "last_error": None,
                },
            )
            for provider in PROVIDER_SPECS
        ],
    }


@router.put("/{provider}")
async def update_setting(
    provider: str,
    body: CredentialUpdate,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.MANAGE_SECURITY)
    try:
        model = await save_tenant_credential(
            session,
            tenant_id=context.tenant_id,
            provider=provider,
            values=body.values,
            cipher=_cipher(),
        )
    except CredentialConfigurationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    now = datetime.now(UTC)
    session.add(
        AuditEventModel(
            tenant_id=context.tenant_id,
            event_type="credential.updated",
            resource_type="credential",
            resource_id=model.id,
            actor_id=context.actor_id,
            payload_json={"provider": provider, "fields": sorted(body.values)},
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    return _payload(model)


@router.delete("/{provider}", status_code=204)
async def delete_setting(
    provider: str,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    require_permission(context, Permission.MANAGE_SECURITY)
    model = await session.scalar(
        select(TenantCredentialModel).where(
            TenantCredentialModel.tenant_id == context.tenant_id,
            TenantCredentialModel.provider == provider,
        )
    )
    if model is None:
        raise HTTPException(status_code=404, detail="credential not found")
    now = datetime.now(UTC)
    session.add(
        AuditEventModel(
            tenant_id=context.tenant_id,
            event_type="credential.deleted",
            resource_type="credential",
            resource_id=model.id,
            actor_id=context.actor_id,
            payload_json={"provider": provider},
            created_at=now,
            updated_at=now,
        )
    )
    await session.execute(
        delete(TenantCredentialModel).where(
            TenantCredentialModel.tenant_id == context.tenant_id,
            TenantCredentialModel.provider == provider,
        )
    )


@router.post("/{provider}/test")
async def test_setting(
    provider: str,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.MANAGE_SECURITY)
    model = await session.scalar(
        select(TenantCredentialModel).where(
            TenantCredentialModel.tenant_id == context.tenant_id,
            TenantCredentialModel.provider == provider,
        )
    )
    if model is None:
        raise HTTPException(status_code=404, detail="credential not found")
    values = _cipher().decrypt(model.encrypted_payload)
    now = datetime.now(UTC)
    try:
        if provider in {"openai", "anthropic", "gemini", "gateway"}:
            models = await _fetch_models(provider, values)
            message = f"모델 API 연결 성공 · {len(models)}개 모델 확인"
        else:
            message = "자격증명 형식 확인 완료 · 실제 연결은 시장조사 실행 시 검증됩니다."
        model.status = "active"
        model.last_error = None
    except Exception as error:
        model.status = "failed"
        model.last_error = f"{type(error).__name__}: 연결에 실패했습니다."
        model.last_tested_at = now
        model.updated_at = now
        await session.flush()
        raise HTTPException(status_code=502, detail=model.last_error) from error
    model.last_tested_at = now
    model.updated_at = now
    await session.flush()
    return {"provider": provider, "status": model.status, "message": message}


@router.get("/{provider}/models")
async def list_provider_models(
    provider: str,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.MANAGE_SECURITY)
    if provider not in {"openai", "anthropic", "gemini", "gateway"}:
        raise HTTPException(status_code=422, detail="이 공급자는 모델 목록을 제공하지 않습니다.")
    model = await session.scalar(
        select(TenantCredentialModel).where(
            TenantCredentialModel.tenant_id == context.tenant_id,
            TenantCredentialModel.provider == provider,
        )
    )
    if model is None:
        raise HTTPException(status_code=404, detail="먼저 공급자 설정을 저장하세요.")
    try:
        models = await _fetch_models(provider, _cipher().decrypt(model.encrypted_payload))
    except ProviderModelError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail=f"{provider} API에 연결하지 못했습니다. 네트워크 상태를 확인하세요.",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"{provider} 모델 목록 응답을 처리하지 못했습니다.",
        ) from error
    return {"provider": provider, "models": models}
