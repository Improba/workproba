"""Tests CloudControlPlaneClient scaffold (T-V3-CP-1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

import app.auth as authmod
import app.main as mainmod
from app.plugins.ports.managed_regards import create_personas_managed_port, sign_bundle_for_tests
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, PLUGIN_WORKPROBA_PERSONAS
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    app_data = tmp_path / "app_data"
    plugins = app_data / "plugins"
    cloud_dir = plugins / PLUGIN_WORKPROBA_CLOUD
    personas_dir = plugins / PLUGIN_WORKPROBA_PERSONAS
    cloud_dir.mkdir(parents=True)
    personas_dir.mkdir(parents=True)
    return cloud_dir, personas_dir, plugins


def _sample_bundle_dict() -> dict:
    return sign_bundle_for_tests(
        catalog_id="cloud-regards",
        version="2.0.0",
        name="Cloud Regards",
        personas=[
            {
                "id": "c01",
                "name": "Risk",
                "role": "Risques",
                "description": "Risque opérationnel",
                "system_prompt": "Tu es risk manager.",
                "avatar_color": "#AA5533",
                "avatar_icon": "alert-triangle",
            }
        ],
    ).to_dict()


@pytest.mark.asyncio
async def test_authenticate_bearer_persists_tokens(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    client = CloudControlPlaneClient(
        base_url="https://cloud.example.test",
        plugin_data_dir=cloud_dir,
    )
    result = await client.authenticate(bearer_token="test-token", org_id="org-42")
    assert result["authenticated"] is True
    tokens = client.load_tokens()
    assert tokens["access_token"] == "test-token"
    assert tokens["org_id"] == "org-42"


@pytest.mark.asyncio
async def test_authenticate_user_jwt_exchanges_for_device_bearer(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    exchange_calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            auth = request.headers.get("authorization", "")
            exchange_calls.append(auth)
            assert auth == f"Bearer {user_jwt}"
            return httpx.Response(
                200,
                json={
                    "accessToken": "wp_dev_from_jwt",
                    "orgId": "org-jwt",
                    "deviceId": "dev_browser_1_1",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        result = await client.authenticate(bearer_token=user_jwt)

    assert result["authenticated"] is True
    assert result["org_id"] == "org-jwt"
    assert len(exchange_calls) == 1
    tokens = client.load_tokens()
    assert tokens["access_token"] == "wp_dev_from_jwt"
    assert tokens["org_id"] == "org-jwt"
    assert tokens["device_id"] == "dev_browser_1_1"


@pytest.mark.asyncio
async def test_authenticate_wp_dev_skips_exchange(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url.path}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        result = await client.authenticate(
            bearer_token="wp_dev_existing",
            org_id="org-42",
        )

    assert result["authenticated"] is True
    tokens = client.load_tokens()
    assert tokens["access_token"] == "wp_dev_existing"
    assert tokens["org_id"] == "org-42"


@pytest.mark.asyncio
async def test_authenticate_wp_dev_preserves_org_id_when_none(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {
                    "access_token": "wp_dev_old",
                    "org_id": "org-prod",
                    "token_type": "bearer",
                },
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected request: {request.url.path}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        result = await client.authenticate(
            bearer_token="wp_dev_existing",
            org_id=None,
        )

    assert result["authenticated"] is True
    tokens = client.load_tokens()
    assert tokens["access_token"] == "wp_dev_existing"
    assert tokens["org_id"] == "org-prod"


def test_looks_like_user_jwt_rejects_fake_three_part_token() -> None:
    assert CloudControlPlaneClient._looks_like_user_jwt("a.b.c") is False


def test_looks_like_user_jwt_accepts_real_three_part_token() -> None:
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    assert CloudControlPlaneClient._looks_like_user_jwt(user_jwt) is True


@pytest.mark.asyncio
async def test_ensure_durable_device_bearer_opaque_permission_error(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": "opaque-admin-token", "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/llm/v1/quota":
            return httpx.Response(403, json={"message": "forbidden"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        durable = await client.ensure_durable_device_bearer()

    assert durable is False


@pytest.mark.asyncio
async def test_ensure_durable_device_bearer_opaque_quota_ok(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": "opaque-admin-token", "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/llm/v1/quota":
            return httpx.Response(200, json={"remaining": 100})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        durable = await client.ensure_durable_device_bearer()

    assert durable is True


@pytest.mark.asyncio
async def test_ensure_durable_device_bearer_migrates_stored_jwt(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": user_jwt, "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            return httpx.Response(
                200,
                json={
                    "accessToken": "wp_dev_migrated",
                    "orgId": "org-migrated",
                    "deviceId": "dev_browser_2_1",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        migrated = await client.ensure_durable_device_bearer()

    assert migrated is True
    tokens = client.load_tokens()
    assert tokens["access_token"] == "wp_dev_migrated"
    assert tokens["org_id"] == "org-migrated"
    assert tokens["device_id"] == "dev_browser_2_1"


@pytest.mark.asyncio
async def test_exchange_user_jwt_missing_access_token_raises(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    existing_token = "wp_dev_existing"
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": existing_token, "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            return httpx.Response(200, json={"orgId": "org-1", "deviceId": "dev-1"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        with pytest.raises(ValueError, match="desktop_bearer_missing"):
            await client.exchange_user_jwt_for_device_bearer(user_jwt)

    tokens = client.load_tokens()
    assert tokens["access_token"] == existing_token


@pytest.mark.asyncio
async def test_exchange_user_jwt_non_wp_dev_access_token_raises(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            return httpx.Response(
                200,
                json={
                    "accessToken": "not_a_device_bearer",
                    "orgId": "org-1",
                    "deviceId": "dev-1",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        with pytest.raises(ValueError, match="desktop_bearer_missing"):
            await client.exchange_user_jwt_for_device_bearer(user_jwt)

    assert client.load_tokens() == {}


@pytest.mark.asyncio
async def test_exchange_user_jwt_sends_numeric_org_header(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": user_jwt, "org_id": "42", "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            seen_headers.append(dict(request.headers))
            return httpx.Response(
                200,
                json={
                    "accessToken": "wp_dev_with_org_header",
                    "orgId": "42",
                    "deviceId": "dev-42",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.exchange_user_jwt_for_device_bearer(user_jwt)

    assert len(seen_headers) == 1
    assert seen_headers[0].get("x-organization-id") == "42"


@pytest.mark.asyncio
async def test_ensure_durable_device_bearer_permission_error_keeps_jwt(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": user_jwt, "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            return httpx.Response(403, json={"message": "forbidden"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        migrated = await client.ensure_durable_device_bearer()

    assert migrated is False
    tokens = client.load_tokens()
    assert tokens["access_token"] == user_jwt


@pytest.mark.asyncio
async def test_ensure_durable_device_bearer_false_when_exchange_returns_non_wp_dev(
    tmp_path: Path,
) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    user_jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig"
    config_path = cloud_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "base_url": "https://cloud.example.test",
                "tokens": {"access_token": user_jwt, "token_type": "bearer"},
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/desktop-bearer":
            return httpx.Response(200, json={"accessToken": "bad_token"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        migrated = await client.ensure_durable_device_bearer()

    assert migrated is False
    assert client.load_tokens()["access_token"] == user_jwt


@pytest.mark.asyncio
async def test_authenticate_device_code_raises_join_token_required(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    client = CloudControlPlaneClient(
        base_url="https://cloud.example.test",
        plugin_data_dir=cloud_dir,
    )
    with pytest.raises(ValueError, match="join_token_required"):
        await client.authenticate(device_code="pending-code", org_id="org-42")


@pytest.mark.asyncio
async def test_fetch_endpoints_with_mock_transport(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    bundle = _sample_bundle_dict()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/catalogs/regards":
            assert "org" not in request.url.params
            return httpx.Response(200, json={"bundles": [bundle]})
        if request.url.path == "/catalogs/capabilities":
            assert "org" not in request.url.params
            return httpx.Response(200, json={"capabilities": ["workproba.personas"]})
        if request.url.path == "/policies":
            assert "org" not in request.url.params
            return httpx.Response(200, json={"project_sync": True})
        if request.url.path == "/presets/active":
            assert "device" not in request.url.params
            return httpx.Response(200, json={"preset_id": "enterprise"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.authenticate(bearer_token="abc")
        regards = await client.fetch_regards_catalog(org_id="org-1")
        caps = await client.fetch_capabilities(org_id="org-1")
        policies = await client.fetch_policies(org_id="org-1")
        preset = await client.fetch_active_preset(device_id="dev-1")

    assert regards["bundles"][0]["catalog_id"] == "cloud-regards"
    assert "workproba.personas" in caps["capabilities"]
    assert policies["project_sync"] is True
    assert preset["preset_id"] == "enterprise"


@pytest.mark.asyncio
async def test_pull_and_install_regards(tmp_path: Path) -> None:
    cloud_dir, personas_dir, _ = _layout(tmp_path)
    bundle = _sample_bundle_dict()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/catalogs/regards":
            return httpx.Response(200, json={"bundles": [bundle]})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.authenticate(bearer_token="abc")
        port = create_personas_managed_port(personas_dir)
        result = await client.pull_and_install_regards(port)

    assert result["count"] == 1
    assert result["activated"]["catalog_id"] == "cloud-regards"
    status = port.get_catalog_status()
    assert status["active"] is True


@pytest.mark.asyncio
async def test_join_with_token_persists_tokens(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/join":
            body = json.loads(request.content.decode())
            assert body["token"] == "join-abc"
            assert body["deviceName"] == "desk-lyon"
            assert "authorization" not in request.headers
            return httpx.Response(
                201,
                json={
                    "deviceId": "dev_join1",
                    "accessToken": "wp_dev_join_token",
                    "profile": "field",
                    "orgId": "org-field",
                    "organizationName": "Acme Field Ops",
                    "baseUrl": "https://cloud.example.test",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        result = await client.join_with_token(token="join-abc", device_name="desk-lyon")

    assert result["deviceId"] == "dev_join1"
    tokens = client.load_tokens()
    assert tokens["access_token"] == "wp_dev_join_token"
    assert tokens["device_id"] == "dev_join1"
    assert tokens["org_id"] == "org-field"
    assert tokens["profile"] == "field"
    assert tokens["org_label"] == "Acme Field Ops"
    config_path = cloud_dir / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["base_url"] == "https://cloud.example.test"


@pytest.mark.asyncio
async def test_join_with_token_org_label_falls_back_to_profile(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devices/join":
            return httpx.Response(
                201,
                json={
                    "deviceId": "dev_join2",
                    "accessToken": "wp_dev_join_token2",
                    "profile": "enterprise",
                    "orgId": "org-ent",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.join_with_token(token="join-def")

    tokens = client.load_tokens()
    assert tokens["org_label"] == "enterprise"


def test_cloud_join_http(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)

    async def fake_join(self, *, token: str, device_name: str | None = None):
        assert token == "opaque-token"
        self.save_tokens(
            {
                "access_token": "wp_dev_http",
                "device_id": "dev_http",
                "org_id": "org-http",
                "profile": "standard",
                "token_type": "bearer",
            }
        )
        return {
            "deviceId": "dev_http",
            "accessToken": "wp_dev_http",
            "orgId": "org-http",
            "profile": "standard",
        }

    with patch.object(CloudControlPlaneClient, "join_with_token", fake_join):
        with TestClient(mainmod.app) as test_client:
            enroll_resp = test_client.post(
                "/plugins/cloud/enroll",
                json={
                    "plugin_data_dir": str(cloud_dir),
                    "base_url": "https://cloud.example.test",
                    "join_token": "opaque-token",
                },
                headers=INTERNAL_HEADERS,
            )
            assert enroll_resp.status_code == 200
            body = enroll_resp.json()
            assert body["authenticated"] is True
            assert body["method"] == "join_token"
            assert body["org_id"] == "org-http"


@pytest.mark.asyncio
async def test_enroll_device_raises_join_token_required(tmp_path: Path) -> None:
    """enroll_device est déprécié : org_id seul exige un code d'invitation."""
    cloud_dir, _, _ = _layout(tmp_path)
    client = CloudControlPlaneClient(
        base_url="https://cloud.example.test",
        plugin_data_dir=cloud_dir,
    )
    with pytest.raises(ValueError, match="join_token_required"):
        await client.enroll_device(org_id="org-99", device_name="desk-paris")


