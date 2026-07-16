"""CLI entry point: ``python -m evals``."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from evals.answer_eval import run_answer_case
from evals.config import eval_enabled, get_api_key
from evals.retrieval_eval import run_retrieval_case
from evals.schema import AnswerJudgeCase, RetrievalCase, load_all_cases


async def _run_all() -> int:
    cases = load_all_cases()
    if not cases:
        print("No eval cases found.")
        return 1

    if not eval_enabled():
        print(f"Loaded {len(cases)} case(s). Set WP_EVAL=1 to run live evals.")
        for case in cases:
            print(f"  - {case.id} ({case.type})")
        return 0

    api_key = get_api_key()
    if not api_key:
        print("WP_EVAL=1 but no MISTRAL_API_KEY or LLM_DEFAULT_API_KEY in environment.")
        return 1

    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory(prefix="workproba-eval-") as tmp:
        db_path = Path(tmp) / "memory.db"
        for case in cases:
            if isinstance(case, RetrievalCase):
                result = await run_retrieval_case(case, db_path=db_path, api_key=api_key)
                status = "PASS" if result.passed else "FAIL"
                print(
                    f"[{status}] {result.case_id}: recall@{case.k}={result.recall_at_k:.2f} "
                    f"retrieved={result.retrieved_ids}"
                )
            elif isinstance(case, AnswerJudgeCase):
                result = await run_answer_case(case, api_key=api_key)
                status = "PASS" if result.passed else "FAIL"
                print(
                    f"[{status}] {result.case_id}: score={result.score}/5 "
                    f"min={case.pass_min_score}"
                )
            else:
                print(f"[SKIP] unknown case type: {case!r}")
                continue

            if result.passed:
                passed += 1
            else:
                failed += 1

    print(f"Summary: {passed} passed, {failed} failed, {len(cases)} total.")
    return 0 if failed == 0 else 1


def main() -> None:
    raise SystemExit(asyncio.run(_run_all()))


if __name__ == "__main__":
    main()
