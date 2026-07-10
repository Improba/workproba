# Architecture Workproba

> **Dernière mise à jour :** 09/07/2026

## Vue d'ensemble

**Workproba** est une application bureau (macOS, Linux, Windows) : l'utilisateur ouvre un **dossier projet local** ; l'agent manipule les fichiers en place, s'appuie sur une mémoire indexée localement et exécute du code sous le capot dans un sandbox isolé.

Documentation détaillée : [desktop.md](./desktop.md), [workspace-storage.md](./workspace-storage.md).

## Stack

| Couche | Technologie | Rôle |
|---|---|---|
| Coque bureau | Tauri 2 (Rust) | Fenêtre, filesystem natif, stockage workspace, packaging |
| Frontend | Quasar 2 + Vue 3 | UI en webview (chat, fichiers) |
| Cœur IA | Python 3.12 + FastAPI (sidecar) | Loop agent, extraction, RAG, sandbox |
| Données locales | `{app_data}/workspaces/{id}/.workproba/` | Conversations, versions, mémoire |
| Agent | Pydantic AI (modèles natifs) | Chat/agent type-safe, outils, streaming |
| LLM | OpenAIChatModel (OpenAI-compat) + AnthropicModel | Ollama local, Mistral cloud, vLLM, OpenAI, Anthropic |
| Embeddings RAG | LiteLLM (`aembedding`) | Ollama, Mistral, OpenAI… |
| RAG | SQLite + sqlite-vec (`memory.db`) | Embeddings + recherche vectorielle par workspace |
| Extraction | pdfplumber, python-docx, openpyxl, python-pptx | PDF/Office digitaux (OCR hors V1) |

## Diagramme

```
┌─────────────────────────────────────────────────────────────────┐
│  Quasar (webview Tauri)                                         │
└──────────────┬─────────────────────────────┬────────────────────┘
               │ HTTP SSE                      │ Tauri invoke
               ▼                               ▼
┌──────────────────────────┐       ┌─────────────────────────────┐
│  Python sidecar :8765    │       │  Tauri / Rust               │
└───────────┬──────────────┘       └──────────────┬──────────────┘
            ▼                                     ▼
┌──────────────────────────┐       ┌─────────────────────────────┐
│  LLM (Ollama / cloud)    │       │  Dossier projet utilisateur │
└──────────────────────────┘       └─────────────────────────────┘
```

## Flux d'un message

1. L'utilisateur ouvre un dossier (Tauri).
2. Quasar envoie le message en SSE vers `127.0.0.1:8765`.
3. Python exécute la loop agent (LLM, tools fichier, sandbox subprocess).
4. Les sessions sont persistées dans `{app_data}/workspaces/{id}/.workproba/`.

## Modules actifs

| Dossier | Rôle |
|---|---|
| `desktop/` | Coque Tauri |
| `front/` | UI Quasar |
| `services/ai/` | Sidecar Python |
| `legacy/` | Ancien stack web NestJS (archivé) |

## Voir aussi

- [desktop.md](./desktop.md)
- [intention.md](./intention.md)
- [stack.md](./stack.md)

## Gestion des modèles LLM depuis l'app

L'accès aux modèles (provider, modèle, base URL, **clé API**) se configure depuis
l'app : écran **« Modèles IA »** (icône réglages en pied de sidebar, route `/settings/models`).

- **Stockage** : `{app_data}/settings.json` (géré par Tauri/Rust, commands
  `get_app_settings` / `save_app_settings`). Clé stockée en clair sur la machine
  locale, comme les autres métadonnées Workproba. Pas dans le dossier client.
- **Plusieurs providers** configurables ; un provider actif pour le **chat**, un
  pour les **embeddings RAG** (la clé est partagée entre chat et embeddings d'une
  même entrée). Bouton **Tester** qui valide la clé via `GET /models` (coût nul).
- **Transit** : à chaque tour, le front envoie la config active dans
  `llm_provider_config` (chat) et `embedding_config` (RAG) du payload
  `/agent/turn`. Le sidecar n'utilise les variables d'environnement `LLM_DEFAULT_*`
  / `LLM_EMBEDDING_*` que comme **repli de dev** si l'app n'envoie rien.
- La clé peut être changée à tout moment depuis l'app, sans toucher au `.env`.
