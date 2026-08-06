"""Tests ManagedRegardsPort (T-V3-CP-2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.plugins.ports.managed_regards import (
    MANAGED_REGARDS_PERMISSION,
    CATALOG_FILE,
    FilesystemManagedRegardsPort,
    SignatureVerifier,
    SignedBundle,
    clear_managed_audit_log,
    create_personas_managed_port,
    dual_read_catalog_entries,
    is_specialist_enabled,
    managed_audit_log,
    open_managed_regards_port,
    pick_bundle_to_activate,
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


def _sample_specialists() -> list[dict[str, str]]:
    return [
        {
            "id": "org.gestionnaire",
            "name": "Gestionnaire",
            "role": "RH",
            "description": "Regard RH",
            "system_prompt": "Tu es RH.",
            "avatar_color": "#336699",
            "avatar_icon": "people",
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


def test_signed_bundle_always_includes_specialists_array() -> None:
    bundle = sign_bundle_for_tests(
        catalog_id="spec-cat",
        version="1.0.0",
        name="Specialists",
        specialists=_sample_specialists(),
    )
    payload = bundle.to_dict()
    assert payload["specialists"] == _sample_specialists()
    assert payload["personas"] == []
    assert "specialists" in payload


def test_personas_only_bundle_backward_compatible(tmp_path: Path) -> None:
    """T2: ancien bundle sans specialists reste vérifiable."""
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from app.plugins.ports.managed_regards import (
        TEST_SIGNING_PRIVATE_KEY_B64,
        canonical_signing_bytes,
    )

    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    legacy_body = {
        "catalog_id": "legacy-cat",
        "version": "1.0.0",
        "name": "Legacy",
        "personas": _sample_personas(),
        "algorithm": "ed25519",
        "provenance": "managed",
    }
    message = canonical_signing_bytes(legacy_body)
    private_key = Ed25519PrivateKey.from_private_bytes(
        base64.b64decode(TEST_SIGNING_PRIVATE_KEY_B64)
    )
    legacy_payload = {
        **legacy_body,
        "signature": base64.b64encode(private_key.sign(message)).decode("ascii"),
    }
    assert port.verify_signature(legacy_payload) is True
    port.install_catalog_version(legacy_payload)
    port.activate_catalog("legacy-cat")
    active = port.active_persona_set()
    assert active is not None
    assert len(active["personas"]) == 1
    specialist_set = port.active_specialist_set()
    assert specialist_set is not None
    assert specialist_set["specialists"] == []
    assert len(specialist_set["effective_entries"]) == 1


def test_specialists_only_dual_read(tmp_path: Path) -> None:
    """T3: bundle specialists-only, dual-read utilise specialists."""
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="spec-only",
        version="1.0.0",
        name="Spec only",
        specialists=_sample_specialists(),
    )
    port.install_catalog_version(bundle)
    port.activate_catalog("spec-only")
    status = port.get_catalog_status()
    assert status["specialist_count"] == 1
    assert status["persona_count"] == 0
    active = port.active_specialist_set()
    assert active is not None
    assert len(active["specialists"]) == 1
    assert active["personas"] == []
    assert len(active["effective_entries"]) == 1
    assert active["effective_entries"][0]["id"] == "org.gestionnaire"


def test_dual_read_prefers_specialists_over_personas() -> None:
    catalog = {
        "personas": _sample_personas(),
        "specialists": _sample_specialists(),
    }
    entries = dual_read_catalog_entries(catalog)
    assert entries[0]["id"] == "org.gestionnaire"


def test_personas_only_bundle_with_empty_specialists_array(tmp_path: Path) -> None:
    """Cloud format: personas-only bundle signed with specialists: []."""
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="cloud-personas",
        version="1.0.0",
        name="Cloud personas",
        personas=_sample_personas(),
        specialists=[],
    )
    payload = bundle.to_dict()
    assert payload["specialists"] == []
    assert port.verify_signature(payload) is True
    port.install_catalog_version(bundle)
    catalog_path = personas_dir / "managed" / "cloud-personas" / "1.0.0" / CATALOG_FILE
    with catalog_path.open("r", encoding="utf-8") as handle:
        installed = json.load(handle)
    assert installed["specialists"] == []
    assert len(installed["personas"]) == 1


def test_install_strips_hmac_secret_from_catalog_file(tmp_path: Path) -> None:
    """M3: hmac_secret_b64 must not be persisted in catalog.json."""
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
        catalog_id="hmac-strip",
        version="0.1.0",
        name="HMAC strip",
        personas=_sample_personas(),
        algorithm="hmac-sha256",
        hmac_secret_b64=secret,
    )
    payload = bundle.to_dict()
    payload["hmac_secret_b64"] = secret
    assert port.verify_signature(payload) is True
    port.install_catalog_version(payload)
    catalog_path = personas_dir / "managed" / "hmac-strip" / "0.1.0" / CATALOG_FILE
    with catalog_path.open("r", encoding="utf-8") as handle:
        installed = json.load(handle)
    assert "hmac_secret_b64" not in installed


def _sample_specialists_with_tools() -> list[dict[str, object]]:
    return [
        {
            "id": "org.gestionnaire",
            "name": "Gestionnaire",
            "role": "RH",
            "description": "Regard RH",
            "system_prompt": "Tu es RH.",
            "avatar_color": "#336699",
            "avatar_icon": "people",
            "tools": {
                "allowed": [
                    {"connector_id": "ihora", "tool": "list_absences"},
                    {"connector_id": "ihora", "tool": "get_timesheet"},
                ],
                "forbidden": [],
            },
        }
    ]


def test_active_persona_set_marks_business_agents_with_tools(tmp_path: Path) -> None:
    """P1: dual-read specialists expose is_business_agent et tools pour l'UI."""
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="spec-tools",
        version="1.0.0",
        name="Agents outils",
        specialists=_sample_specialists_with_tools(),
    )
    port.install_catalog_version(bundle)
    port.activate_catalog("spec-tools")

    active = port.active_persona_set()
    assert active is not None
    assert active["has_specialists"] is True
    assert len(active["personas"]) == 1
    agent = active["personas"][0]
    assert agent["is_business_agent"] is True
    assert agent["id"] == "org.gestionnaire"
    tools = agent.get("tools") or {}
    allowed = tools.get("allowed") or []
    assert len(allowed) == 2
    assert allowed[0]["connector_id"] == "ihora"


