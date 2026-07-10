"""Détection des capacités runtime (Docker/sandbox)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Capabilities:
    docker: bool
    sandbox_available: bool


def detect_docker() -> bool:
    """Détecte si le démon Docker répond. Ne lève jamais."""
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.debug("Docker indisponible : %s", exc)
        return False


def detect_capabilities() -> Capabilities:
    docker = detect_docker()
    return Capabilities(docker=docker, sandbox_available=docker)