@pytest.mark.asyncio
async def test_sync_artefact_endpoints_with_mock_transport(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    artefact_meta = {
        "id": 42,
        "projectId": "proj-alpha",
        "artifactId": "art-q1",
        "version": "1.0.0",
        "filename": "q1.pdf",
        "checksum": "sha256:abc",
        "size": 4096,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sync/artefacts" and request.method == "GET":
            assert request.url.params.get("projectId") == "proj-alpha"
            return httpx.Response(200, json={"items": [artefact_meta]})
        if request.url.path == "/sync/artefacts" and request.method == "POST":
            body = json.loads(request.content.decode())
            assert body == {k: v for k, v in artefact_meta.items() if k != "id"}
            return httpx.Response(200, json=artefact_meta)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=transport,
    ) as http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=http_client,
        )
        await client.authenticate(bearer_token="sync-token")
        pushed = await client.push_sync_artefact_metadata(
            project_id="proj-alpha",
            artifact_id="art-q1",
            version="1.0.0",
            filename="q1.pdf",
            checksum="sha256:abc",
            size=4096,
        )
        listed = await client.list_sync_artefacts(project_id="proj-alpha")

    assert pushed["id"] == 42
    assert pushed["artifactId"] == "art-q1"
    assert listed["items"][0]["filename"] == "q1.pdf"


