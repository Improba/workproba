# Workproba AI Core

Sidecar Python de l'application bureau Workproba : loop agent, providers LLM, extraction, RAG, mémoire scopée, plugins, sandbox subprocess.

Écoute sur `127.0.0.1:8765` (loopback uniquement en production).

## Développement

```bash
./run_dev.sh
# ou depuis la racine : make dev-ai
# ou tout-en-un : make dev
```

## Sécurité

La plupart des endpoints exigent le header `X-Internal-Secret` (valeur `INTERNAL_SECRET` côté sidecar, `DESKTOP_INTERNAL_SECRET` côté front). Les flux SSE agent et personas sont accessibles sur loopback sans secret.

## Endpoints

### Santé et capacités

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| GET | `/health` | non | Santé du sidecar |
| GET | `/capabilities` | oui | Capacités sidecar (plugins, OCR, …) |

### LLM et utilitaires

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| POST | `/llm/test` | oui | Test connexion provider |
| POST | `/llm/sets/test` | oui | Test jeu de providers (chat + embeddings) |
| POST | `/util/title` | oui | Génération titre de conversation |
| POST | `/util/summarize` | oui | Résumé de texte |

### Agent

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| POST | `/agent/turn` | non (SSE loopback) | Tour agent, flux SSE |
| POST | `/agent/confirm` | oui | Confirmation action sensible |
| POST | `/agent/plan/approve` | oui | Approbation plan agent |
| POST | `/agent/index-workspace` | oui | Indexation RAG bulk du dossier projet |
| POST | `/agent/reprocess-attachment` | oui | Reprocess OCR/vision d'une pièce jointe |

### Documents et versions

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| GET | `/documents/preview` | oui | Aperçu HTML/texte d'un fichier |
| POST | `/documents/preview-change` | oui | Diff avant écriture |
| GET | `/versions` | oui | Liste versions d'un fichier |
| POST | `/versions/restore` | oui | Restauration d'une version |

### Mémoire

Scopes `user` (global) et `project` (workspace). Voir [docs/memory.md](../../docs/memory.md).

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| GET | `/memory/items` | oui | Liste souvenirs explicites |
| GET | `/memory/search` | oui | Recherche (RAG + explicite sur project) |
| POST | `/memory/add` | oui | Ajout manuel |
| POST | `/memory/forget` | oui | Suppression par id |
| DELETE | `/memory` | oui | Effacement (conversations, mémoires, tout) |

### Plugin Personas (`workproba.personas`)

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| GET/POST | `/plugins/personas/sets` | oui | Liste / création sets |
| DELETE | `/plugins/personas/sets/{set_id}` | oui | Suppression set custom |
| POST | `/plugins/personas/ask` | non (SSE) | Avis par persona |
| POST | `/plugins/personas/meeting` | non (SSE) | Réunion simulée |
| POST | `/plugins/personas/discuss` | non (SSE) | Discussion multi-tours |
| POST | `/plugins/personas/estimate-cost` | oui | Estimation coût tokens |
| GET | `/plugins/personas/meetings` | oui | Historique réunions |
| GET | `/plugins/personas/meetings/{id}` | oui | Détail réunion |
| GET | `/plugins/personas/discussions` | oui | Historique discussions |
| GET | `/plugins/personas/discussions/{id}` | oui | Détail discussion |

### Plugin Projet (`workproba.projet`)

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| GET/POST | `/plugins/projet/projects` | oui | Projets internes |
| POST | `/plugins/projet/publish` | oui | Publication artefact |
| GET | `/plugins/projet/artefacts` | oui | Liste artefacts |

### Plugins expérimentaux

| Plugin | Routes principales |
|---|---|
| Browser | `/plugins/browser/navigate`, `/snapshot`, `/action`, `/close`, `/status` |
| Cloud | `/plugins/cloud/status`, `/config`, `/sync` |

### Audit

| Méthode | Route | Secret | Rôle |
|---|---|---|---|
| GET | `/audit` | oui | Entrées journal |
| GET | `/audit/export` | oui | Export CSV |
| GET/POST | `/audit/config` | oui | Configuration rétention |

## Indexation RAG du workspace

`POST /agent/index-workspace` parcourt le dossier projet, extrait le texte des fichiers éligibles (texte + Office : PDF/DOCX/XLSX/PPTX) et les indexe dans le `RagStore` du workspace (`memory.db`, scope project). Dossiers sensibles (`.git`, `node_modules`, …) et chemins interdits (`.env`, …) ignorés. Bornes : `INDEX_MAX_FILES` / `INDEX_MAX_FILE_BYTES` / `INDEX_MAX_TOTAL_CHARS`. Si le RAG est désactivé (pas de modèle d'embedding), renvoie `enabled=false` sans erreur.

## Outils agent

Outillage de base : lecture/écriture documents, recherche KB, sandbox, versions, etc.

Outillage mémoire : `remember` (scope user/project), injection automatique via `memory_prompt`.

Outillage plugins (si actifs) : `ask_personas`, `simulate_meeting` (personas), outils projet/browser/cloud selon manifest.

Registre : `app/plugins/registry.py`.

## Variables

Voir `.env.example`.

## Tests

```bash
# Suite hors-ligne (déterministe, via TestModel — pas de LLM requis)
.venv/bin/pytest -q

# Tests live contre Mistral (réseau + clé requis)
WP_LIVE_LLM=1 .venv/bin/pytest tests/test_live_mistral.py -q
```

Couverture : agent, mémoire scopée, plugins, documents, audit, attachments, RAG, HTTP SSE. Voir [docs/testing.md](../../docs/testing.md).

## Limites actuelles

- Agent : [Pydantic AI](https://ai.pydantic.dev/) (modèles natifs). Routage via `OpenAIChatModel` + `AnthropicModel`.
- Embeddings RAG : LiteLLM (`litellm.aembedding`). Désactivé si `LLM_EMBEDDING_MODEL` vide → repli recherche substring.
- Extraction : PDF texte, Word, Excel, PowerPoint. OCR / PDFs scannés hors scope V1.
- Durable (Temporal/Inngest) : reporté.
