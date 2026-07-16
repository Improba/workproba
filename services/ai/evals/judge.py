"""LLM-as-judge via remote Mistral (OpenAI-compatible API)."""

from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from evals.config import DEFAULT_JUDGE_MODEL


class JudgeVerdict(BaseModel):
    score: int = Field(ge=1, le=5, description="Quality score from 1 (poor) to 5 (excellent).")
    rationale: str


async def judge_answer(
    *,
    question: str,
    candidate_answer: str,
    criteria: str,
    api_key: str,
    base_url: str,
    model_name: str = DEFAULT_JUDGE_MODEL,
) -> JudgeVerdict:
    """Score a fixed candidate answer against a rubric using a remote judge model."""
    model = OpenAIChatModel(
        model_name=model_name,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )
    agent = Agent(
        model=model,
        output_type=JudgeVerdict,
        system_prompt=(
            "You are an evaluation judge. Score the candidate answer against the rubric "
            "on a scale of 1-5. Respond with JSON: {\"score\": int, \"rationale\": str}."
        ),
    )
    prompt = (
        f"Question:\n{question}\n\n"
        f"Candidate answer:\n{candidate_answer}\n\n"
        f"Rubric:\n{criteria}"
    )
    result = await agent.run(prompt)
    return result.output
