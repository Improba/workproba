"""Tests for workspace space policy (approval mode)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.space_policy import (
    DEFAULT_APPROVAL_MODE,
    load_approval_mode,
    policy_path,
    set_approval_mode,
)


def test_load_default_when_file_missing(tmp_path: Path) -> None:
    assert load_approval_mode(tmp_path) == DEFAULT_APPROVAL_MODE


def test_set_and_persist_trust_mode(tmp_path: Path) -> None:
    mode = set_approval_mode(tmp_path, "trust")
    assert mode == "trust"
    assert load_approval_mode(tmp_path) == "trust"

    on_disk = json.loads(policy_path(tmp_path).read_text(encoding="utf-8"))
    assert on_disk == {"version": 1, "approvalMode": "trust"}


def test_set_security_mode(tmp_path: Path) -> None:
    set_approval_mode(tmp_path, "trust")
    mode = set_approval_mode(tmp_path, "security")
    assert mode == "security"
    assert load_approval_mode(tmp_path) == "security"


def test_invalid_mode_falls_back_to_security(tmp_path: Path) -> None:
    policy_path(tmp_path).write_text(
        json.dumps({"version": 1, "approvalMode": "unknown"}),
        encoding="utf-8",
    )
    assert load_approval_mode(tmp_path) == "security"


def test_set_invalid_mode_writes_security(tmp_path: Path) -> None:
    mode = set_approval_mode(tmp_path, "bogus")  # type: ignore[arg-type]
    assert mode == "security"
    assert load_approval_mode(tmp_path) == "security"


@pytest.mark.parametrize("bad_payload", ['{"version":1}', "[]", "null", "not-json"])
def test_corrupt_file_falls_back_to_security(
    tmp_path: Path,
    bad_payload: str,
) -> None:
    policy_path(tmp_path).write_text(bad_payload, encoding="utf-8")
    assert load_approval_mode(tmp_path) == "security"


def test_workspace_policy_api_roundtrip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.auth as authmod
    from fastapi.testclient import TestClient

    import app.main as mainmod

    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    with TestClient(mainmod.app) as client:
        headers = {"X-Internal-Secret": "desktop-dev-secret"}
        get_resp = client.get(
            "/workspace/policy",
            params={"workspace_data_dir": str(tmp_path)},
            headers=headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json() == {"approvalMode": "security"}

        put_resp = client.put(
            "/workspace/policy",
            headers=headers,
            json={
                "workspace_data_dir": str(tmp_path),
                "approval_mode": "trust",
            },
        )
        assert put_resp.status_code == 200
        assert put_resp.json() == {"approvalMode": "trust"}

        get_resp2 = client.get(
            "/workspace/policy",
            params={"workspace_data_dir": str(tmp_path)},
            headers=headers,
        )
        assert get_resp2.json() == {"approvalMode": "trust"}
