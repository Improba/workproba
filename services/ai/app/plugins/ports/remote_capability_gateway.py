"""RemoteCapabilityGateway — appels plugins distants (scaffold V3)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import httpx

from app.audit import log_event, resolve_app_data_dir

REMOTE_CAPABILITY_PERMISSION = "capability:remote"
DEFAULT_REMOTE_TIMEOUT_SECONDS = 30.0

JsonDict = dict[str, Any]

_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "conversations",
        "conversation",
        "messages",
        "chat_history",
        "local_files",
        "files",
        "attachments",
        "memory_items",
        "workspace_data_dir",
        "project_path",
        "project_root",
        "workspace_root",
    }
)

_REMOTE_AUDIT_LOG: list[JsonDict] = []


class RemoteCapabilityRejected(Exception):
    """Appel distant refusé (stub, permission ou politique de minimisation)."""


def remote_capability_audit_log() -> list[JsonDict]:
    return list(_REMOTE_AUDIT_LOG)


def clear_remote_capability_audit_log() -> None:
    _REMOTE_AUDIT_LOG.clear()


@dataclass(frozen=True)
class IdentityDelegation:
    """Jetons et contexte d'identité transmis au plugin distant (jamais de fichiers locaux)."""

    subject_id: str
    org_id: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    access_token: str | None = None


def minimize_remote_payload(payload: JsonDict) -> JsonDict:
    """Retire les champs sensibles ou hors périmètre avant envoi distant."""
    minimized: JsonDict = {}
    for key, value in payload.items():
        if key in _FORBIDDEN_PAYLOAD_KEYS:
            continue
        if isinstance(value, dict):
            nested = minimize_remote_payload(value)
            if nested:
                minimized[key] = nested
            continue
        if isinstance(value, list):
            cleaned_list: list[Any] = []
            for item in value:
                if isinstance(item, dict):
                    nested_item = minimize_remote_payload(item)
                    if nested_item:
                        cleaned_list.append(nested_item)
                elif not (
                    key in {"conversation", "conversations"} and isinstance(item, str)
                ):
                    cleaned_list.append(item)
            if cleaned_list:
                minimized[key] = cleaned_list
            continue
        minimized[key] = value
    return minimized


@runtime_checkable
class RemoteCapabilityGateway(Protocol):
    async def invoke_remote(
        self,
        capability_id: str,
        payload: JsonDict,
        identity_delegation: IdentityDelegation,
    ) -> JsonDict: ...


