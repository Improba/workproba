"""Ports typés entre plugins (isolation des namespaces)."""

from app.plugins.ports.managed_regards import (
    MANAGED_REGARDS_PERMISSION,
    FilesystemManagedRegardsPort,
    ManagedRegardsPort,
    SignedBundle,
    create_personas_managed_port,
    open_managed_regards_port,
)
from app.plugins.ports.remote_capability_gateway import (
    REMOTE_CAPABILITY_PERMISSION,
    HttpRemoteCapabilityGateway,
    IdentityDelegation,
    LocalRemoteCapabilityGateway,
    RemoteCapabilityGateway,
    RemoteCapabilityRejected,
    minimize_remote_payload,
    open_remote_capability_gateway,
    remote_capability_audit_log,
)

__all__ = [
    "MANAGED_REGARDS_PERMISSION",
    "FilesystemManagedRegardsPort",
    "ManagedRegardsPort",
    "SignedBundle",
    "create_personas_managed_port",
    "open_managed_regards_port",
    "REMOTE_CAPABILITY_PERMISSION",
    "HttpRemoteCapabilityGateway",
    "IdentityDelegation",
    "LocalRemoteCapabilityGateway",
    "RemoteCapabilityGateway",
    "RemoteCapabilityRejected",
    "minimize_remote_payload",
    "open_remote_capability_gateway",
    "remote_capability_audit_log",
]
