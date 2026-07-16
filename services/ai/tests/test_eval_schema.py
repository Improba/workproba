"""Validate all eval case JSON files against the schema (offline)."""

from __future__ import annotations

from evals.schema import (
    CASES_DIR,
    AnswerJudgeCase,
    RetrievalCase,
    load_all_cases,
    load_case,
)


def test_cases_dir_exists() -> None:
    assert CASES_DIR.is_dir()
    assert list(CASES_DIR.glob("*.json")), "expected at least one case JSON"


def test_load_all_cases() -> None:
    cases = load_all_cases()
    assert len(cases) >= 10
    types = {case.type for case in cases}
    assert "retrieval" in types
    assert "answer_judge" in types


def test_retrieval_support_client_case() -> None:
    case = load_case(CASES_DIR / "retrieval_support_client.json")
    assert isinstance(case, RetrievalCase)
    assert case.id == "retrieval_support_client"
    assert case.k == 2
    assert "notes.md" in case.relevant_ids


def test_answer_factual_short_case() -> None:
    case = load_case(CASES_DIR / "answer_factual_short.json")
    assert isinstance(case, AnswerJudgeCase)
    assert case.id == "answer_factual_short"
    assert case.pass_min_score == 3
