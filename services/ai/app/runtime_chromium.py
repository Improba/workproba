"""Chromium Playwright bundlé (PDF HTML + navigateur), sans pip dans l'exe gelé.

Contrat:
- Le sidecar contient le driver Playwright (pin dans pyproject.toml).
- Les binaires vivent sous ``PLAYWRIGHT_BROWSERS_PATH`` (resources Tauri).
- Fetch : ``playwright install chromium --no-shell`` (Chrome for Testing
  complet, pas le headless-shell).
- Launch : ``channel='chromium'`` pour le new headless de ce binaire.
  Sans channel, Playwright 1.49+ cherche ``chromium-headless-shell``.
"""

from __future__ import annotations

import inspect
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

PLAYWRIGHT_PIP_SPEC = "playwright==1.61.0"
_BUILD_DIR = re.compile(r"^chromium-\d+$")
_PROBE: bool | None = None
_REVISION_CACHE: str | None = None
_REVISION_RESOLVED = False


class ChromiumUnavailable(RuntimeError):
    """Playwright ou le binaire Chromium est absent."""


def is_frozen() -> bool:
    """True dans le sidecar PyInstaller (pas de pip, pas de venv)."""
    return bool(getattr(sys, "frozen", False))


def reset_chromium_probe_cache() -> None:
    """Invalide le cache de ``chromium_available`` (tests)."""
    global _PROBE, _REVISION_CACHE, _REVISION_RESOLVED
    _PROBE = None
    _REVISION_CACHE = None
    _REVISION_RESOLVED = False


def chromium_launch_args() -> list[str]:
    """Flags de lancement communs PDF + plugin browser."""
    args = ["--disable-dev-shm-usage"]
    if is_frozen():
        args.append("--no-sandbox")
    return args


def chromium_launch_kwargs() -> dict[str, Any]:
    """Kwargs ``chromium.launch`` : Chromium bundlé, pas le headless-shell."""
    return {
        "headless": True,
        "channel": "chromium",
        "args": chromium_launch_args(),
    }


def playwright_browsers_roots() -> list[Path]:
    """Répertoires candidats (env d'abord).

    En binaire gelé : uniquement ``PLAYWRIGHT_BROWSERS_PATH`` (installeur).
    """
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if is_frozen():
        return [Path(env).expanduser()] if env else []

    roots: list[Path] = []
    if env:
        roots.append(Path(env).expanduser())

    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    defaults = [
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / "Library" / "Caches" / "ms-playwright",
    ]
    if local_app:
        defaults.append(Path(local_app) / "ms-playwright")

    if len(Path(__file__).resolve().parents) >= 4:
        defaults.append(
            Path(__file__).resolve().parents[3]
            / "desktop"
            / "src-tauri"
            / "resources"
            / "ms-playwright"
        )

    for candidate in defaults:
        resolved = candidate.expanduser()
        if resolved not in roots:
            roots.append(resolved)
    return roots


def playwright_chromium_revision() -> str | None:
    """Révision ``chromium`` lue dans le ``browsers.json`` du driver."""
    global _REVISION_CACHE, _REVISION_RESOLVED
    if _REVISION_RESOLVED:
        return _REVISION_CACHE
    revision: str | None = None
    try:
        import playwright

        browsers_json = (
            Path(inspect.getfile(playwright)).resolve().parent
            / "driver"
            / "package"
            / "browsers.json"
        )
        data = json.loads(browsers_json.read_text(encoding="utf-8"))
        for item in data.get("browsers", []):
            if item.get("name") == "chromium":
                revision = str(item["revision"])
                break
    except (OSError, KeyError, TypeError, ValueError, ImportError):
        revision = None
    _REVISION_CACHE = revision
    _REVISION_RESOLVED = True
    return revision


def find_chromium_build_dir(roots: Iterable[Path] | None = None) -> Path | None:
    """Dossier ``chromium-<revision>`` (pas le headless-shell)."""
    search = list(roots) if roots is not None else playwright_browsers_roots()
    revision = playwright_chromium_revision()
    for root in search:
        found = _find_build_in_root(root, revision=revision)
        if found is not None:
            return found
    return None


def _is_nonempty_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        return any(path.iterdir())
    except OSError:
        return False


def _find_build_in_root(root: Path, *, revision: str | None) -> Path | None:
    if not root.is_dir():
        return None
    if revision:
        exact = root / f"chromium-{revision}"
        if _is_nonempty_dir(exact):
            return exact
        if is_frozen():
            return None
    return _any_chromium_build(root)


def _any_chromium_build(root: Path) -> Path | None:
    try:
        children = list(root.iterdir())
    except OSError:
        return None
    for child in children:
        if _BUILD_DIR.match(child.name) and _is_nonempty_dir(child):
            return child
    return None


def chromium_available() -> bool:
    """True si le build Chromium attendu par le driver est présent."""
    global _PROBE
    if _PROBE is not None:
        return _PROBE
    try:
        import playwright  # noqa: F401
    except ImportError:
        _PROBE = False
        return False
    _PROBE = find_chromium_build_dir() is not None
    return _PROBE


def require_chromium(*, allow_dev_install: bool = True) -> None:
    """Garantit Playwright + Chromium, ou lève ``ChromiumUnavailable``.

    En binaire gelé : jamais de pip / ``playwright install``.
    """
    if chromium_available():
        return
    if is_frozen() or not allow_dev_install:
        raise ChromiumUnavailable(
            "Chromium bundlé introuvable (PLAYWRIGHT_BROWSERS_PATH)"
        )
    _dev_install_chromium()
    reset_chromium_probe_cache()
    if not chromium_available():
        raise ChromiumUnavailable("Installation Chromium de développement échouée")


def _dev_install_chromium() -> None:
    logger.info("dev: installation Playwright / Chromium")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pip = subprocess.run(
            [sys.executable, "-m", "pip", "install", PLAYWRIGHT_PIP_SPEC],
            capture_output=True,
            text=True,
            check=False,
        )
        if pip.returncode != 0:
            logger.warning("pip install playwright failed: %s", pip.stderr)
            return
    dest = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    env = os.environ.copy()
    if dest:
        env["PLAYWRIGHT_BROWSERS_PATH"] = dest
    install = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium", "--no-shell"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if install.returncode != 0:
        logger.warning("playwright install chromium failed: %s", install.stderr)
        fallback = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if fallback.returncode != 0:
            logger.warning("playwright install chromium retry failed: %s", fallback.stderr)


def health_chromium_status() -> str:
    """Valeur stable pour ``GET /health`` : ready | missing."""
    return "ready" if chromium_available() else "missing"


__all__ = [
    "ChromiumUnavailable",
    "PLAYWRIGHT_PIP_SPEC",
    "chromium_available",
    "chromium_launch_args",
    "chromium_launch_kwargs",
    "find_chromium_build_dir",
    "health_chromium_status",
    "is_frozen",
    "playwright_browsers_roots",
    "playwright_chromium_revision",
    "require_chromium",
    "reset_chromium_probe_cache",
]
