"""Manifeste du plugin cloud (builtin V2, scaffold)."""

VERSION = "0.1.0"

PERMISSIONS = [
    "storage:namespace",
    "project:sync",
    "regards:managed",
    "capability:remote",
    "network:improba-cloud",
    "ui:panels",
    "settings:section",
]

TOOLS = ["sync_to_cloud", "sync_from_cloud", "enroll_to_cloud", "sync_managed_regards"]

HOOKS: list[str] = []

DEFAULT_ENABLED = False