class LocalRemoteCapabilityGateway:
    """Stub local : rejette par défaut, journalise chaque tentative."""

    def __init__(
        self,
        *,
        caller_plugin_id: str,
        app_data_dir: Any,
        allowed_capability_ids: frozenset[str] | None = None,
        timeout_seconds: float = DEFAULT_REMOTE_TIMEOUT_SECONDS,
    ) -> None:
        self._caller_plugin_id = caller_plugin_id
        self._app_data_dir = app_data_dir
        self._allowed_capability_ids = allowed_capability_ids or frozenset()
        self._timeout_seconds = timeout_seconds

    def _audit(self, op: str, detail: JsonDict) -> None:
        entry = {"caller": self._caller_plugin_id, "op": op, **detail}
        _REMOTE_AUDIT_LOG.append(entry)
        log_event(
            self._app_data_dir,
            "plugin.remote_capability",
            f"plugin:{self._caller_plugin_id}",
            {"op": op, **detail},
        )

    async def invoke_remote(
        self,
        capability_id: str,
        payload: JsonDict,
        identity_delegation: IdentityDelegation,
    ) -> JsonDict:
        minimized = minimize_remote_payload(payload)
        self._audit(
            "invoke_remote",
            {
                "capability_id": capability_id,
                "payload_keys": sorted(minimized.keys()),
                "subject_id": identity_delegation.subject_id,
                "org_id": identity_delegation.org_id,
            },
        )
        if capability_id not in self._allowed_capability_ids:
            self._audit(
                "invoke_rejected",
                {"capability_id": capability_id, "reason": "not_allowed"},
            )
            raise RemoteCapabilityRejected(
                f"Remote capability not allowed: {capability_id}"
            )
        try:
            return await asyncio.wait_for(
                self._invoke_allowed(capability_id, minimized, identity_delegation),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            self._audit(
                "invoke_timeout",
                {"capability_id": capability_id, "timeout_seconds": self._timeout_seconds},
            )
            raise RemoteCapabilityRejected(
                f"Remote capability timed out: {capability_id}"
            ) from exc

    async def _invoke_allowed(
        self,
        capability_id: str,
        payload: JsonDict,
        identity_delegation: IdentityDelegation,
    ) -> JsonDict:
        return {
            "ok": True,
            "capability_id": capability_id,
            "mode": "local_stub",
            "subject_id": identity_delegation.subject_id,
            "payload_keys": sorted(payload.keys()),
        }


class HttpRemoteCapabilityGateway(LocalRemoteCapabilityGateway):
    """HTTP : POST vers `{base_url}/connectors/{id}/invoke` avec délégation minimale."""

    def __init__(
        self,
        *,
        base_url: str,
        caller_plugin_id: str,
        app_data_dir: Any,
        allowed_capability_ids: frozenset[str] | None = None,
        timeout_seconds: float = DEFAULT_REMOTE_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            caller_plugin_id=caller_plugin_id,
            app_data_dir=app_data_dir,
            allowed_capability_ids=allowed_capability_ids,
            timeout_seconds=timeout_seconds,
        )
        self._base_url = base_url.rstrip("/")
        self._http_client = http_client

    async def _invoke_allowed(
        self,
        capability_id: str,
        payload: JsonDict,
        identity_delegation: IdentityDelegation,
    ) -> JsonDict:
        body = {
            "payload": payload,
            "identity": {
                "subject_id": identity_delegation.subject_id,
                "org_id": identity_delegation.org_id,
                "scopes": sorted(identity_delegation.scopes),
            },
        }
        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            )
        try:
            response = await client.post(
                f"/connectors/{capability_id}/invoke",
                json=body,
                headers=self._auth_headers(identity_delegation),
            )
            if response.is_error:
                detail = ""
                try:
                    err_body = response.json()
                    if isinstance(err_body, dict):
                        detail = str(
                            err_body.get("message")
                            or err_body.get("error")
                            or err_body
                        )
                except Exception:  # noqa: BLE001
                    detail = response.text[:200]
                raise RemoteCapabilityRejected(
                    f"remote_http_{response.status_code}:{detail or response.reason_phrase}"
                )
            data = response.json()
            if not isinstance(data, dict):
                raise RemoteCapabilityRejected("invalid_remote_response")
            return data
        finally:
            if owns_client:
                await client.aclose()

    def _auth_headers(self, identity_delegation: IdentityDelegation) -> dict[str, str]:
        token = identity_delegation.access_token
        if isinstance(token, str) and token.strip():
            return {"Authorization": f"Bearer {token.strip()}"}
        return {}


def open_remote_capability_gateway(
    *,
    caller_plugin_id: str,
    caller_permissions: frozenset[str],
    plugins_root: Path,
    base_url: str | None = None,
    allowed_capability_ids: frozenset[str] | None = None,
    timeout_seconds: float = DEFAULT_REMOTE_TIMEOUT_SECONDS,
    http_client: httpx.AsyncClient | None = None,
) -> RemoteCapabilityGateway:
    if REMOTE_CAPABILITY_PERMISSION not in caller_permissions:
        raise PermissionError(f"Missing permission: {REMOTE_CAPABILITY_PERMISSION}")

    app_data_dir = resolve_app_data_dir(plugins_root)
    if base_url:
        return HttpRemoteCapabilityGateway(
            base_url=base_url,
            caller_plugin_id=caller_plugin_id,
            app_data_dir=app_data_dir,
            allowed_capability_ids=allowed_capability_ids,
            timeout_seconds=timeout_seconds,
            http_client=http_client,
        )
    return LocalRemoteCapabilityGateway(
        caller_plugin_id=caller_plugin_id,
        app_data_dir=app_data_dir,
        allowed_capability_ids=allowed_capability_ids,
        timeout_seconds=timeout_seconds,
    )
