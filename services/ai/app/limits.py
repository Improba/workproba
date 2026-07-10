"""Limites opérationnelles des outils Workproba.

Centralise tous les plafonds (taille de lecture, extraction, recherche, sandbox,
génération de documents) pour qu'ils soient cohérents entre l'outil, le client
projet et le runner sandbox. Défense en profondeur : le client applique les
plafonds durs quelle que soit la valeur demandée par le modèle.

Les valeurs par défaut visent un usage bureau local-first : assez généreuses pour
un document métier, assez strictes pour éviter l'explosion du contexte LLM et la
saturation mémoire du sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass


def _mb(n: int) -> int:
    return n * 1024 * 1024


def _kb(n: int) -> int:
    return n * 1024


# Chemins dont l'écriture est interdite pour generate_document. La règle
# s'applique sur les composants du chemin relatif : un composant égal à l'un de
# ces noms, ou commençant par le préfixe `.env`, est refusé.
DEFAULT_GENERATE_DENY_NAMES: tuple[str, ...] = (".git", ".workproba")
DEFAULT_GENERATE_DENY_PREFIXES: tuple[str, ...] = (".env",)


@dataclass(frozen=True)
class Limits:
    # --- read_document (fichiers texte) ---
    read_max_lines: int = 2000
    read_max_bytes: int = _kb(256)  # 256 KiB retournés max par appel

    # --- extraction documents binaires ---
    extract_max_pages: int = 50  # PDF / PPTX
    extract_max_rows: int = 20_000  # XLSX (par feuille)
    extract_max_chars: int = 200_000  # plafond global du texte extrait
    extract_max_input_bytes: int = _mb(50)  # taille max du fichier binaire chargé en RAM

    # --- search_kb ---
    search_max_limit: int = 20
    search_max_files: int = 20_000  # budget de fichiers scannés (substring)
    search_file_max_bytes: int = _mb(1)  # taille max d'un fichier scanné

    # --- list_files + inventaire projet injecté au prompt ---
    list_max_entries: int = 500  # nombre max d'entrées renvoyées par list_files
    list_max_depth: int = 8  # profondeur de récursion max
    inventory_max_entries: int = 200  # fichiers listés dans le prompt système

    # --- sandbox / run_code ---
    sandbox_output_max_bytes: int = _kb(256)  # par flux (stdout + stderr)
    sandbox_memory_mb: int = 1024
    sandbox_cpu_seconds: int = 30
    sandbox_file_size_mb: int = 50  # taille max d'un fichier projet copié
    sandbox_max_output_files: int = 16  # fichiers générés collectés
    sandbox_max_output_file_bytes: int = _kb(256)
    sandbox_block_network: bool = True

    # --- generate_document ---
    generate_max_bytes: int = _mb(5)
    generate_deny_names: tuple[str, ...] = DEFAULT_GENERATE_DENY_NAMES
    generate_deny_prefixes: tuple[str, ...] = DEFAULT_GENERATE_DENY_PREFIXES


DEFAULT_LIMITS = Limits()
