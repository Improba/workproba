# Product eval harness

Offline-first evaluation cases for the Workproba AI sidecar. Live runs use the same **remote Mistral** stack as production (API cloud). They do **not** start a local LLM on the laptop.

## Purpose

Two complementary checks:

| Kind | What it measures | Needs network? |
|---|---|---|
| **Retrieval** | Does RAG return the right documents for a query? (`recall@k`) | Yes (embeddings `mistral-embed`) |
| **Answer judge** | Does a fixed answer match a rubric? (score 1–5) | Yes (chat `mistral-small-latest`) |

Offline CI only validates JSON schemas and metric helpers. Quality checks run when `WP_EVAL=1`.

## What the Mistral judge does

The judge is an **LLM-as-judge**: a second remote call to Mistral that grades an answer, it does not run the agent loop.

Flow for an `answer_judge` case:

1. Load a golden JSON case: `question`, fixed `candidate_answer`, `criteria` (rubric), `pass_min_score`.
2. Call Mistral (`mistral-small-latest` via OpenAI-compatible API) with a short system prompt: score 1–5 against the rubric.
3. Parse a structured verdict `{ "score": int, "rationale": str }`.
4. Pass if `score >= pass_min_score`.

First-slice goal: prove judge plumbing and regression on fixed goldens (example: `2+2` → `"4"`). Later slices can feed real agent outputs into the same judge.

The judge is **not** used for retrieval cases (those use embeddings + `recall@k` only).

## Synthetic métier cases

Ten fictional golden cases (personas **Sylvie**, assistante RH bureautique, and **Marc**, technicien non-info) complement the two original smoke cases. All names, companies and amounts are invented; no real PII.

| Id | Kind | Persona / theme |
|---|---|---|
| `retrieval_rh_conges` | retrieval | Sylvie — règles congés payés |
| `retrieval_rh_entretien_annuel` | retrieval | Sylvie — trame entretien annuel |
| `retrieval_devis_fournisseur` | retrieval | Sylvie — montant devis fournisseur |
| `answer_rh_mail_sans_jargon` | answer_judge | Sylvie — reformulation mail RH |
| `answer_contrat_extraire_dates` | answer_judge | Sylvie — extraction dates contrat |
| `answer_cr_cinq_puces` | answer_judge | Sylvie — CR réunion en 5 puces |
| `answer_rh_refus_conge_poli` | answer_judge | Sylvie — refus de congé poli |
| `retrieval_chantier_epi` | retrieval | Marc — EPI chantier Nord |
| `retrieval_intervention_panne` | retrieval | Marc — procédure panne presse |
| `answer_tech_checklist_maintenance` | answer_judge | Marc — checklist maintenance |

Original smoke cases: `retrieval_support_client`, `answer_factual_short`.

## Layout

```
evals/
  cases/           # JSON golden cases
  schema.py        # Pydantic models
  metrics.py       # recall@k, precision@k
  judge.py         # remote Mistral LLM-as-judge
  retrieval_eval.py
  answer_eval.py
  __main__.py      # python -m evals
```

## Case formats

### Retrieval (`type: "retrieval"`)

| Field | Description |
|---|---|
| `id` | Case identifier |
| `documents` | `[{id, title, text}]` to index |
| `query` | Search query |
| `relevant_ids` | Document ids that must appear in top-k |
| `k` | Top-k limit (default 2) |
| `pass_threshold` | Minimum recall@k to pass (default 1.0) |

### Answer judge (`type: "answer_judge"`)

| Field | Description |
|---|---|
| `id` | Case identifier |
| `question` | User question |
| `candidate_answer` | Fixed answer to judge (golden string) |
| `criteria` | Short rubric for the judge |
| `pass_min_score` | Minimum score 1-5 to pass (default 3) |

## Environment

| Variable | Role |
|---|---|
| `WP_EVAL=1` | Gate live eval runs (distinct from `WP_LIVE_LLM`; CI stays green) |
| `MISTRAL_API_KEY` or `LLM_DEFAULT_API_KEY` | API key (env only, never hardcoded) |
| `LLM_DEFAULT_BASE_URL` | OpenAI-compatible base URL (default `https://api.mistral.ai/v1`) |

In this monorepo, the Mistral key often lives in the **workspace root** `.env` (imp-work). Export it before running, for example:

```bash
set -a && source ../../.env && set +a   # from services/ai, adjust path as needed
# or from repo root:
set -a && source .env && set +a
```

## Commands

```bash
cd services/ai

# Offline: schema + metrics unit tests (CI)
.venv/bin/pytest tests/test_eval_metrics.py tests/test_eval_schema.py -q

# Live evals (network + key)
WP_EVAL=1 .venv/bin/pytest tests/test_eval_live.py -q

# CLI summary (list cases offline; run live when WP_EVAL=1)
python -m evals
WP_EVAL=1 python -m evals
```
