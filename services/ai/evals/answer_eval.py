"""Run answer-judge eval cases."""

from __future__ import annotations

from dataclasses import dataclass

from evals.config import get_api_key, get_base_url
from evals.judge import JudgeVerdict, judge_answer
from evals.schema import AnswerJudgeCase


@dataclass(frozen=True)
class AnswerEvalResult:
    case_id: str
    score: int
    rationale: str
    passed: bool


async def run_answer_case(
    case: AnswerJudgeCase,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> AnswerEvalResult:
    """Judge a fixed golden candidate answer against the case rubric."""
    key = api_key if api_key is not None else get_api_key()
    if not key:
        raise RuntimeError("MISTRAL_API_KEY or LLM_DEFAULT_API_KEY is required for answer eval.")

    verdict: JudgeVerdict = await judge_answer(
        question=case.question,
        candidate_answer=case.candidate_answer,
        criteria=case.criteria,
        api_key=key,
        base_url=base_url or get_base_url(),
    )
    return AnswerEvalResult(
        case_id=case.id,
        score=verdict.score,
        rationale=verdict.rationale,
        passed=verdict.score >= case.pass_min_score,
    )
