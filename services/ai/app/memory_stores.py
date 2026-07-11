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


def user_memory_db_path(workspace_data_dir: Path) -> Path:
    """Chemin de la base de mémoire globale user (dérivée du workspace_data_dir)."""
    user_dir = resolve_user_data_dir(workspace_data_dir)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "memory.db"


def project_memory_db_path(workspace_data_dir: Path) -> Path:
    """Chemin de la base de mémoire projet (dans le dossier de données du workspace)."""
    return workspace_data_dir / "memory.db"


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
