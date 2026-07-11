"""Manifeste du plugin projet (builtin V2)."""

VERSION = "1.0.0"

PERMISSIONS = [
    "space:read",
    "files:write",
    "agent:tools",
    "ui:panels",
    "ui:composer",
    "settings:section",
    "hooks:subscribe",
    "storage:namespace",
    "storage:cross:workproba.projet",
]

TOOLS = ["publish_artifact", "list_projects", "create_project"]

HOOKS = ["space.opened", "file.written", "tool.call_completed"]

DEFAULT_ENABLED = False
