# Architecture Workproba

> **Dernière mise à jour :** 11/07/2026

## Vue d'ensemble

**Workproba** est une application bureau (macOS, Linux, Windows) : l'utilisateur ouvre un **dossier projet local** ; l'agent manipule les fichiers en place, s'appuie sur une mémoire indexée localement et exécute du code sous le capot dans un sandbox isolé.

Documentation détaillée : [desktop.md](./desktop.md), [workspace-storage.md](./workspace-storage.md).

## Stack

| Couche | Technologie | Rôle |
|---|---|---|
| Coque bureau | Tauri 2 (Rust) | Fenêtre, filesystem natif, stockage workspace, packaging |
| Frontend | Quasar 2 + Vue 3 | UI en webview (chat, fichiers) |
| Cœur IA | Python 3.12 + FastAPI (sidecar) | Loop agent, extraction, RAG, sandbox |
| Données locales | `{app_data}/` (workspaces, user, plugins, audit) | Conversations, versions, mémoire, plugins |
| Agent | Pydantic AI (modèles natifs) | Chat/agent type-safe, outils, streaming |
| LLM | OpenAIChatModel (OpenAI-compat) + AnthropicModel | Ollama local, Mistral cloud, vLLM, OpenAI, Anthropic |
| Embeddings RAG | LiteLLM (`aembedding`) | Ollama, Mistral, OpenAI… |
| RAG | SQLite + sqlite-vec (`memory.db`) | Embeddings + recherche vectorielle par projet ; souvenirs explicites user/projet |
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
5. Les souvenirs explicites et le RAG projet alimentent le contexte agent (voir [memory.md](./memory.md)).

## Shell UI (layout bureau)

Le layout principal (`WorkprobaLayout.vue`) organise l'écran :

```
WorkprobaTitleBar
├── WorkspaceSidebar (gauche, mode rail responsive)
├── zone centrale (router-view : chat, réglages, onboarding)
├── RightPanel (droite, Ctrl+B) — fichiers · aperçu · personas · plugins
└── SideChatPanel (Ctrl+Shift+L) — discussion personas latérale
```

**Sidebar** (`WorkspaceSidebar.vue`) : arbre workspaces → conversations, indicateur de streaming, profil utilisateur, accès mémoire et réglages modèles.

**Panneau droit** (`RightPanel.vue`) : explorateur de fichiers, aperçu document (`DocumentPreview` + `VersionsPanel`), onglet Personas si plugin actif, onglets plugins dynamiques.

**Chat** (`ChatView.vue`) : compositeur en pilule, menu « + » (pièces jointes + actions personas), contrôle modèle/raisonnement, drag-and-drop de fichiers.

## Pièces jointes et aperçu documents

- **Attachments** : stockés dans `{workspace_data_dir}/attachments/{session_id}/{attachment_id}/`. Reprocess OCR/vision via `POST /agent/reprocess-attachment`.
- **Aperçu HTML/texte** : sidecar `GET /documents/preview` (contenu rendu côté webview).
- **Aperçu images** : `convertFileSrc` Tauri avec feature `protocol-asset` (`tauri.conf.json` → `assetProtocol`).
- **Diff avant écriture** : `POST /documents/preview-change`.

## Plugins V2

Quatre plugins builtin (personas activé par défaut). Voir [plugins.md](./plugins.md).

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
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)

## Gestion des modèles LLM depuis l'app

L'accès aux modèles (provider, modèle, base URL, **clé API**) se configure depuis
l'app : écran **« Modèles IA »** (icône réglages en pied de sidebar, route `/settings/models`).

- **Stockage** : `{app_data}/settings.json` (géré par Tauri/Rust, commands
  `get_app_settings` / `save_app_settings`). Clé stockée en clair sur la machine
  locale, comme les autres métadonnées Workproba. Pas dans le dossier client.
- **Plusieurs providers** configurables ; un provider actif pour le **chat**, un
  pour les **embeddings RAG** (la clé est partagée entre chat et embeddings d'une
  même entrée). Bouton **Tester** qui valide la clé via `GET /models` (coût nul).
- **Transit** : à chaque tour agent, le front envoie le **`provider_set`** actif
  (avec overrides de session : modèle et raisonnement par conversation) dans le
  payload `/agent/turn`. En l'absence de set, repli sur `llm_provider_config` +
  `embedding_config` (legacy). Le sidecar priorise toujours `provider_set` côté
  `resolve_llm_config`. Les variables d'environnement `LLM_DEFAULT_*` /
  `LLM_EMBEDDING_*` ne servent qu'en **repli de dev**.
- **Clé API** : pour les moteurs cloud (ex. Mistral), la clé est saisie dans
  Réglages → Modèles IA et stockée dans `set.chat.apiKey`. Si elle manque, le
  front bloque l'envoi et le sidecar renvoie `api_key_missing`. Le champ
  `api_key_ref` des sets intégrés est un marqueur interne ; seule `api_key`
  compte à l'exécution.
- La clé peut être changée à tout moment depuis l'app, sans toucher au `.env`.

## Modèle et raisonnement par conversation

L'écran « Modèles IA » choisit un **fournisseur/préréglage** (provider, base URL,
clé, modèle par défaut). Le **modèle précis** et le **niveau de raisonnement** se
choisissent **par conversation**, directement dans le compositeur du chat, pas dans
les réglages.

- **Compositeur** (`ChatView` + `ChatModelControl`) : un contrôle compact affiche
  le modèle courant et le niveau de raisonnement. Le menu propose les modèles
  suggérés du provider (`utils/modelCatalog.ts`) et les niveaux de raisonnement
  supportés par le modèle (`utils/reasoningSupport.ts`), avec une aide verbose par
  option pour les utilisateurs non techniques.
- **Persistance par session** : le modèle et l'effort de raisonnement sont
  sauvegardés **avec** la conversation côté Tauri (`ConversationSession.model` et
  `reasoningEffort`). Au chargement d'une session, le modèle sauvegardé est
  restauré s'il reste applicable au provider actif ; sinon il retombe sur le modèle
  par défaut du provider (logique `isModelApplicable` + watch du provider actif).
- **Transit du tour** : `buildActiveProviderSet` applique les overrides de
  session au set actif ; `useLlmSessionContext` propage ces overrides aux
  personas et aux pièces jointes tant que la conversation est active.
  `mergeLlmConfigsWithSessionReasoning` (`utils/llmRouting.ts`) ne sert qu'au
  repli legacy sans set.
- **Étiquettes FR** : `Aucun` · `Faible` · `Moyen` · `Élevé`.

## UX du chat (compositeur & raisonnement)

- **Compositeur en pilule** : à vide, le champ et les actions (modèle/raisonnement,
  envoyer) tiennent sur une ligne. Dès la saisie, le champ s'étend en multi-lignes
  et les actions passent en barre dessous, le champ prenant toute la largeur.
- **Envoi** : le champ se vide, le message utilisateur apparaît immédiatement
  (poussé synchrone dans `useChatStream.send`) et la vue défile vers le bas.
  `MessageList.getScrollTarget` détecte le conteneur réellement scrollable
  (double conteneur `q-scroll-area` + `DynamicScroller`) pour cibler le bon.
- **Raisonnement en cours** : un **spinner** rotatif + libellé « Raisonnement en
  cours… » s'affiche dans la zone raisonnement (`ThinkingCard`) pendant le
  streaming. Un placeholder « Le modèle réfléchit… » couvre le délai d'amorçage
  entre l'envoi et le premier event (`thinking_start` ou token).
