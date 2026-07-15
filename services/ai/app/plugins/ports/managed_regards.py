"""ManagedRegardsPort — catalogue Regards administrés (namespace workproba.personas)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from app.audit import log_event, resolve_app_data_dir
from app.plugins.registry import PLUGIN_WORKPROBA_PERSONAS

MANAGED_REGARDS_PERMISSION = "regards:managed"
MANAGED_DIR = "managed"
STATE_FILE = "state.json"
CATALOG_FILE = "catalog.json"

# Paire Ed25519 de test (dev/tests uniquement — ne pas utiliser en production).
TEST_SIGNING_PRIVATE_KEY_B64 = "TPDi/M4mFl4xB22wyEDypq/aFiu5VZenocpQ7KjQSms="
TEST_SIGNING_PUBLIC_KEY_B64 = "kPUjR91E/8GgKr4V5Bt8vfrKBmPkg0sF4bYfCHXyNl0="

JsonDict = dict[str, Any]

_MANAGED_AUDIT_LOG: list[JsonDict] = []


def managed_audit_log() -> list[JsonDict]:
    return list(_MANAGED_AUDIT_LOG)


def clear_managed_audit_log() -> None:
    _MANAGED_AUDIT_LOG.clear()


def _safe_segment(value: str) -> bool:
    if not value or value in {".", ".."}:
        return False
    if "/" in value or "\\" in value or ".." in value:
        return False
    return True


def canonical_signing_bytes(payload: JsonDict) -> bytes:
    """Octets signés : JSON canonique sans champs signature / secret."""
    excluded = {"signature", "hmac_secret_b64"}
    body = {key: value for key, value in payload.items() if key not in excluded}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class SignedBundle:
    catalog_id: str
    version: str
    name: str
    personas: list[JsonDict]
    signature: str
    algorithm: str = "ed25519"
    provenance: str = "managed"
    hmac_secret_b64: str | None = None

    def to_dict(self) -> JsonDict:
        data: JsonDict = {
            "catalog_id": self.catalog_id,
            "version": self.version,
            "name": self.name,
            "personas": self.personas,
            "signature": self.signature,
            "algorithm": self.algorithm,
            "provenance": self.provenance,
        }
        if self.hmac_secret_b64 is not None:
            data["hmac_secret_b64"] = self.hmac_secret_b64
        return data

    @classmethod
    def from_dict(cls, raw: JsonDict) -> SignedBundle:
        catalog_id = str(raw.get("catalog_id") or "")
        version = str(raw.get("version") or "")
        name = str(raw.get("name") or "")
        personas = list(raw.get("personas") or [])
        signature = str(raw.get("signature") or "")
        algorithm = str(raw.get("algorithm") or "ed25519")
        provenance = str(raw.get("provenance") or "managed")
        secret = raw.get("hmac_secret_b64")
        hmac_secret_b64 = str(secret) if isinstance(secret, str) else None
        if not catalog_id or not version or not signature:
            raise ValueError("invalid_signed_bundle")
        return cls(
            catalog_id=catalog_id,
            version=version,
            name=name,
            personas=personas,
            signature=signature,
            algorithm=algorithm,
            provenance=provenance,
            hmac_secret_b64=hmac_secret_b64,
        )


@runtime_checkable
class ManagedRegardsPort(Protocol):
    def list_managed_catalogs(self) -> list[JsonDict]: ...

    def install_catalog_version(self, signed_bundle: SignedBundle | JsonDict) -> JsonDict: ...

    def verify_signature(self, signed_bundle: SignedBundle | JsonDict) -> bool: ...

    def activate_catalog(self, catalog_id: str, version: str | None = None) -> JsonDict: ...

    def remove_revoked_version(self, catalog_id: str, version: str) -> bool: ...

    def get_catalog_status(self) -> JsonDict: ...


class SignatureVerifier:
    def __init__(
        self,
        *,
        public_key_b64: str | None = None,
        hmac_secret_b64: str | None = None,
        allow_test_keys: bool = False,
    ) -> None:
        if public_key_b64:
            self._public_key_b64 = public_key_b64
        elif allow_test_keys:
            self._public_key_b64 = TEST_SIGNING_PUBLIC_KEY_B64
        else:
            env_key = os.environ.get("WORKPROBA_REGARDS_PUBLIC_KEY_B64")
            self._public_key_b64 = env_key if env_key else None
        self._hmac_secret_b64 = hmac_secret_b64

    def verify(self, payload: JsonDict) -> bool:
        algorithm = str(payload.get("algorithm") or "ed25519").lower()
        signature = str(payload.get("signature") or "")
        if not signature:
            return False
        message = canonical_signing_bytes(payload)
        if algorithm == "ed25519":
            return self._verify_ed25519(message, signature)
        if algorithm in {"hmac-sha256", "hmac_sha256"}:
            secret_b64 = self._hmac_secret_b64
            if not isinstance(secret_b64, str) or not secret_b64:
                return False
            expected = hmac.new(
                base64.b64decode(secret_b64),
                message,
                hashlib.sha256,
            ).digest()
            try:
                provided = base64.b64decode(signature)
            except (ValueError, TypeError):
                return False
            return hmac.compare_digest(expected, provided)
        return False

    def _verify_ed25519(self, message: bytes, signature_b64: str) -> bool:
        if not self._public_key_b64:
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError:
            return False
        try:
            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(self._public_key_b64)
            )
            public_key.verify(base64.b64decode(signature_b64), message)
            return True
        except (ValueError, TypeError):
            return False


def default_signature_verifier() -> SignatureVerifier:
    """Verifier par défaut : clé prod via env, ou clés de test si autorisé."""
    public_key_b64 = os.environ.get("WORKPROBA_REGARDS_PUBLIC_KEY_B64")
    allow_test_keys = (
        os.environ.get("WORKPROBA_ALLOW_TEST_REGARDS_KEYS") == "1"
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
    )
    return SignatureVerifier(
        public_key_b64=public_key_b64,
        allow_test_keys=allow_test_keys,
    )


def sign_bundle_for_tests(
    *,
    catalog_id: str,
    version: str,
    name: str,
    personas: list[JsonDict],
    algorithm: str = "ed25519",
    private_key_b64: str | None = None,
    hmac_secret_b64: str | None = None,
) -> SignedBundle:
    """Signe un bundle avec la clé de test (pytest uniquement)."""
    body: JsonDict = {
        "catalog_id": catalog_id,
        "version": version,
        "name": name,
        "personas": personas,
        "algorithm": algorithm,
        "provenance": "managed",
    }
    message = canonical_signing_bytes(body)
    if algorithm == "ed25519":
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        private_key = Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(private_key_b64 or TEST_SIGNING_PRIVATE_KEY_B64)
        )
        signature = base64.b64encode(private_key.sign(message)).decode("ascii")
    elif algorithm in {"hmac-sha256", "hmac_sha256"}:
        secret = hmac_secret_b64 or TEST_SIGNING_PUBLIC_KEY_B64
        digest = hmac.new(base64.b64decode(secret), message, hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode("ascii")
    else:
        raise ValueError("unsupported_algorithm")
    body["signature"] = signature
    return SignedBundle.from_dict(body)


class FilesystemManagedRegardsPort:
    """Implémentation locale sous `{personas_data}/managed/{catalog_id}/{version}/`."""

    def __init__(
        self,
        *,
        personas_data_dir: Path,
        caller_plugin_id: str,
        app_data_dir: Path,
        verifier: SignatureVerifier | None = None,
    ) -> None:
        self._personas_data_dir = personas_data_dir
        self._caller_plugin_id = caller_plugin_id
        self._app_data_dir = app_data_dir
        self._verifier = verifier or default_signature_verifier()

    def _audit(self, op: str, detail: JsonDict) -> None:
        entry = {"caller": self._caller_plugin_id, "op": op, **detail}
        _MANAGED_AUDIT_LOG.append(entry)
        log_event(
            self._app_data_dir,
            "plugin.managed_regards",
            f"plugin:{self._caller_plugin_id}",
            {"op": op, **detail},
        )

    def _managed_root(self) -> Path:
        return self._personas_data_dir / MANAGED_DIR

    def _state_path(self) -> Path:
        return self._managed_root() / STATE_FILE

    def _load_state(self) -> JsonDict:
        path = self._state_path()
        if not path.is_file():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return raw if isinstance(raw, dict) else {}

    def _save_state(self, state: JsonDict) -> None:
        root = self._managed_root()
        root.mkdir(parents=True, exist_ok=True)
        with self._state_path().open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)

    def _version_dir(self, catalog_id: str, version: str) -> Path:
        if not _safe_segment(catalog_id) or not _safe_segment(version):
            raise ValueError("invalid_catalog_id")
        return self._managed_root() / catalog_id / version

    def _read_catalog(self, catalog_id: str, version: str) -> JsonDict | None:
        path = self._version_dir(catalog_id, version) / CATALOG_FILE
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        return raw if isinstance(raw, dict) else None

    def list_managed_catalogs(self) -> list[JsonDict]:
        self._audit("list_managed_catalogs", {})
        root = self._managed_root()
        if not root.is_dir():
            return []
        state = self._load_state()
        active_id = state.get("active_catalog_id")
        active_version = state.get("active_version")
        catalogs: list[JsonDict] = []
        for catalog_dir in sorted(root.iterdir()):
            if not catalog_dir.is_dir() or catalog_dir.name == STATE_FILE:
                continue
            catalog_id = catalog_dir.name
            for version_dir in sorted(catalog_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                catalog = self._read_catalog(catalog_id, version_dir.name)
                if catalog is None:
                    continue
                catalogs.append(
                    {
                        "catalog_id": catalog_id,
                        "version": version_dir.name,
                        "name": catalog.get("name", ""),
                        "provenance": catalog.get("provenance", "managed"),
                        "persona_count": len(catalog.get("personas") or []),
                        "active": catalog_id == active_id and version_dir.name == active_version,
                        "installed_at": catalog.get("installed_at"),
                    }
                )
        return catalogs

    def verify_signature(self, signed_bundle: SignedBundle | JsonDict) -> bool:
        payload = (
            signed_bundle.to_dict()
            if isinstance(signed_bundle, SignedBundle)
            else dict(signed_bundle)
        )
        self._audit(
            "verify_signature",
            {"catalog_id": payload.get("catalog_id"), "version": payload.get("version")},
        )
        return self._verifier.verify(payload)

    def install_catalog_version(self, signed_bundle: SignedBundle | JsonDict) -> JsonDict:
        bundle = (
            signed_bundle
            if isinstance(signed_bundle, SignedBundle)
            else SignedBundle.from_dict(signed_bundle)
        )
        payload = bundle.to_dict()
        if not self.verify_signature(payload):
            raise ValueError("invalid_signature")
        self._audit(
            "install_catalog_version",
            {"catalog_id": bundle.catalog_id, "version": bundle.version},
        )
        version_dir = self._version_dir(bundle.catalog_id, bundle.version)
        version_dir.mkdir(parents=True, exist_ok=True)
        from app.plugins.workproba_personas.storage import now_iso

        catalog_record: JsonDict = {
            **payload,
            "installed_at": now_iso(),
        }
        with (version_dir / CATALOG_FILE).open("w", encoding="utf-8") as handle:
            json.dump(catalog_record, handle, ensure_ascii=False, indent=2)
        return {
            "catalog_id": bundle.catalog_id,
            "version": bundle.version,
            "name": bundle.name,
            "provenance": bundle.provenance,
            "installed": True,
        }

    def activate_catalog(self, catalog_id: str, version: str | None = None) -> JsonDict:
        if not _safe_segment(catalog_id):
            raise ValueError("invalid_catalog_id")
        self._audit("activate_catalog", {"catalog_id": catalog_id, "version": version})
        catalog_dir = self._managed_root() / catalog_id
        if not catalog_dir.is_dir():
            raise ValueError("catalog_not_found")
        effective_version = version
        if effective_version is None:
            versions = sorted(
                child.name for child in catalog_dir.iterdir() if child.is_dir()
            )
            if not versions:
                raise ValueError("catalog_not_found")
            effective_version = versions[-1]
        if not _safe_segment(effective_version):
            raise ValueError("invalid_catalog_id")
        catalog = self._read_catalog(catalog_id, effective_version)
        if catalog is None:
            raise ValueError("catalog_not_found")
        self._save_state(
            {
                "active_catalog_id": catalog_id,
                "active_version": effective_version,
            }
        )
        return {
            "catalog_id": catalog_id,
            "version": effective_version,
            "name": catalog.get("name", ""),
            "provenance": catalog.get("provenance", "managed"),
            "active": True,
        }

    def remove_revoked_version(self, catalog_id: str, version: str) -> bool:
        if not _safe_segment(catalog_id) or not _safe_segment(version):
            return False
        self._audit(
            "remove_revoked_version",
            {"catalog_id": catalog_id, "version": version},
        )
        version_dir = self._version_dir(catalog_id, version)
        if not version_dir.is_dir():
            return False
        shutil.rmtree(version_dir)
        state = self._load_state()
        if (
            state.get("active_catalog_id") == catalog_id
            and state.get("active_version") == version
        ):
            self._save_state({})
        return True

    def get_catalog_status(self) -> JsonDict:
        self._audit("get_catalog_status", {})
        state = self._load_state()
        catalog_id = state.get("active_catalog_id")
        version = state.get("active_version")
        if not isinstance(catalog_id, str) or not isinstance(version, str):
            return {"active": False, "catalog_id": None, "version": None}
        catalog = self._read_catalog(catalog_id, version)
        if catalog is None:
            return {"active": False, "catalog_id": catalog_id, "version": version}
        return {
            "active": True,
            "catalog_id": catalog_id,
            "version": version,
            "name": catalog.get("name", ""),
            "provenance": catalog.get("provenance", "managed"),
            "persona_count": len(catalog.get("personas") or []),
            "installed_at": catalog.get("installed_at"),
        }

    def active_persona_set(self) -> JsonDict | None:
        """Expose le catalogue actif au format set personas."""
        status = self.get_catalog_status()
        if not status.get("active"):
            return None
        catalog_id = str(status.get("catalog_id") or "")
        version = str(status.get("version") or "")
        catalog = self._read_catalog(catalog_id, version)
        if catalog is None:
            return None
        personas = catalog.get("personas") or []
        return {
            "id": f"managed_{catalog_id}",
            "name": str(catalog.get("name") or catalog_id),
            "personas": list(personas),
            "provenance": str(catalog.get("provenance") or "managed"),
            "managed_catalog_id": catalog_id,
            "managed_version": version,
        }


def create_personas_managed_port(personas_data_dir: Path) -> FilesystemManagedRegardsPort:
    """Port côté propriétaire (plugin personas, sans contrôle d'appelant externe)."""
    app_data_dir = resolve_app_data_dir(personas_data_dir.parent)
    return FilesystemManagedRegardsPort(
        personas_data_dir=personas_data_dir,
        caller_plugin_id=PLUGIN_WORKPROBA_PERSONAS,
        app_data_dir=app_data_dir,
        verifier=default_signature_verifier(),
    )


def open_managed_regards_port(
    *,
    caller_plugin_id: str,
    caller_permissions: frozenset[str],
    plugins_root: Path,
) -> FilesystemManagedRegardsPort:
    if MANAGED_REGARDS_PERMISSION not in caller_permissions:
        raise PermissionError(f"Missing permission: {MANAGED_REGARDS_PERMISSION}")
    personas_data_dir = plugins_root / PLUGIN_WORKPROBA_PERSONAS
    app_data_dir = resolve_app_data_dir(plugins_root)
    return FilesystemManagedRegardsPort(
        personas_data_dir=personas_data_dir,
        caller_plugin_id=caller_plugin_id,
        app_data_dir=app_data_dir,
        verifier=default_signature_verifier(),
    )
