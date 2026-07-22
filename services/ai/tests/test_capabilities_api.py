"""Tests for space capabilities API view + wanted updates."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.capabilities_api import (
    apply_wanted_updates,
    build_space_capabilities_view,
)
from app.capabilities_profile import ensure_initialized, set_wanted


LOCAL_IDS = frozenset(
    {"workproba_cloud", "projects", "regards", "web_navigation"}
)


def _view(
    tmp_path: Path,
    *,
    wanted: dict[str, bool] | None = None,
    cloud_entitled: bool = True,
    allowlist: frozenset[str] = frozenset({"ihora"}),
    disabled: frozenset[str] = frozenset(),
):
    ensure_initialized(tmp_path, sorted(LOCAL_IDS | {f"managed:{c}" for c in allowlist}))
    if wanted is not None:
        set_wanted(tmp_path, wanted)
    from app.capabilities_profile import load

    profile = load(tmp_path)
    assert profile is not None
    return build_space_capabilities_view(
        profile,
        machine_entitled_local_ids=LOCAL_IDS,
        cloud_plugin_entitled=cloud_entitled,
        cloud_allowlist=allowlist,
        disabled_managed_connectors=disabled,
    )


def test_active_when_wanted_and_entitled(tmp_path: Path) -> None:
    view = _view(
        tmp_path,
        wanted={
            "workproba_cloud": True,
            "projects": True,
            "regards": False,
            "web_navigation": False,
        },
    )
    by_id = {item.id: item for item in view.items}
    assert by_id["workproba_cloud"].status == "active"
    assert by_id["projects"].status == "active"
    assert by_id["regards"].status == "available"
    assert "projects" in view.effective_ids


def test_nested_unavailable_when_cloud_wanted_off_preserves_wanted(
    tmp_path: Path,
) -> None:
    view = _view(
        tmp_path,
        wanted={
            "workproba_cloud": False,
            "projects": True,
            "managed:ihora": True,
            "regards": True,
        },
    )
    by_id = {item.id: item for item in view.items}
    assert by_id["projects"].status == "unavailable"
    assert by_id["projects"].wanted is True
    assert by_id["projects"].unavailable_reason == "parent_cloud_off"
    assert by_id["managed:ihora"].status == "unavailable"
    assert by_id["managed:ihora"].wanted is True
    assert by_id["regards"].status == "active"
    assert "projects" not in view.effective_ids


def test_auto_want_cloud_parent_on_nested_enable(tmp_path: Path) -> None:
    ensure_initialized(tmp_path, sorted(LOCAL_IDS))
    set_wanted(
        tmp_path,
        {"workproba_cloud": False, "projects": False, "regards": True},
    )
    updated = apply_wanted_updates(tmp_path, {"projects": True})
    assert updated.wanted["projects"] is True
    assert updated.wanted["workproba_cloud"] is True


def test_http_get_put_workspace_capabilities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)
    ensure_initialized(tmp_path, sorted(LOCAL_IDS))

    with TestClient(mainmod.app) as client:
        headers = {"X-Internal-Secret": "desktop-dev-secret"}
        get_resp = client.get(
            "/workspace/capabilities",
            params={
                "workspace_data_dir": str(tmp_path),
                "active_plugins": [
                    "workproba.cloud",
                    "workproba.projet",
                    "workproba.personas",
                    "workproba.browser",
                ],
            },
            headers=headers,
        )
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "wanted" in body
        assert "items" in body

        put_resp = client.put(
            "/workspace/capabilities",
            headers=headers,
            json={
                "workspace_data_dir": str(tmp_path),
                "wanted": {"projects": True, "web_navigation": True},
                "active_plugins": [
                    "workproba.cloud",
                    "workproba.projet",
                    "workproba.personas",
                    "workproba.browser",
                ],
            },
        )
        assert put_resp.status_code == 200
        put_body = put_resp.json()
        assert put_body["wanted"]["projects"] is True
        assert put_body["wanted"]["web_navigation"] is True
        # Nested enable auto-wants parent.
        assert put_body["wanted"]["workproba_cloud"] is True
