"""Manifeste du plugin browser (builtin V2)."""

VERSION = "1.0.0"

PERMISSIONS = [
    "agent:tools",
    "ui:panels",
    "hooks:subscribe",
    "storage:namespace",
    "network:custom",
]

TOOLS = [
    "browser_navigate",
    "browser_click",
    "browser_extract",
    "browser_type",
    "browser_scroll",
    "browser_press",
    "browser_back",
    "browser_forward",
]

HOOKS = ["browser.navigate"]

DEFAULT_ENABLED = False

ACTION_TIMEOUT_MS = 30_000
MAX_SCREENSHOT_BYTES = 2_000_000
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
