"""Pydantic models and loaders for eval case JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class EvalDocument(BaseModel):
    id: str
    title: str
    text: str


class RetrievalCase(BaseModel):
    id: str
    type: Literal["retrieval"]
    documents: list[EvalDocument]
    query: str
    relevant_ids: list[str]
    k: int = Field(default=2, ge=1)
    pass_threshold: float = Field(default=1.0, ge=0.0, le=1.0)


class AnswerJudgeCase(BaseModel):
    id: str
    type: Literal["answer_judge"]
    question: str
    candidate_answer: str
    criteria: str
    pass_min_score: int = Field(default=3, ge=1, le=5)


EvalCase = Annotated[RetrievalCase | AnswerJudgeCase, Field(discriminator="type")]

CASES_DIR = Path(__file__).parent / "cases"


def load_case(path: Path) -> RetrievalCase | AnswerJudgeCase:
    data = json.loads(path.read_text(encoding="utf-8"))
    case_type = data.get("type")
    if case_type == "retrieval":
        return RetrievalCase.model_validate(data)
    if case_type == "answer_judge":
        return AnswerJudgeCase.model_validate(data)
    raise ValueError(f"Unknown eval case type {case_type!r} in {path}")


def load_all_cases(cases_dir: Path | None = None) -> list[RetrievalCase | AnswerJudgeCase]:
    root = cases_dir or CASES_DIR
    return [load_case(path) for path in sorted(root.glob("*.json"))]
