"""Manifeste du plugin cloud (builtin V2, scaffold)."""

VERSION = "0.1.0"

PERMISSIONS = [
    "storage:namespace",
    "project:sync",
    "network:improba-cloud",
    "ui:panels",
    "settings:section",
]

TOOLS = ["sync_to_cloud"]

HOOKS: list[str] = []

DEFAULT_ENABLED = False