def test_list_sets_includes_business_agents_from_specialists(tmp_path: Path) -> None:
    """P1: list_sets desktop retourne les agents métier dual-read."""
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    bundle = sign_bundle_for_tests(
        catalog_id="spec-list",
        version="1.0.0",
        name="Liste agents",
        specialists=_sample_specialists_with_tools(),
    )
    port.install_catalog_version(bundle)
    port.activate_catalog("spec-list")

    sets = personas_storage.list_sets(personas_dir)
    managed = next(s for s in sets if s.get("id") == "managed_spec-list")
    assert managed.get("has_specialists") is True
    assert managed["personas"][0]["is_business_agent"] is True
    assert managed["personas"][0]["tools"]["allowed"][0]["tool"] == "list_absences"


def test_from_dict_rejects_specialists_null() -> None:
    with pytest.raises(ValueError, match="invalid_signed_bundle"):
        SignedBundle.from_dict(
            {
                "catalog_id": "x",
                "version": "1.0.0",
                "name": "x",
                "personas": [],
                "specialists": None,
                "signature": "sig",
            }
        )


def test_is_specialist_enabled_dual_read() -> None:
    assert is_specialist_enabled({"id": "a"}) is True
    assert is_specialist_enabled({"id": "a", "enabled": True}) is True
    assert is_specialist_enabled({"id": "a", "enabled": False}) is False


def test_dual_read_excludes_disabled_specialists() -> None:
    catalog = {
        "personas": _sample_personas(),
        "specialists": [
            {**_sample_specialists()[0], "enabled": False},
            {
                "id": "org.active",
                "name": "Active",
                "role": "Ops",
                "description": "Actif",
                "system_prompt": "Tu es actif.",
                "avatar_color": "#111111",
                "avatar_icon": "check",
            },
        ],
    }
    entries = dual_read_catalog_entries(catalog)
    assert len(entries) == 1
    assert entries[0]["id"] == "org.active"


def test_active_persona_set_excludes_disabled_specialists(tmp_path: Path) -> None:
    _, personas_dir = _personas_layout(tmp_path)
    port = create_personas_managed_port(personas_dir)
    disabled = {**_sample_specialists_with_tools()[0], "enabled": False}
    bundle = sign_bundle_for_tests(
        catalog_id="spec-disabled",
        version="1.0.0",
        name="Disabled agent",
        specialists=[disabled],
    )
    port.install_catalog_version(bundle)
    port.activate_catalog("spec-disabled")
    active = port.active_persona_set()
    assert active is not None
    assert active["personas"] == []
    assert personas_storage.list_managed_specialists(personas_dir) == []


def test_pick_bundle_to_activate_prefers_highest_version() -> None:
    low = sign_bundle_for_tests(
        catalog_id="cat-a",
        version="1.0.0",
        name="A",
        personas=_sample_personas(),
    ).to_dict()
    high = sign_bundle_for_tests(
        catalog_id="cat-b",
        version="2.1.0",
        name="B",
        personas=_sample_personas(),
    ).to_dict()
    older_patch = sign_bundle_for_tests(
        catalog_id="cat-c",
        version="2.0.9",
        name="C",
        personas=_sample_personas(),
    ).to_dict()
    winner = pick_bundle_to_activate([low, high, older_patch])
    assert winner is not None
    assert winner["catalog_id"] == "cat-b"
    assert winner["version"] == "2.1.0"