@pytest.mark.asyncio
async def test_upload_url_confirm_and_put_presigned_blob(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    artefact_db_id = 99
    put_calls: list[httpx.Request] = []

    def cp_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/upload-url":
            assert request.method == "POST"
            assert request.url.params.get("contentType") == "application/pdf"
            return httpx.Response(
                200,
                json={
                    "url": "https://blob.example.test/upload/key",
                    "storageKey": "sync/proj/art/v1/file.pdf",
                    "expiresAt": "2026-07-15T21:40:00.000Z",
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/confirm":
            assert request.method == "POST"
            return httpx.Response(200, json={"id": artefact_db_id, "artifactId": "art-q1"})
        return httpx.Response(404)

    def blob_handler(request: httpx.Request) -> httpx.Response:
        put_calls.append(request)
        assert request.method == "PUT"
        assert request.url == httpx.URL("https://blob.example.test/upload/key")
        assert request.headers.get("content-type") == "application/pdf"
        assert request.headers.get("content-length") == "11"
        assert request.content == b"hello world"
        assert "authorization" not in request.headers
        return httpx.Response(200)

    cp_transport = httpx.MockTransport(cp_handler)
    blob_transport = httpx.MockTransport(blob_handler)
    async with httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=cp_transport,
    ) as cp_http_client, httpx.AsyncClient(transport=blob_transport) as blob_http_client:
        client = CloudControlPlaneClient(
            base_url="https://cloud.example.test",
            plugin_data_dir=cloud_dir,
            http_client=cp_http_client,
        )
        await client.authenticate(bearer_token="sync-token")
        upload = await client.request_upload_url(
            artefact_db_id=artefact_db_id,
            content_type="application/pdf",
        )
        await client.put_presigned_blob(
            url=str(upload["url"]),
            content=b"hello world",
            content_type="application/pdf",
            _put_client=blob_http_client,
        )
        confirmed = await client.confirm_upload(artefact_db_id=artefact_db_id)

    assert upload["storageKey"] == "sync/proj/art/v1/file.pdf"
    assert len(put_calls) == 1
    assert confirmed["id"] == artefact_db_id


def test_cloud_enroll_http(tmp_path: Path) -> None:
    cloud_dir, _, _ = _layout(tmp_path)
    with TestClient(mainmod.app) as test_client:
        enroll_resp = test_client.post(
            "/plugins/cloud/enroll",
            json={
                "plugin_data_dir": str(cloud_dir),
                "base_url": "https://cloud.example.test",
                "bearer_token": "token-xyz",
                "org_id": "org-http",
            },
            headers=INTERNAL_HEADERS,
        )
        assert enroll_resp.status_code == 200
        assert enroll_resp.json()["authenticated"] is True


def test_cloud_enroll_org_id_only_returns_join_token_required(tmp_path: Path) -> None:
    """org_id seul sans join_token ni bearer renvoie 400 join_token_required."""
    cloud_dir, _, _ = _layout(tmp_path)
    with TestClient(mainmod.app) as test_client:
        enroll_resp = test_client.post(
            "/plugins/cloud/enroll",
            json={
                "plugin_data_dir": str(cloud_dir),
                "base_url": "https://cloud.example.test",
                "org_id": "org-only",
            },
            headers=INTERNAL_HEADERS,
        )
        assert enroll_resp.status_code == 400
        assert enroll_resp.json()["detail"] == "join_token_required"


def test_cloud_sync_regards_http(tmp_path: Path) -> None:
    cloud_dir, personas_dir, _ = _layout(tmp_path)
    bundle = _sample_bundle_dict()

    async def fake_pull(
        self,
        managed_regards_port,
        *,
        org_id: str | None = None,
        activate: bool = True,
    ):
        from app.plugins.ports.managed_regards import SignedBundle

        signed = SignedBundle.from_dict(bundle)
        installed = managed_regards_port.install_catalog_version(signed)
        activated = managed_regards_port.activate_catalog(signed.catalog_id, signed.version)
        return {"installed": [installed], "activated": activated, "count": 1}

    with patch.object(CloudControlPlaneClient, "pull_and_install_regards", fake_pull):
        with TestClient(mainmod.app) as test_client:
            test_client.post(
                "/plugins/cloud/enroll",
                json={
                    "plugin_data_dir": str(cloud_dir),
                    "base_url": "https://cloud.example.test",
                    "bearer_token": "token-xyz",
                },
                headers=INTERNAL_HEADERS,
            )
            sync_resp = test_client.post(
                "/plugins/cloud/sync-regards",
                json={"plugin_data_dir": str(cloud_dir)},
                headers=INTERNAL_HEADERS,
            )
            assert sync_resp.status_code == 200
            assert sync_resp.json()["count"] == 1

    port = create_personas_managed_port(personas_dir)
    assert port.get_catalog_status()["catalog_id"] == "cloud-regards"
    assert not (cloud_dir / "managed").exists()
    assert (personas_dir / "managed" / "cloud-regards").exists()
