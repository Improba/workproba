"""Run retrieval eval cases against RagStore."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.rag.store import RagStore

from evals.config import DEFAULT_EMBEDDING_MODEL, get_api_key, get_base_url
from evals.metrics import recall_at_k
from evals.schema import RetrievalCase


@dataclass(frozen=True)
class RetrievalEvalResult:
    case_id: str
    recall_at_k: float
    retrieved_ids: list[str]
    passed: bool


async def run_retrieval_case(
    case: RetrievalCase,
    *,
    store: RagStore | None = None,
    db_path: Path | None = None,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
) -> RetrievalEvalResult:
    """Index case documents, search, and score recall@k."""
    key = api_key if api_key is not None else get_api_key()
    if not key:
        raise RuntimeError("MISTRAL_API_KEY or LLM_DEFAULT_API_KEY is required for retrieval eval.")

    owned_store = store
    if owned_store is None:
        if db_path is None:
            raise ValueError("Either store or db_path must be provided.")
        owned_store = RagStore(
            db_path=db_path,
            embedding_model=embedding_model,
            embedding_base_url=base_url or get_base_url(),
            embedding_api_key=key,
        )

    try:
        for doc in case.documents:
            await owned_store.index_document(
                document_id=doc.id,
                title=doc.title,
                mime_type="text/plain",
                text=doc.text,
            )
        results = await owned_store.search(query=case.query, limit=case.k)
        retrieved_ids = [row["document_id"] for row in results]
        score = recall_at_k(retrieved_ids, case.relevant_ids, case.k)
        return RetrievalEvalResult(
            case_id=case.id,
            recall_at_k=score,
            retrieved_ids=retrieved_ids,
            passed=score >= case.pass_threshold,
        )
    finally:
        if store is None and owned_store is not None:
            owned_store.close()
