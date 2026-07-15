"""Tests ManagedRegardsPort (T-V3-CP-2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.plugins.ports.managed_regards import (
    MANAGED_REGARDS_PERMISSION,
    CATALOG_FILE,
    FilesystemManagedRegardsPort,
    SignatureVerifier,
    clear_managed_audit_log,
    create_personas_managed_port,
    managed_audit_log,
    open_managed_regards_port,
    sign_bundle_for_tests,
)
from app.plugins.registry import PLUGIN_WORKPROBA_CLOUD, PLUGIN_WORKPROBA_PERSONAS
from app.plugins.workproba_personas import storage as personas_storage


def _sample_personas() -> list[dict[str, str]]:
    return [
        {
            "id": "m01",
            "name": "Compliance",
            "role": "Conformité",
            "description": "Regard conformité",
            "system_prompt": "Tu es conformité.",
            "avatar_color": "#336699",
            "avatar_icon": "shield",
        }
    ]


def _personas_layout(tmp_path: Path) -> tuple[Path, Path]:
    plugins_root = tmp_path / "app_data" / "plugins"
    personas_dir = plugins_root / PLUGIN_WORKPROBA_PERSONAS
    personas_dir.mkdir(parents=True)
    return plugins_root, personas_dir


def test_install_verify_activate_and_status(tmp_path: Path) -> None:
    clear_managed_audit_log()
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="eti-regards",
        version="1.0.0",
        name="Regards ETI",
        personas=_sample_personas(),
    )

    installed = port.install_catalog_version(bundle)
    assert installed["installed"] is True
    catalog_path = personas_dir / "managed" / "eti-regards" / "1.0.0" / CATALOG_FILE
    assert catalog_path.is_file()

    activated = port.activate_catalog("eti-regards")
    assert activated["active"] is True
    status = port.get_catalog_status()
    assert status["active"] is True
    assert status["catalog_id"] == "eti-regards"

    catalogs = port.list_managed_catalogs()
    assert len(catalogs) == 1
    assert catalogs[0]["active"] is True

    active_set = port.active_persona_set()
    assert active_set is not None
    assert active_set["provenance"] == "managed"
    sets = personas_storage.list_sets(personas_dir)
    assert any(s.get("id") == "managed_eti-regards" for s in sets)


def test_verify_signature_rejects_invalid_bundle(tmp_path: Path) -> None:
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="eti-regards",
        version="1.0.0",
        name="Regards ETI",
        personas=_sample_personas(),
    )
    tampered = bundle.to_dict()
    tampered["signature"] = "invalid"
    assert port.verify_signature(tampered) is False
    with pytest.raises(ValueError, match="invalid_signature"):
        port.install_catalog_version(tampered)


def test_hmac_sha256_signature_roundtrip(tmp_path: Path) -> None:
    _, personas_dir = _personas_layout(tmp_path)
    secret = "dGVzdC1zZWNyZXQ="
    verifier = SignatureVerifier(hmac_secret_b64=secret)
    port = FilesystemManagedRegardsPort(
        personas_data_dir=personas_dir,
        caller_plugin_id=PLUGIN_WORKPROBA_PERSONAS,
        app_data_dir=tmp_path / "app_data",
        verifier=verifier,
    )
    bundle = sign_bundle_for_tests(
        catalog_id="hmac-cat",
        version="0.1.0",
        name="HMAC catalog",
        personas=_sample_personas(),
        algorithm="hmac-sha256",
        hmac_secret_b64=secret,
    )
    assert port.verify_signature(bundle) is True
    port.install_catalog_version(bundle)


def test_remove_revoked_version_and_cloud_namespace_isolation(tmp_path: Path) -> None:
    clear_managed_audit_log()
    plugins_root, personas_dir = _personas_layout(tmp_path)
    cloud_dir = plugins_root / PLUGIN_WORKPROBA_CLOUD
    cloud_dir.mkdir()
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="eti-regards",
        version="1.0.0",
        name="Regards ETI",
        personas=_sample_personas(),
    )
    port.install_catalog_version(bundle)
    port.activate_catalog("eti-regards")

    cloud_port = open_managed_regards_port(
        caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
        caller_permissions=frozenset({MANAGED_REGARDS_PERMISSION}),
        plugins_root=plugins_root,
    )
    assert cloud_port.list_managed_catalogs()

    assert port.remove_revoked_version("eti-regards", "1.0.0") is True
    assert not (personas_dir / "managed" / "eti-regards" / "1.0.0").exists()
    assert port.get_catalog_status()["active"] is False

    # Cloud plugin must not write into its own namespace for managed catalogs.
    assert not (cloud_dir / "managed").exists()

    audit = managed_audit_log()
    callers = {entry["caller"] for entry in audit}
    assert PLUGIN_WORKPROBA_PERSONAS in callers
    assert PLUGIN_WORKPROBA_CLOUD in callers


def test_personas_managed_http_endpoints(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    import app.auth as authmod
    import app.main as mainmod

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(authmod, "is_loopback_host", lambda host: True)

    _, personas_dir = _personas_layout(tmp_path)
    bundle = sign_bundle_for_tests(
        catalog_id="http-cat",
        version="1.0.0",
        name="HTTP Catalog",
        personas=_sample_personas(),
    )
    with TestClient(mainmod.app) as client:
        list_resp = client.get(
            "/plugins/personas/managed",
            params={"plugin_data_dir": str(personas_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["catalogs"] == []

        install_resp = client.post(
            "/plugins/personas/managed/install",
            json={
                "plugin_data_dir": str(personas_dir),
                "signed_bundle": bundle.to_dict(),
            },
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert install_resp.status_code == 200

        activate_resp = client.post(
            "/plugins/personas/managed/http-cat/activate",
            json={"plugin_data_dir": str(personas_dir), "catalog_id": "http-cat"},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert activate_resp.status_code == 200

        delete_resp = client.delete(
            "/plugins/personas/managed/http-cat/1.0.0",
            params={"plugin_data_dir": str(personas_dir)},
            headers={"X-Internal-Secret": "desktop-dev-secret"},
        )
        assert delete_resp.status_code == 200
    monkeypatch.undo()


def test_open_managed_regards_port_requires_permission(tmp_path: Path) -> None:
    plugins_root, _ = _personas_layout(tmp_path)
    with pytest.raises(PermissionError, match=MANAGED_REGARDS_PERMISSION):
        open_managed_regards_port(
            caller_plugin_id=PLUGIN_WORKPROBA_CLOUD,
            caller_permissions=frozenset({"storage:namespace"}),
            plugins_root=plugins_root,
        )


def test_verify_fails_without_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKPROBA_REGARDS_PUBLIC_KEY_B64", raising=False)
    monkeypatch.delenv("WORKPROBA_ALLOW_TEST_REGARDS_KEYS", raising=False)
    verifier = SignatureVerifier(allow_test_keys=False)
    bundle = sign_bundle_for_tests(
        catalog_id="no-key-cat",
        version="1.0.0",
        name="No key",
        personas=_sample_personas(),
    )
    assert verifier.verify(bundle.to_dict()) is False


def test_hmac_verify_ignores_embedded_payload_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKPROBA_REGARDS_PUBLIC_KEY_B64", raising=False)
    secret = "dGVzdC1zZWNyZXQ="
    verifier = SignatureVerifier(allow_test_keys=False)
    bundle = sign_bundle_for_tests(
        catalog_id="forged-hmac",
        version="0.1.0",
        name="Forged HMAC",
        personas=_sample_personas(),
        algorithm="hmac-sha256",
        hmac_secret_b64=secret,
    )
    payload = bundle.to_dict()
    payload["hmac_secret_b64"] = secret
    assert verifier.verify(payload) is False
    assert "hmac_secret_b64" not in bundle.to_dict()
