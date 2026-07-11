"""Manifeste du plugin personas (builtin V2)."""

VERSION = "1.0.0"

PERMISSIONS = [
    "agent:tools",
    "ui:panels",
    "ui:composer",
    "settings:section",
    "hooks:subscribe",
    "storage:namespace",
    "core.providers.llm",
    "core.memory.search",
    "memory:forget",
]

TOOLS = ["ask_personas", "simulate_meeting"]

HOOKS: list[str] = []

DEFAULT_ENABLED = True

MAX_PERSONAS = 5
MAX_ROUNDS = 5
DEFAULT_ROUNDS = 3
MAX_OPINION_TOKENS = 1024
