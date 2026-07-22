"""Tests des résumés humains des appels d'outils."""

from __future__ import annotations

import pytest

from app.agent.human import build_human_summary


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_list_files_start(locale: str) -> None:
    summary = build_human_summary("list_files", {"subdir": "assets"}, locale=locale)
    if locale == "fr":
        assert summary == "Je vais lister les fichiers du dossier assets"
    else:
        assert summary == "I will list files of folder assets"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_list_files_result(locale: str) -> None:
    summary = build_human_summary(
        "list_files",
        {"subdir": ""},
        result={"entries": [{"path": "a"}, {"path": "b"}]},
        locale=locale,
    )
    if locale == "fr":
        assert summary == "J'ai listé les fichiers de l'espace (2 éléments)"
    else:
        assert summary == "I listed files of the space (2 items)"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_search_kb_start(locale: str) -> None:
    summary = build_human_summary("search_kb", {"query": "CA Q2"}, locale=locale)
    if locale == "fr":
        assert summary == "Je vais chercher « CA Q2 » dans les fichiers"
    else:
        assert summary == "I will search for « CA Q2 » in the files"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_search_kb_result_empty(locale: str) -> None:
    summary = build_human_summary(
        "search_kb",
        {"query": "introuvable"},
        result={"results": []},
        locale=locale,
    )
    if locale == "fr":
        assert summary == "Je n'ai trouvé aucun résultat pour « introuvable »"
    else:
        assert summary == "I found no results for « introuvable »"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_read_document_start(locale: str) -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "docs/fiche_candidat.pdf"},
        locale=locale,
    )
    if locale == "fr":
        assert summary == "Je vais lire fiche_candidat.pdf"
    else:
        assert summary == "I will read fiche_candidat.pdf"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_read_document_result_with_pages(locale: str) -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "fiche_candidat.pdf"},
        result={"metadata": {"pages_total": 12}},
        locale=locale,
    )
    if locale == "fr":
        assert summary == "J'ai lu fiche_candidat.pdf (12 pages)"
    else:
        assert summary == "I read fiche_candidat.pdf (12 pages)"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_read_document_result_with_lines(locale: str) -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "notes.md"},
        result={"metadata": {"lines_returned": 45}},
        locale=locale,
    )
    if locale == "fr":
        assert summary == "J'ai lu notes.md (45 lignes)"
    else:
        assert summary == "I read notes.md (45 lines)"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_run_code_neutral(locale: str) -> None:
    if locale == "fr":
        assert (
            build_human_summary("run_code", {"code": "print(1)"}, locale=locale)
            == "Je vais exécuter un calcul"
        )
        assert (
            build_human_summary(
                "run_code", {"code": "print(1)"}, result={}, locale=locale
            )
            == "J'ai exécuté un calcul"
        )
    else:
        assert (
            build_human_summary("run_code", {"code": "print(1)"}, locale=locale)
            == "I will run a calculation"
        )
        assert (
            build_human_summary(
                "run_code", {"code": "print(1)"}, result={}, locale=locale
            )
            == "I ran a calculation"
        )


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_generate_document(locale: str) -> None:
    start = build_human_summary(
        "generate_document",
        {"name": "contrat_dupont.docx"},
        locale=locale,
    )
    result = build_human_summary(
        "generate_document",
        {"name": "contrat_dupont.docx"},
        result={"metadata": {"saved": True}},
        locale=locale,
    )
    if locale == "fr":
        assert start == "Je vais créer contrat_dupont.docx"
        assert result == "J'ai créé contrat_dupont.docx"
    else:
        assert start == "I will create contrat_dupont.docx"
        assert result == "I created contrat_dupont.docx"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_error_variants(locale: str) -> None:
    summary = build_human_summary(
        "read_document",
        {"document_id": "manquant.pdf"},
        result={},
        is_error=True,
        locale=locale,
    )
    if locale == "fr":
        assert summary == "Je n'ai pas pu lire manquant.pdf"
    else:
        assert summary == "I could not read manquant.pdf"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_sync_from_cloud(locale: str) -> None:
    start = build_human_summary(
        "sync_from_cloud",
        {"project_id": "alpha"},
        locale=locale,
    )
    done = build_human_summary(
        "sync_from_cloud",
        {"project_id": "alpha"},
        result={"pulled": [{"id": "a"}, {"id": "b"}], "count": 2},
        locale=locale,
    )
    error = build_human_summary(
        "sync_from_cloud",
        {"project_id": "alpha"},
        result={},
        is_error=True,
        locale=locale,
    )
    if locale == "fr":
        assert start == "Je vais récupérer les documents du projet alpha depuis le cloud"
        assert done == "J'ai récupéré 2 document(s) du projet alpha depuis le cloud"
        assert error == "Je n'ai pas pu récupérer les documents du projet alpha depuis le cloud"
    else:
        assert start == "I will pull documents for project alpha from the cloud"
        assert done == "I pulled 2 document(s) for project alpha from the cloud"
        assert error == "I could not pull documents for project alpha from the cloud"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_enroll_to_cloud(locale: str) -> None:
    start = build_human_summary("enroll_to_cloud", {"base_url": "https://cloud.example"}, locale=locale)
    done = build_human_summary(
        "enroll_to_cloud",
        {"base_url": "https://cloud.example"},
        result={"authenticated": True},
        locale=locale,
    )
    error = build_human_summary(
        "enroll_to_cloud",
        {"base_url": "https://cloud.example"},
        result={},
        is_error=True,
        locale=locale,
    )
    if locale == "fr":
        assert start == "Je vais me connecter à Improba Cloud"
        assert done == "Je suis connecté à Improba Cloud"
        assert error == "Je n'ai pas pu me connecter à Improba Cloud"
    else:
        assert start == "I will sign in to Improba Cloud"
        assert done == "I am signed in to Improba Cloud"
        assert error == "I could not sign in to Improba Cloud"


@pytest.mark.parametrize("locale", ["fr", "en"])
def test_human_summary_sync_managed_regards(locale: str) -> None:
    start = build_human_summary("sync_managed_regards", {}, locale=locale)
    done = build_human_summary(
        "sync_managed_regards",
        {},
        result={"count": 3},
        locale=locale,
    )
    error = build_human_summary(
        "sync_managed_regards",
        {},
        result={},
        is_error=True,
        locale=locale,
    )
    if locale == "fr":
        assert start == "Je vais synchroniser les regards de l'organisation"
        assert done == "J'ai synchronisé 3 regard(s) de l'organisation"
        assert error == "Je n'ai pas pu synchroniser les regards de l'organisation"
    else:
        assert start == "I will sync organization regards"
        assert done == "I synced 3 organization regard(s)"
        assert error == "I could not sync organization regards"
