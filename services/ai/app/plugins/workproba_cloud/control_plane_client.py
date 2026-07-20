"""Client HTTP du plan de contrôle cloud (plugin workproba.cloud)."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.plugins.ports.managed_regards import ManagedRegardsPort, SignedBundle

JsonDict = dict[str, Any]

DEFAULT_TIMEOUT = 30.0
DEVICE_TOKEN_PREFIX = "wp_dev_"


def _merge_token_fields(
    *,
    access_token: str,
    org_id: str | None = None,
    device_id: str | None = None,
) -> JsonDict:
    out: JsonDict = {"access_token": access_token, "token_type": "bearer"}
    if isinstance(org_id, str) and org_id.strip():
        out["org_id"] = org_id.strip()
    if isinstance(device_id, str) and device_id.strip():
        out["device_id"] = device_id.strip()
    return out


class CloudControlPlaneClient:
    """Scaffold V3 : auth device/org, catalogues signés, politiques, preset actif."""

    def __init__(
        self,
        *,
        base_url: str,
        plugin_data_dir: Path,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._plugin_data_dir = plugin_data_dir
        self._http_client = http_client

    def _config_path(self) -> Path:
        return self._plugin_data_dir / "config.json"

    def load_tokens(self) -> JsonDict:
        path = self._config_path()
        if not path.is_file():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            return {}
        tokens = raw.get("tokens")
        return dict(tokens) if isinstance(tokens, dict) else {}

    def save_tokens(self, tokens: JsonDict) -> JsonDict:
        self._plugin_data_dir.mkdir(parents=True, exist_ok=True)
        config: JsonDict = {}
        path = self._config_path()
        if path.is_file():
            with path.open("r", encoding="utf-8") as handle:
                existing = json.load(handle)
            if isinstance(existing, dict):
                config = existing
        config["base_url"] = self._base_url
        config["tokens"] = {**self.load_tokens(), **tokens}
        with path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        return config["tokens"]

    def _auth_headers(self) -> dict[str, str]:
        token = self.load_tokens().get("access_token")
        if isinstance(token, str) and token.strip():
            return {"Authorization": f"Bearer {token.strip()}"}
        return {}

    async def _client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=DEFAULT_TIMEOUT,
            headers=self._auth_headers(),
        )

    async def authenticate(
        self,
        *,
        bearer_token: str | None = None,
        device_code: str | None = None,
        org_id: str | None = None,
    ) -> JsonDict:
        """Enrôlement : bearer direct (admin) ou join_token via join_with_token."""
        if bearer_token:
            token = bearer_token.strip()
            if token.startswith(DEVICE_TOKEN_PREFIX):
                tokens = self.save_tokens(
                    _merge_token_fields(access_token=token, org_id=org_id)
                )
                return {
                    "authenticated": True,
                    "method": "bearer",
                    "org_id": tokens.get("org_id"),
                }

            if self._looks_like_user_jwt(token):
                tokens = await self.exchange_user_jwt_for_device_bearer(token)
                return {
                    "authenticated": True,
                    "method": "bearer",
                    "org_id": tokens.get("org_id"),
                }

            tokens = self.save_tokens(
                _merge_token_fields(access_token=token, org_id=org_id)
            )
            return {"authenticated": True, "method": "bearer", "org_id": tokens.get("org_id")}

        if device_code:
            raise ValueError("join_token_required")

        raise ValueError("cloud_auth_required")

    @staticmethod
    def _looks_like_user_jwt(token: str) -> bool:
        if token.startswith(DEVICE_TOKEN_PREFIX):
            return False
        parts = token.split(".")
        if len(parts) != 3:
            return False
        header_b64 = parts[0]
        padding = (-len(header_b64)) % 4
        if padding:
            header_b64 += "=" * padding
        try:
            header = json.loads(base64.urlsafe_b64decode(header_b64))
        except (ValueError, json.JSONDecodeError, TypeError):
            return False
        return isinstance(header, dict) and "alg" in header

    async def exchange_user_jwt_for_device_bearer(self, user_jwt: str) -> JsonDict:
        """Échange un User JWT contre un jeton poste durable (POST /devices/desktop-bearer)."""
        headers: dict[str, str] = {"Authorization": f"Bearer {user_jwt.strip()}"}
        stored_org_id = self.load_tokens().get("org_id")
        if (
            isinstance(stored_org_id, str)
            and stored_org_id.strip()
            and re.fullmatch(r"\d+", stored_org_id.strip())
        ):
            headers["X-Organization-Id"] = stored_org_id.strip()

        client = await self._client()
        owns_client = self._http_client is None
        try:
            response = await client.post(
                "/devices/desktop-bearer",
                headers=headers,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._reraise_http_error(exc)
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid_control_plane_response")
        finally:
            if owns_client:
                await client.aclose()

        access_token = payload.get("accessToken")
        org_id = payload.get("orgId")
        device_id = payload.get("deviceId")
        if (
            not isinstance(access_token, str)
            or not access_token.strip()
            or not access_token.strip().startswith(DEVICE_TOKEN_PREFIX)
        ):
            raise ValueError("desktop_bearer_missing")

        tokens: JsonDict = {
            "access_token": access_token.strip(),
            "token_type": "bearer",
        }
        if isinstance(org_id, str) and org_id.strip():
            tokens["org_id"] = org_id.strip()
        if isinstance(device_id, str) and device_id.strip():
            tokens["device_id"] = device_id.strip()
        self.save_tokens(tokens)
        return tokens

    async def ensure_durable_device_bearer(self) -> bool:
        token = self.load_tokens().get("access_token")
        if not isinstance(token, str) or not token.strip():
            return False
        token = token.strip()
        if token.startswith(DEVICE_TOKEN_PREFIX):
            return True
        if self._looks_like_user_jwt(token):
            try:
                tokens = await self.exchange_user_jwt_for_device_bearer(token)
                access = tokens.get("access_token")
                return isinstance(access, str) and access.startswith(DEVICE_TOKEN_PREFIX)
            except (PermissionError, ValueError, httpx.HTTPError, httpx.RequestError):
                return False
        # Bearer opaque (admin) : valider auprès du cloud, pas de True aveugle
        try:
            await self.get_llm_quota()
            return True
        except PermissionError:
            return False
        except (httpx.HTTPError, ValueError):
            # Panne réseau : fail-open pour ne pas déconnecter à tort
            return True

    @staticmethod
    def _auth_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                for key in ("message", "detail", "error"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        except (json.JSONDecodeError, ValueError):
            pass
        return "invalid_device_token"

    @staticmethod
    def _reraise_http_error(exc: httpx.HTTPStatusError) -> None:
        status = exc.response.status_code
        if status in (401, 403):
            raise PermissionError(
                CloudControlPlaneClient._auth_error_detail(exc.response),
            ) from exc
        raise ValueError(f"control_plane_http_{status}") from exc

    async def _get_json(self, path: str, *, params: JsonDict | None = None) -> JsonDict:
        client = await self._client()
        owns_client = self._http_client is None
        try:
            response = await client.get(path, params=params, headers=self._auth_headers())
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._reraise_http_error(exc)
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid_control_plane_response")
            return payload
        finally:
            if owns_client:
                await client.aclose()

    async def _post_json(
        self,
        path: str,
        *,
        json_body: JsonDict | None = None,
        params: JsonDict | None = None,
    ) -> JsonDict:
        client = await self._client()
        owns_client = self._http_client is None
        try:
            response = await client.post(
                path,
                json=json_body,
                params=params,
                headers=self._auth_headers(),
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self._reraise_http_error(exc)
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid_control_plane_response")
            return payload
        finally:
            if owns_client:
                await client.aclose()

    async def _post_public_json(
        self,
        path: str,
        *,
        json_body: JsonDict | None = None,
    ) -> JsonDict:
        """POST sans jeton (endpoints publics, ex. /devices/join)."""
        client = await self._client()
        owns_client = self._http_client is None
        try:
            response = await client.post(path, json=json_body)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid_control_plane_response")
            return payload
        finally:
            if owns_client:
                await client.aclose()

    async def join_with_token(
        self,
        *,
        token: str,
        device_name: str | None = None,
    ) -> JsonDict:
        """Échange un jeton join contre deviceId + accessToken (POST /devices/join)."""
        body: JsonDict = {"token": token.strip()}
        if device_name and device_name.strip():
            body["deviceName"] = device_name.strip()
        payload = await self._post_public_json("/devices/join", json_body=body)

        response_base_url = payload.get("baseUrl")
        if isinstance(response_base_url, str) and response_base_url.strip():
            self._base_url = response_base_url.strip().rstrip("/")

        tokens: JsonDict = {}
        device_id = payload.get("deviceId")
        access_token = payload.get("accessToken")
        org_id = payload.get("orgId")
        profile = payload.get("profile")
        organization_name = payload.get("organizationName")
        if isinstance(device_id, str) and device_id.strip():
            tokens["device_id"] = device_id.strip()
        if isinstance(access_token, str) and access_token.strip():
            tokens["access_token"] = access_token.strip()
            tokens["token_type"] = "bearer"
        if isinstance(org_id, str) and org_id.strip():
            tokens["org_id"] = org_id.strip()
        if isinstance(profile, str) and profile.strip():
            tokens["profile"] = profile.strip()
        org_label = next(
            (
                value.strip()
                for value in (organization_name, profile, org_id)
                if isinstance(value, str) and value.strip()
            ),
            None,
        )
        if org_label:
            tokens["org_label"] = org_label
        if tokens:
            self.save_tokens(tokens)

        return payload

    async def enroll_device(
        self,
        *,
        org_id: str,
        device_name: str,
    ) -> JsonDict:
        """Déprécié : POST /devices/enroll supprimé en H0.1 — utiliser join_with_token."""
        _ = org_id, device_name
        raise ValueError("join_token_required")

    async def list_sync_artefacts(self, *, project_id: str | None = None) -> JsonDict:
        params: JsonDict = {}
        if project_id:
            params["projectId"] = project_id
        return await self._get_json("/sync/artefacts", params=params or None)

    async def push_sync_artefact_metadata(
        self,
        *,
        project_id: str,
        artifact_id: str,
        version: str,
        filename: str,
        checksum: str,
        size: int,
    ) -> JsonDict:
        return await self._post_json(
            "/sync/artefacts",
            json_body={
                "projectId": project_id,
                "artifactId": artifact_id,
                "version": version,
                "filename": filename,
                "checksum": checksum,
                "size": size,
            },
        )

    async def request_upload_url(
        self,
        *,
        artefact_db_id: int,
        content_type: str | None = None,
    ) -> JsonDict:
        params: JsonDict | None = None
        if content_type:
            params = {"contentType": content_type}
        return await self._post_json(
            f"/sync/artefacts/{artefact_db_id}/upload-url",
            params=params,
        )

    async def confirm_upload(self, *, artefact_db_id: int) -> JsonDict:
        return await self._post_json(f"/sync/artefacts/{artefact_db_id}/confirm")

    async def request_download_url(self, *, artefact_db_id: int) -> JsonDict:
        return await self._post_json(f"/sync/artefacts/{artefact_db_id}/download-url")

    async def verify_blob(self, *, artefact_db_id: int) -> JsonDict:
        return await self._post_json(f"/sync/artefacts/{artefact_db_id}/verify-blob")

    async def get_presigned_blob(self, url: str) -> bytes:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def put_presigned_blob(
        self,
        *,
        url: str,
        content: bytes,
        content_type: str | None = None,
        _put_client: httpx.AsyncClient | None = None,
    ) -> None:
        headers: dict[str, str] = {"Content-Length": str(len(content))}
        if content_type:
            headers["Content-Type"] = content_type

        if _put_client is not None:
            response = await _put_client.put(url, content=content, headers=headers)
            response.raise_for_status()
            return

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.put(url, content=content, headers=headers)
            response.raise_for_status()

    async def fetch_regards_catalog(self, *, org_id: str | None = None) -> JsonDict:
        """org_id ignoré : l'org est dérivée du DeviceBearer côté cloud."""
        _ = org_id
        return await self._get_json("/catalogs/regards")

    async def fetch_capabilities(self, *, org_id: str | None = None) -> JsonDict:
        """org_id ignoré : l'org est dérivée du DeviceBearer côté cloud."""
        _ = org_id
        return await self._get_json("/catalogs/capabilities")

    async def fetch_policies(self, *, org_id: str | None = None) -> JsonDict:
        """org_id ignoré : l'org est dérivée du DeviceBearer côté cloud."""
        _ = org_id
        return await self._get_json("/policies")

    async def list_connectors(self, *, org_id: str | None = None) -> JsonDict:
        """GET /connectors — connecteurs managés autorisés pour le device."""
        _ = org_id  # org is implied by DeviceBearer on the server
        return await self._get_json("/connectors")

    async def get_llm_quota(self) -> JsonDict:
        """GET /llm/v1/quota — statut quota LLM de l'organisation."""
        return await self._get_json("/llm/v1/quota")

    async def fetch_allowed_connector_ids(self) -> frozenset[str]:
        """GET /connectors → ids ; liste vide = org sans connecteurs (pas un fallback)."""
        payload = await self._get_json("/connectors")
        raw_connectors = payload.get("connectors")
        if not isinstance(raw_connectors, list):
            return frozenset()
        return frozenset(
            str(item.get("id"))
            for item in raw_connectors
            if isinstance(item, dict) and item.get("id")
        )

    async def invoke_connector(
        self,
        connector_id: str,
        *,
        payload: JsonDict | None = None,
        subject_id: str | None = None,
        org_id: str | None = None,
        scopes: list[str] | None = None,
    ) -> JsonDict:
        """POST /connectors/{id}/invoke — relai transport Mode A."""
        _ = subject_id, org_id  # identity locale uniquement ; cloud dérive du DeviceBearer
        body: JsonDict = {"payload": payload or {}}
        if scopes:
            body["identity"] = {"scopes": scopes}
        return await self._post_json(f"/connectors/{connector_id}/invoke", json_body=body)

    async def fetch_active_preset(self, *, device_id: str | None = None) -> JsonDict:
        """device_id ignoré : le device est dérivé du DeviceBearer côté cloud."""
        _ = device_id
        return await self._get_json("/presets/active")

    async def pull_and_install_regards(
        self,
        managed_regards_port: ManagedRegardsPort,
        *,
        org_id: str | None = None,
        activate: bool = True,
    ) -> JsonDict:
        """Télécharge les bundles signés et les installe via ManagedRegardsPort."""
        catalog = await self.fetch_regards_catalog(org_id=org_id)
        bundles_raw = catalog.get("bundles") or catalog.get("catalogs") or []
        if not isinstance(bundles_raw, list):
            raise ValueError("invalid_regards_catalog")

        installed: list[JsonDict] = []
        activated: JsonDict | None = None
        for item in bundles_raw:
            if not isinstance(item, dict):
                continue
            bundle = SignedBundle.from_dict(item)
            record = managed_regards_port.install_catalog_version(bundle)
            installed.append(record)
            if activate:
                activated = managed_regards_port.activate_catalog(
                    bundle.catalog_id,
                    bundle.version,
                )

        return {
            "installed": installed,
            "activated": activated,
            "count": len(installed),
        }
