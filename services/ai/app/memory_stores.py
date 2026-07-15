"""Résolution des stores de mémoire par scope (user global / project par espace).

La mémoire utilisateur est globale (partagée entre tous les espaces) ; la mémoire
projet est attachée à un workspace. Les deux sont matérialisées par des bases
SQLite distinctes (`memory.db`) ouvertes via `open_memory_store`.
"""

from __future__ import annotations

from pathlib import Path

from app.audit import resolve_user_data_dir
from app.rag.store import RagStore, open_memory_store

MemoryScope = str  # "user" | "project"
VALID_SCOPES: frozenset[str] = frozenset({"user", "project"})


def workspace_storage_root(workspace_data_dir: Path) -> Path:
    """Racine canonique V2 d'un espace (parent de `.workproba` si besoin)."""
    resolved = workspace_data_dir.expanduser().resolve()
    if resolved.name == ".workproba":
        return resolved.parent
    return resolved


def resolve_project_memory_db_path(workspace_data_dir: Path) -> Path:
    """Résout `memory.db` : plat (V2) prioritaire, puis imbriqué sous `.workproba`."""
    resolved = workspace_data_dir.expanduser().resolve()
    flat = workspace_storage_root(resolved) / "memory.db"
    nested = resolved / "memory.db"
    if flat.is_file():
        return flat
    if nested.is_file():
        return nested
    return flat


def user_memory_db_path(workspace_data_dir: Path) -> Path:
    """Chemin de la base de mémoire globale user (dérivée du workspace_data_dir)."""
    user_dir = resolve_user_data_dir(workspace_data_dir)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "memory.db"


def project_memory_db_path(workspace_data_dir: Path) -> Path:
    """Chemin de la base de mémoire projet (canonique V2 ou legacy imbriqué)."""
    return resolve_project_memory_db_path(workspace_data_dir)


def memory_db_path_for_scope(scope: MemoryScope, workspace_data_dir: Path) -> Path:
    if scope == "user":
        return user_memory_db_path(workspace_data_dir)
    return project_memory_db_path(workspace_data_dir)


def open_memory_store_for_scope(
    scope: MemoryScope,
    workspace_data_dir: Path,
) -> RagStore:
    """Ouvre le store de mémoire explicite (sans embeddings) pour le scope donné.

    Suffisant pour lister / ajouter / oublier des souvenirs explicites. Pour la
    recherche RAG projet (search_combined), utiliser le store complet côté main.
    """
    return open_memory_store(memory_db_path_for_scope(scope, workspace_data_dir))
