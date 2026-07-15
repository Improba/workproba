"""Ports typés entre plugins (isolation des namespaces)."""

from app.plugins.ports.managed_regards import (
    MANAGED_REGARDS_PERMISSION,
    FilesystemManagedRegardsPort,
    ManagedRegardsPort,
    SignedBundle,
    create_personas_managed_port,
    open_managed_regards_port,
)

__all__ = [
    "MANAGED_REGARDS_PERMISSION",
    "FilesystemManagedRegardsPort",
    "ManagedRegardsPort",
    "SignedBundle",
    "create_personas_managed_port",
    "open_managed_regards_port",
]
