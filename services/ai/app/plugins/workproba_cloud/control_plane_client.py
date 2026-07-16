"""Client HTTP du plan de contrôle cloud (plugin workproba.cloud)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.plugins.ports.managed_regards import ManagedRegardsPort, SignedBundle

JsonDict = dict[str, Any]

DEFAULT_TIMEOUT = 30.0


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
        """Enrôlement stub : bearer direct ou device code (polling simulé)."""
        if bearer_token:
            tokens = self.save_tokens(
                {
                    "access_token": bearer_token,
                    "token_type": "bearer",
                    "org_id": org_id,
                }
            )
            return {"authenticated": True, "method": "bearer", "org_id": tokens.get("org_id")}

        if device_code:
            client = await self._client()
            try:
                response = await client.post(
                    "/devices/token",
                    json={"device_code": device_code, "org_id": org_id},
                )
                if response.status_code == 200:
                    payload = response.json()
                    if isinstance(payload, dict) and payload.get("access_token"):
                        tokens = self.save_tokens(
                            {
                                "access_token": str(payload["access_token"]),
                                "refresh_token": payload.get("refresh_token"),
                                "token_type": payload.get("token_type", "bearer"),
                                "org_id": payload.get("org_id") or org_id,
                            }
                        )
                        return {
                            "authenticated": True,
                            "method": "device_code",
                            "org_id": tokens.get("org_id"),
                        }
            finally:
                if self._http_client is None:
                    await client.aclose()

            # Stub local : mémorise le device code en attente de validation admin.
            tokens = self.save_tokens(
                {
                    "device_code": device_code,
                    "device_pending": True,
                    "org_id": org_id,
                }
            )
            return {
                "authenticated": False,
                "method": "device_code",
                "pending": True,
                "org_id": tokens.get("org_id"),
            }

        raise ValueError("cloud_auth_required")

    async def _get_json(self, path: str, *, params: JsonDict | None = None) -> JsonDict:
        client = await self._client()
        owns_client = self._http_client is None
        try:
            response = await client.get(path, params=params, headers=self._auth_headers())
            response.raise_for_status()
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
            response.raise_for_status()
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
        params: JsonDict = {}
        if org_id:
            params["org"] = org_id
        return await self._get_json("/catalogs/regards", params=params or None)

    async def fetch_capabilities(self, *, org_id: str | None = None) -> JsonDict:
        params: JsonDict = {}
        if org_id:
            params["org"] = org_id
        return await self._get_json("/catalogs/capabilities", params=params or None)

    async def fetch_policies(self, *, org_id: str | None = None) -> JsonDict:
        params: JsonDict = {}
        if org_id:
            params["org"] = org_id
        return await self._get_json("/policies", params=params or None)

    async def fetch_active_preset(self, *, device_id: str | None = None) -> JsonDict:
        params: JsonDict = {}
        if device_id:
            params["device"] = device_id
        return await self._get_json("/presets/active", params=params or None)

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
