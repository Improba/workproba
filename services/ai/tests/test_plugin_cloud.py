"""Tests plugin cloud (sync dossier local via ProjectSyncPort)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic_ai import RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.test import TestModel

import app.auth as authmod
import app.main as mainmod
from app.agent.tools import ToolDeps, ToolContext, build_agent
from app.limits import DEFAULT_LIMITS
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD
from app.plugins.workproba_cloud import storage as cloud_storage
from app.plugins.workproba_cloud.control_plane_client import CloudControlPlaneClient
from app.plugins.workproba_cloud.sync_access import open_sync_port_for_cloud
from app.plugins.workproba_projet import storage as projet_storage
from app.sandbox.runner import SandboxRunner

from conftest import FakeProjectClient

INTERNAL_HEADERS = {"X-Internal-Secret": "desktop-dev-secret"}


@pytest.fixture(autouse=True)
def _patch_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)


def _layout(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    app_data = tmp_path / "app_data"
    plugins = app_data / "plugins"
    cloud_dir = plugins / PLUGIN_WORKPROBA_CLOUD
    projet_dir = plugins / "workproba.projet"
    cloud_dir.mkdir(parents=True)
    projet_dir.mkdir(parents=True)
    mount = tmp_path / "cloud_mount"
    mount.mkdir()
    project = projet_storage.create_project(projet_dir, "Contrats")
    project_id = str(project["id"])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "contrat.docx"
    source.write_text("contenu", encoding="utf-8")
    projet_storage.publish_artifact(
        plugin_data_dir=projet_dir,
        workspace_root=workspace,
        source_path="contrat.docx",
        project_id=project_id,
        name="contrat.docx",
    )
    return cloud_dir, projet_dir, mount, project_id


def _enroll_cloud_dir(cloud_dir: Path) -> None:
    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.example.test"})
    with (cloud_dir / "config.json").open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["tokens"] = {"access_token": "sync-token", "token_type": "bearer"}
    with (cloud_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)


def test_cloud_disconnect_clears_tokens(tmp_path: Path) -> None:
    cloud_dir, _, _, _ = _layout(tmp_path)
    cloud_storage.save_config(
        cloud_dir,
        {
            "base_url": "https://cloud.example.test",
            "tokens": {
                "access_token": "sync-token",
                "device_id": "dev_1",
                "org_id": "org-1",
            },
        },
    )
    assert cloud_storage.is_enrolled(cloud_dir)

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/disconnect",
            json={"plugin_data_dir": str(cloud_dir)},
            headers=INTERNAL_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    assert not cloud_storage.is_enrolled(cloud_dir)
    assert cloud_storage.get_access_token(cloud_dir) is None
    assert cloud_storage.get_control_plane_base_url(cloud_dir) == "https://cloud.example.test"


def test_cloud_enroll_org_id_only_requires_join_token(tmp_path: Path) -> None:
    cloud_dir, _, _, _ = _layout(tmp_path)
    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/enroll",
            json={
                "plugin_data_dir": str(cloud_dir),
                "base_url": "https://cloud.example.test",
                "org_id": "org-only",
            },
            headers=INTERNAL_HEADERS,
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "join_token_required"


def test_cloud_enroll_network_unreachable_returns_502(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_dir, _, _, _ = _layout(tmp_path)

    async def fake_authenticate(self, **_kwargs):  # noqa: ANN001
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(CloudControlPlaneClient, "authenticate", fake_authenticate)

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/enroll",
            json={
                "plugin_data_dir": str(cloud_dir),
                "base_url": "https://cloud.example.test",
                "bearer_token": "wp_dev_unused",
            },
            headers=INTERNAL_HEADERS,
        )

    assert resp.status_code == 502
    assert resp.json()["detail"] == "control_plane_unreachable"


def test_cloud_config_and_status(tmp_path: Path) -> None:
    cloud_dir, _, mount, _ = _layout(tmp_path)
    cloud_storage.save_config(cloud_dir, {"mount_path": str(mount)})
    status = cloud_storage.status(cloud_dir)
    assert status["configured"] is True
    assert status["mount_path"] == str(mount)


def test_cloud_sync_copies_artefacts_via_port(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    sync_port = open_sync_port_for_cloud(cloud_dir.parent)
    result = cloud_storage.sync_project(
        plugin_data_dir=cloud_dir,
        sync_port=sync_port,
        project_id=project_id,
        mount_path=str(mount),
    )
    assert "contrat.docx" in result["synced"]
    copied = mount / "projects" / project_id / "contrat.docx"
    assert copied.is_file()
    assert copied.read_text(encoding="utf-8") == "contenu"


def test_cloud_sync_requires_configuration(tmp_path: Path) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    sync_port = open_sync_port_for_cloud(cloud_dir.parent)
    with pytest.raises(ValueError, match="cloud_not_configured"):
        cloud_storage.sync_project(
            plugin_data_dir=cloud_dir,
            sync_port=sync_port,
            project_id=project_id,
        )


def test_cloud_http_endpoints(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    with TestClient(mainmod.app) as client:
        config_resp = client.post(
            "/plugins/cloud/config",
            json={
                "plugin_data_dir": str(cloud_dir),
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert config_resp.status_code == 200
        assert config_resp.json()["ok"] is True

        status_resp = client.get(
            "/plugins/cloud/status",
            params={"plugin_data_dir": str(cloud_dir)},
            headers=INTERNAL_HEADERS,
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["configured"] is True

        sync_resp = client.post(
            "/plugins/cloud/sync",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert sync_resp.status_code == 200
        assert "contrat.docx" in sync_resp.json()["synced"]


def test_cloud_status_reports_not_enrolled_when_jwt_exchange_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud_dir, _, _, _ = _layout(tmp_path)
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

    async def fake_ensure(self) -> bool:
        return False

    monkeypatch.setattr(CloudControlPlaneClient, "ensure_durable_device_bearer", fake_ensure)

    with TestClient(mainmod.app) as client:
        status_resp = client.get(
            "/plugins/cloud/status",
            params={"plugin_data_dir": str(cloud_dir)},
            headers=INTERNAL_HEADERS,
        )

    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["enrolled"] is False
    assert body["has_token"] is False


def test_cloud_sync_http_forbidden_without_project_sync(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.plugins.workproba_cloud import sync_access

    def deny_port(_plugins_root: Path):
        raise PermissionError("Missing permission: project:sync")

    monkeypatch.setattr(sync_access, "open_sync_port_for_cloud", deny_port)

    cloud_dir, _, mount, project_id = _layout(tmp_path)
    with TestClient(mainmod.app) as client:
        sync_resp = client.post(
            "/plugins/cloud/sync",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert sync_resp.status_code == 403
        assert "project:sync" in sync_resp.json()["detail"]


@pytest.mark.asyncio
async def test_sync_to_cloud_syncs_mount_without_enrollment(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent

    cloud_storage.save_config(cloud_dir, {"mount_path": str(mount)})

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id=project_id,
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["sync_to_cloud"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")

    result = await tool.function(ctx, project_id=project_id)

    assert "contrat.docx" in result["synced"]
    assert (mount / "projects" / project_id / "contrat.docx").is_file()


@pytest.mark.asyncio
async def test_sync_to_cloud_rejected_when_enrolled(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent

    cloud_storage.save_config(
        cloud_dir,
        {"mount_path": str(mount), "base_url": "https://cloud.example.test"},
    )
    _enroll_cloud_dir(cloud_dir)

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id=project_id,
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["sync_to_cloud"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")

    with pytest.raises(ModelRetry, match="source de vérité"):
        await tool.function(ctx, project_id=project_id)


@pytest.mark.asyncio
async def test_sync_to_cloud_without_mount_when_enrolled(tmp_path: Path) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent

    _enroll_cloud_dir(cloud_dir)

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id=project_id,
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["sync_to_cloud"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")

    with pytest.raises(ModelRetry, match="source de vérité"):
        await tool.function(ctx, project_id=project_id)


@pytest.mark.asyncio
async def test_sync_from_cloud_rejected_when_enrolled(tmp_path: Path) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent

    _enroll_cloud_dir(cloud_dir)

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id=project_id,
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["sync_from_cloud"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc2")

    with pytest.raises(ModelRetry, match="source de vérité"):
        await tool.function(ctx, project_id=project_id)


@pytest.mark.asyncio
async def test_verify_skip_when_blob_missing(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent

    cloud_storage.save_config(cloud_dir, {"mount_path": str(mount)})

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id=project_id,
            session_id="s1",
            documents=[],
            plugin_data_dir=plugins_root,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["sync_to_cloud"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc3")

    result = await tool.function(ctx, project_id=project_id)

    assert "contrat.docx" in result["synced"]
    assert (mount / "projects" / project_id / "contrat.docx").is_file()


def test_version_bump_on_republish(tmp_path: Path) -> None:
    _, projet_dir, _, project_id = _layout(tmp_path)
    workspace = tmp_path / "workspace"
    listed = projet_storage.list_artefacts(projet_dir, project_id)
    assert listed[0]["version"] == "1.0.0"
    second = projet_storage.publish_artifact(
        plugin_data_dir=projet_dir,
        workspace_root=workspace,
        source_path="contrat.docx",
        project_id=project_id,
        name="contrat.docx",
    )
    assert second["version"] == "1.0.1"
    listed_after = projet_storage.list_artefacts(projet_dir, project_id)
    assert listed_after[0]["version"] == "1.0.1"


@pytest.mark.asyncio
async def test_pull_skips_cache_up_to_date_with_reason(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.plugins.workproba_cloud.cache_service import write_artefact_to_cache

    cloud_dir, projet_dir, _, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent
    artefact_db_id = 77

    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.example.test"})
    with (cloud_dir / "config.json").open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["tokens"] = {"access_token": "sync-token", "token_type": "bearer"}
    with (cloud_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)

    write_artefact_to_cache(
        cloud_dir,
        project_id=project_id,
        artefact_id="contrat.docx",
        version="1.0.0",
        filename="contrat.docx",
        content=b"contenu",
    )

    def cp_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sync/artefacts" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": artefact_db_id,
                            "projectId": project_id,
                            "artifactId": "contrat.docx",
                            "version": "1.0.0",
                            "filename": "contrat.docx",
                            "checksum": "sha256:deadbeef",
                            "size": 8,
                            "confirmedAt": "2026-06-01T12:00:00.000Z",
                        }
                    ]
                },
            )
        return httpx.Response(404)

    cp_http_client = httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=httpx.MockTransport(cp_handler),
    )

    original_init = CloudControlPlaneClient.__init__

    def patched_init(
        self,
        *,
        base_url: str,
        plugin_data_dir: Path,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is None and base_url == "https://cloud.example.test":
            http_client = cp_http_client
        original_init(
            self,
            base_url=base_url,
            plugin_data_dir=plugin_data_dir,
            http_client=http_client,
        )

    monkeypatch.setattr(CloudControlPlaneClient, "__init__", patched_init)

    from app.plugins.workproba_cloud.sync_service import pull_project_artefacts_from_cloud

    sync_port = open_sync_port_for_cloud(plugins_root)
    client = CloudControlPlaneClient(base_url="https://cloud.example.test", plugin_data_dir=cloud_dir)

    try:
        result = await pull_project_artefacts_from_cloud(
            cloud_dir=cloud_dir,
            sync_port=sync_port,
            project_id=project_id,
            client=client,
        )
    finally:
        await cp_http_client.aclose()

    assert result["pulled"] == []
    assert result["skipped"] == ["contrat.docx:cache_up_to_date"]
    assert result["errors"] == []
    assert (projet_dir / "artefacts" / project_id / "contrat.docx").read_text(encoding="utf-8") == "contenu"


@pytest.mark.asyncio
async def test_pull_reports_checksum_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cloud_dir, projet_dir, _, project_id = _layout(tmp_path)
    plugins_root = cloud_dir.parent
    artefact_db_id = 88

    cloud_storage.save_config(cloud_dir, {"base_url": "https://cloud.example.test"})
    with (cloud_dir / "config.json").open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config["tokens"] = {"access_token": "sync-token", "token_type": "bearer"}
    with (cloud_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)

    def cp_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sync/artefacts" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": artefact_db_id,
                            "projectId": project_id,
                            "artifactId": "cloud-note.md",
                            "version": "2.0.0",
                            "filename": "cloud-note.md",
                            "checksum": "sha256:deadbeef",
                            "size": 13,
                            "confirmedAt": "2026-06-01T12:00:00.000Z",
                        }
                    ]
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/download-url":
            return httpx.Response(
                200,
                json={
                    "url": "https://blob.example.test/download/cloud-note.md",
                    "storageKey": "sync/key",
                    "expiresAt": "2026-07-15T21:40:00.000Z",
                },
            )
        return httpx.Response(404)

    def blob_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"cloud-content")

    cp_http_client = httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=httpx.MockTransport(cp_handler),
    )
    blob_http_client = httpx.AsyncClient(transport=httpx.MockTransport(blob_handler))

    original_init = CloudControlPlaneClient.__init__

    def patched_init(
        self,
        *,
        base_url: str,
        plugin_data_dir: Path,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is None and base_url == "https://cloud.example.test":
            http_client = cp_http_client
        original_init(
            self,
            base_url=base_url,
            plugin_data_dir=plugin_data_dir,
            http_client=http_client,
        )

    async def patched_get(self, url: str) -> bytes:
        response = await blob_http_client.get(url)
        response.raise_for_status()
        return response.content

    monkeypatch.setattr(CloudControlPlaneClient, "__init__", patched_init)
    monkeypatch.setattr(CloudControlPlaneClient, "get_presigned_blob", patched_get)

    from app.plugins.workproba_cloud.sync_service import pull_project_artefacts_from_cloud

    sync_port = open_sync_port_for_cloud(plugins_root)
    client = CloudControlPlaneClient(base_url="https://cloud.example.test", plugin_data_dir=cloud_dir)

    try:
        result = await pull_project_artefacts_from_cloud(
            cloud_dir=cloud_dir,
            sync_port=sync_port,
            project_id=project_id,
            client=client,
        )
    finally:
        await cp_http_client.aclose()
        await blob_http_client.aclose()

    assert result["pulled"] == []
    assert result["errors"] == ["cloud-note.md:checksum_mismatch"]
    assert not (projet_dir / "artefacts" / project_id / "cloud-note.md").exists()
    assert not (cloud_dir / "cache" / project_id / "cloud-note.md").exists()


def test_cloud_publish_direct_and_list(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cloud_dir, projet_dir, _, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)

    artefact_db_id = 101
    stored_items: list[dict[str, object]] = []
    put_calls: list[httpx.Request] = []

    def cp_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sync/artefacts" and request.method == "GET":
            return httpx.Response(200, json={"items": stored_items})
        if request.url.path == "/sync/artefacts" and request.method == "POST":
            body = json.loads(request.content.decode())
            item = {
                **body,
                "id": artefact_db_id,
                "confirmedAt": None,
                "createdAt": "2026-07-16T12:00:00.000Z",
            }
            stored_items.append(item)
            return httpx.Response(200, json=item)
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/verify-blob":
            return httpx.Response(
                200,
                json={
                    "id": artefact_db_id,
                    "blobExists": False,
                    "confirmedAt": None,
                    "staleCleared": False,
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/upload-url":
            return httpx.Response(
                200,
                json={
                    "url": "https://blob.example.test/upload/note.md",
                    "storageKey": f"sync/{project_id}/note.md",
                    "expiresAt": "2026-07-16T21:40:00.000Z",
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/confirm":
            stored_items[0]["confirmedAt"] = "2026-07-16T12:01:00.000Z"
            return httpx.Response(200, json=stored_items[0])
        return httpx.Response(404)

    def blob_handler(request: httpx.Request) -> httpx.Response:
        put_calls.append(request)
        return httpx.Response(200)

    cp_http_client = httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=httpx.MockTransport(cp_handler),
    )
    blob_http_client = httpx.AsyncClient(transport=httpx.MockTransport(blob_handler))

    original_init = CloudControlPlaneClient.__init__
    original_put = CloudControlPlaneClient.put_presigned_blob

    def patched_init(
        self,
        *,
        base_url: str,
        plugin_data_dir: Path,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is None and base_url == "https://cloud.example.test":
            http_client = cp_http_client
        original_init(
            self,
            base_url=base_url,
            plugin_data_dir=plugin_data_dir,
            http_client=http_client,
        )

    async def patched_put(
        self,
        *,
        url: str,
        content: bytes,
        content_type: str | None = None,
        _put_client: httpx.AsyncClient | None = None,
    ) -> None:
        await original_put(
            self,
            url=url,
            content=content,
            content_type=content_type,
            _put_client=blob_http_client,
        )

    monkeypatch.setattr(CloudControlPlaneClient, "__init__", patched_init)
    monkeypatch.setattr(CloudControlPlaneClient, "put_presigned_blob", patched_put)

    with TestClient(mainmod.app) as client:
        publish_resp = client.post(
            "/plugins/cloud/artefacts/publish",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "name": "note.md",
                "content": "# Hello cloud",
            },
            headers=INTERNAL_HEADERS,
        )
        assert publish_resp.status_code == 200
        artefact = publish_resp.json()["artefact"]
        assert artefact["id"] == "note.md"
        assert artefact["version"] == "1.0.0"
        assert artefact["cloud_confirmed"] is True

        list_resp = client.get(
            "/plugins/cloud/artefacts",
            params={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
            },
            headers=INTERNAL_HEADERS,
        )
        assert list_resp.status_code == 200
        listed = list_resp.json()["artefacts"]
        assert len(listed) == 1
        assert listed[0]["id"] == "note.md"
        assert listed[0]["cloud_confirmed"] is True

    assert len(put_calls) == 1
    assert not (projet_dir / "artefacts" / project_id / "note.md").exists()


@pytest.mark.asyncio
async def test_cloud_open_artefact_writes_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)
    artefact_db_id = 201

    def cp_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sync/artefacts" and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": artefact_db_id,
                            "projectId": project_id,
                            "artifactId": "note.md",
                            "version": "1.2.0",
                            "filename": "note.md",
                            "checksum": "sha256:bb13d809c46ac7abbe1b7fed4744a6f9c85c6cb94306fa47745fecd9dccd5d5c",
                            "size": 13,
                            "confirmedAt": "2026-07-16T12:00:00.000Z",
                        }
                    ]
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/download-url":
            return httpx.Response(
                200,
                json={
                    "url": "https://blob.example.test/download/note.md",
                    "storageKey": "sync/key",
                    "expiresAt": "2026-07-16T21:40:00.000Z",
                },
            )
        return httpx.Response(404)

    def blob_handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, content=b"cloud-content")

    cp_http_client = httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=httpx.MockTransport(cp_handler),
    )
    blob_http_client = httpx.AsyncClient(transport=httpx.MockTransport(blob_handler))

    original_init = CloudControlPlaneClient.__init__

    def patched_init(
        self,
        *,
        base_url: str,
        plugin_data_dir: Path,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is None and base_url == "https://cloud.example.test":
            http_client = cp_http_client
        original_init(
            self,
            base_url=base_url,
            plugin_data_dir=plugin_data_dir,
            http_client=http_client,
        )

    async def patched_get(self, url: str) -> bytes:
        response = await blob_http_client.get(url)
        response.raise_for_status()
        return response.content

    monkeypatch.setattr(CloudControlPlaneClient, "__init__", patched_init)
    monkeypatch.setattr(CloudControlPlaneClient, "get_presigned_blob", patched_get)

    with TestClient(mainmod.app) as client:
        open_resp = client.post(
            "/plugins/cloud/artefacts/open",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "artefact_id": "note.md",
            },
            headers=INTERNAL_HEADERS,
        )
        assert open_resp.status_code == 200
        payload = open_resp.json()
        assert payload["artefact_id"] == "note.md"
        assert payload["version"] == "1.2.0"
        assert payload["filename"] == "note.md"
        cached = Path(payload["local_path"])
        assert cached.is_file()
        assert cached.read_bytes() == b"cloud-content"
        assert cached == cloud_dir / "cache" / project_id / "note.md" / "v1.2.0" / "note.md"

        second_resp = client.post(
            "/plugins/cloud/artefacts/open",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "artefact_id": "note.md",
            },
            headers=INTERNAL_HEADERS,
        )
        assert second_resp.status_code == 200
        assert second_resp.json()["local_path"] == payload["local_path"]

    await cp_http_client.aclose()
    await blob_http_client.aclose()


@pytest.mark.asyncio
async def test_cloud_republish_from_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)
    artefact_db_id = 401

    stored_items, put_calls = _patch_cloud_control_plane(
        monkeypatch,
        project_id=project_id,
        artefact_db_id=artefact_db_id,
    )
    stored_items.append(
        {
            "id": artefact_db_id,
            "projectId": project_id,
            "artifactId": "note.md",
            "version": "1.2.0",
            "filename": "note.md",
            "checksum": "sha256:old",
            "size": 13,
            "confirmedAt": "2026-07-16T12:00:00.000Z",
        }
    )

    cache_path = cloud_dir / "cache" / project_id / "note.md" / "v1.2.0" / "note.md"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(b"edited-local")

    with TestClient(mainmod.app) as client:
        republish_resp = client.post(
            "/plugins/cloud/artefacts/republish",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "artefact_id": "note.md",
            },
            headers=INTERNAL_HEADERS,
        )
        assert republish_resp.status_code == 200
        artefact = republish_resp.json()["artefact"]
        assert artefact["id"] == "note.md"
        assert artefact["version"] == "1.2.1"
        assert artefact["cloud_confirmed"] is True

        missing_resp = client.post(
            "/plugins/cloud/artefacts/republish",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "artefact_id": "missing.md",
            },
            headers=INTERNAL_HEADERS,
        )
        assert missing_resp.status_code == 400

    assert len(put_calls) == 1
    assert put_calls[0].content == b"edited-local"


def _patch_cloud_control_plane(
    monkeypatch: pytest.MonkeyPatch,
    *,
    project_id: str,
    artefact_db_id: int = 301,
) -> tuple[list[dict[str, object]], list[httpx.Request]]:
    stored_items: list[dict[str, object]] = []
    put_calls: list[httpx.Request] = []

    def cp_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sync/artefacts" and request.method == "GET":
            return httpx.Response(200, json={"items": stored_items})
        if request.url.path == "/sync/artefacts" and request.method == "POST":
            body = json.loads(request.content.decode())
            item = {
                **body,
                "id": artefact_db_id,
                "confirmedAt": None,
                "createdAt": "2026-07-16T12:00:00.000Z",
            }
            stored_items.append(item)
            return httpx.Response(200, json=item)
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/verify-blob":
            return httpx.Response(
                200,
                json={
                    "id": artefact_db_id,
                    "blobExists": False,
                    "confirmedAt": None,
                    "staleCleared": False,
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/upload-url":
            return httpx.Response(
                200,
                json={
                    "url": "https://blob.example.test/upload/routed.md",
                    "storageKey": f"sync/{project_id}/routed.md",
                    "expiresAt": "2026-07-16T21:40:00.000Z",
                },
            )
        if request.url.path == f"/sync/artefacts/{artefact_db_id}/confirm":
            stored_items[0]["confirmedAt"] = "2026-07-16T12:01:00.000Z"
            return httpx.Response(200, json=stored_items[0])
        return httpx.Response(404)

    def blob_handler(request: httpx.Request) -> httpx.Response:
        put_calls.append(request)
        return httpx.Response(200)

    cp_http_client = httpx.AsyncClient(
        base_url="https://cloud.example.test",
        transport=httpx.MockTransport(cp_handler),
    )
    blob_http_client = httpx.AsyncClient(transport=httpx.MockTransport(blob_handler))

    original_init = CloudControlPlaneClient.__init__
    original_put = CloudControlPlaneClient.put_presigned_blob

    def patched_init(
        self,
        *,
        base_url: str,
        plugin_data_dir: Path,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if http_client is None and base_url == "https://cloud.example.test":
            http_client = cp_http_client
        original_init(
            self,
            base_url=base_url,
            plugin_data_dir=plugin_data_dir,
            http_client=http_client,
        )

    async def patched_put(
        self,
        *,
        url: str,
        content: bytes,
        content_type: str | None = None,
        _put_client: httpx.AsyncClient | None = None,
    ) -> None:
        await original_put(
            self,
            url=url,
            content=content,
            content_type=content_type,
            _put_client=blob_http_client,
        )

    monkeypatch.setattr(CloudControlPlaneClient, "__init__", patched_init)
    monkeypatch.setattr(CloudControlPlaneClient, "put_presigned_blob", patched_put)
    return stored_items, put_calls


def test_projet_publish_http_routes_to_cloud_when_enrolled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cloud_dir, projet_dir, _, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)
    _, put_calls = _patch_cloud_control_plane(monkeypatch, project_id=project_id)

    with TestClient(mainmod.app) as client:
        publish_resp = client.post(
            "/plugins/projet/publish",
            json={
                "plugin_data_dir": str(projet_dir),
                "project_id": project_id,
                "name": "routed.md",
                "content": "# Routed via projet publish",
            },
            headers=INTERNAL_HEADERS,
        )
        assert publish_resp.status_code == 200
        artefact = publish_resp.json()["artefact"]
        assert artefact["id"] == "routed.md"
        assert artefact["cloud_confirmed"] is True

    assert len(put_calls) == 1
    assert not (projet_dir / "artefacts" / project_id / "routed.md").exists()


@pytest.mark.asyncio
async def test_publish_artifact_tool_routes_to_cloud_when_enrolled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.plugins.workproba_projet import PLUGIN_ID

    cloud_dir, projet_dir, _, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)
    _, put_calls = _patch_cloud_control_plane(monkeypatch, project_id=project_id)

    deps = ToolDeps(
        context=ToolContext(
            tenant_id="t",
            project_id="p",
            session_id="s1",
            documents=[],
            plugin_data_dir=projet_dir,
            locale="fr",
        ),
        project_client=FakeProjectClient(),
        sandbox_runner=SandboxRunner(timeout_seconds=30, limits=DEFAULT_LIMITS),
        limits=DEFAULT_LIMITS,
        confirmation_gate=None,
    )
    agent = build_agent(TestModel(), active_plugins=[PLUGIN_ID, PLUGIN_WORKPROBA_CLOUD])
    tool = agent._function_toolset.tools["publish_artifact"]
    ctx = RunContext(deps=deps, model=TestModel(), usage=None, prompt=None, tool_call_id="tc1")

    result = await tool.function(
        ctx,
        project_id=project_id,
        name="tool-routed.md",
        source_path="",
        content="# Tool routed to cloud",
    )
    assert result["id"] == "tool-routed.md"
    assert result["cloud_confirmed"] is True
    assert len(put_calls) == 1
    assert not (projet_dir / "artefacts" / project_id / "tool-routed.md").exists()


def test_cloud_sync_http_rejected_when_enrolled(tmp_path: Path) -> None:
    cloud_dir, _, mount, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)
    cloud_storage.save_config(cloud_dir, {"mount_path": str(mount)})

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/sync",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
                "mount_path": str(mount),
            },
            headers=INTERNAL_HEADERS,
        )
        assert resp.status_code == 400
        assert "source de vérité" in resp.json()["detail"]


def test_cloud_pull_http_rejected_when_enrolled(tmp_path: Path) -> None:
    cloud_dir, _, _, project_id = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/pull",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": project_id,
            },
            headers=INTERNAL_HEADERS,
        )
        assert resp.status_code == 400
        assert "source de vérité" in resp.json()["detail"]


def test_cache_service_rejects_path_traversal(tmp_path: Path) -> None:
    from app.plugins.workproba_cloud.cache_service import (
        cache_artefact_path,
        find_cached_artefact_path,
    )

    cloud_dir = tmp_path / "cloud"
    cloud_dir.mkdir()
    with pytest.raises(ValueError, match="invalid_project_id"):
        cache_artefact_path(
            cloud_dir,
            project_id="../escape",
            artifact_id="doc.md",
            version="1.0.0",
            filename="doc.md",
        )
    with pytest.raises(ValueError, match="invalid_artifact_id"):
        cache_artefact_path(
            cloud_dir,
            project_id="p1",
            artifact_id="..\\evil",
            version="1.0.0",
            filename="doc.md",
        )

    cache_root = cloud_dir / "cache" / "p1" / "doc.md" / "v1.0.0"
    cache_root.mkdir(parents=True)
    valid = cache_root / "doc.md"
    valid.write_text("ok", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("nope", encoding="utf-8")

    with pytest.raises(ValueError, match="cache_path_outside_cache"):
        find_cached_artefact_path(
            cloud_dir,
            project_id="p1",
            artefact_id="doc.md",
            cache_path=str(outside),
        )


def test_cloud_publish_rejects_missing_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cloud_dir, _, _, _ = _layout(tmp_path)
    _enroll_cloud_dir(cloud_dir)
    _patch_cloud_control_plane(monkeypatch, project_id="missing-project")

    with TestClient(mainmod.app) as client:
        resp = client.post(
            "/plugins/cloud/artefacts/publish",
            json={
                "plugin_data_dir": str(cloud_dir),
                "project_id": "missing-project",
                "name": "note.md",
                "content": "# Hello",
            },
            headers=INTERNAL_HEADERS,
        )
        assert resp.status_code == 404

