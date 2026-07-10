"""Tests des résumés humains des appels d'outils."""

from __future__ import annotations

from app.agent.human import build_human_summary


def test_human_summary_list_files_start() -> None:
    summary = build_human_summary("list_files", {"subdir": "assets"})
    assert summary == "Je vais lister les fichiers du dossier assets"


def test_human_summary_list_files_result() -> None:
    summary = build_human_summary(
        "list_files",
        {"subdir": ""},
        result={"entries": [{"path": "a"}, {"path": "b"}]},
    )
    assert summary == "J'ai listé les fichiers du projet (2 éléments)"


def test_human_summary_search_kb_start() -> None:
    summary = build_human_summary("search_kb", {"query": "CA Q2"})
    assert summary == "Je vais chercher « CA Q2 » dans les fichiers"


def test_human_summary_search_kb_result_empty() -> None:
    summary = build_human_summary(
        "search_kb",
        {"query": "introuvable"},
        result={"results": []},
    )
    assert summary == "Je n'ai trouvé aucun résultat pour « introuvable »"


def test_human_summary_read_document_start() -> None:
    summary = build_human_summary("read_document", {"document_id": "docs/fiche_candidat.pdf"})
    assert summary == "Je vais lire fiche_candidat.pdf"


def test_human_summary_read_document_result_with_pages() -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "fiche_candidat.pdf"},
        result={"metadata": {"pages_total": 12}},
    )
    assert summary == "J'ai lu fiche_candidat.pdf (12 pages)"


def test_human_summary_read_document_result_with_lines() -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "notes.md"},
        result={"metadata": {"lines_returned": 45}},
    )
    assert summary == "J'ai lu notes.md (45 lignes)"


def test_human_summary_run_code_neutral() -> None:
    assert build_human_summary("run_code", {"code": "print(1)"}) == "Je vais exécuter un calcul"
    assert build_human_summary("run_code", {"code": "print(1)"}, result={}) == "J'ai exécuté un calcul"


def test_human_summary_generate_document() -> None:
    start = build_human_summary("generate_document", {"name": "contrat_dupont.docx"})
    result = build_human_summary(
        "generate_document",
        {"name": "contrat_dupont.docx"},
        result={"metadata": {"saved": True}},
    )
    assert start == "Je vais créer contrat_dupont.docx"
    assert result == "J'ai créé contrat_dupont.docx"


def test_human_summary_error_variants() -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "manquant.pdf"},
        result={},
        is_error=True,
    )
    assert summary == "Je n'ai pas pu lire manquant.pdf"
