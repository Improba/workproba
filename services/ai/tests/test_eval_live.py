"""Live product eval harness tests (network + Mistral key).

Skipped unless WP_EVAL=1 (distinct from WP_LIVE_LLM so CI stays green).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evals.answer_eval import run_answer_case
from evals.config import get_api_key, get_base_url
from evals.retrieval_eval import run_retrieval_case
from evals.schema import AnswerJudgeCase, RetrievalCase, load_all_cases

pytestmark = pytest.mark.skipif(
    os.getenv("WP_EVAL") != "1",
    reason="Live eval tests disabled (set WP_EVAL=1).",
)

_ALL_CASES = load_all_cases()
_RETRIEVAL_CASES = [c for c in _ALL_CASES if isinstance(c, RetrievalCase)]
_ANSWER_JUDGE_CASES = [c for c in _ALL_CASES if isinstance(c, AnswerJudgeCase)]


@pytest.fixture
def api_key() -> str:
    key = get_api_key()
    if not key:
        pytest.skip("MISTRAL_API_KEY or LLM_DEFAULT_API_KEY required for live eval.")
    return key


@pytest.mark.parametrize("case", _RETRIEVAL_CASES, ids=[c.id for c in _RETRIEVAL_CASES])
async def test_eval_retrieval_live(case: RetrievalCase, tmp_path: Path, api_key: str) -> None:
    result = await run_retrieval_case(
        case,
        db_path=tmp_path / f"{case.id}.db",
        api_key=api_key,
        base_url=get_base_url(),
    )
    assert result.recall_at_k >= case.pass_threshold, (
        f"[{case.id}] recall@{case.k}={result.recall_at_k}, retrieved={result.retrieved_ids}"
    )


@pytest.mark.parametrize("case", _ANSWER_JUDGE_CASES, ids=[c.id for c in _ANSWER_JUDGE_CASES])
async def test_eval_judge_live(case: AnswerJudgeCase, api_key: str) -> None:
    result = await run_answer_case(case, api_key=api_key, base_url=get_base_url())
    assert result.score >= case.pass_min_score, (
        f"[{case.id}] score={result.score}, rationale={result.rationale!r}"
    )
