# Mémoire Workproba

> **Dernière mise à jour :** 11/07/2026

Workproba combine deux mécanismes complémentaires :

1. **RAG projet** — index vectoriel des documents du dossier (recherche sémantique).
2. **Souvenirs explicites** — faits mémorisés volontairement, par l'utilisateur ou par l'agent.

Les souvenirs explicites existent à **deux scopes** ; le RAG reste attaché au **projet** (workspace).

## Scopes

| Scope | Portée | Fichier SQLite | Usage typique |
|---|---|---|---|
| `user` | Global, partagé entre tous les espaces | `{app_data}/user/memory.db` | Préférences, contexte personnel, habitudes |
| `project` | Un workspace | `{workspace_data_dir}/memory.db` | Faits métier du dossier client, décisions projet |

`{app_data}` = dossier applicatif Workproba (`~/.local/share/fr.improba.workproba/` sur Linux, etc.).
`{workspace_data_dir}` = `{app_data}/workspaces/{workspace_id}/.workproba/`.

La résolution des chemins est centralisée dans `services/ai/app/memory_stores.py`.

## RAG vs souvenirs explicites

Sur le scope **project**, les deux cohabitent dans la même base `memory.db` :

- **RAG** : chunks de documents indexés via `/agent/index-workspace` ou lors de lectures agent. Recherche vectorielle (sqlite-vec) ou repli substring si embeddings désactivés.
- **Souvenirs explicites** : entrées texte ajoutées manuellement (UI) ou via l'outil agent `remember`. Source enregistrée : `manual` ou `agent`.

Sur le scope **user**, seuls les souvenirs explicites sont stockés (pas d'indexation RAG des dossiers).

## Injection dans l'agent

À chaque tour, l'outil `memory_prompt` (`services/ai/app/agent/tools.py`) injecte dans le system prompt les souvenirs explicites récents :

- jusqu'à 64 entrées **user** ;
- jusqu'à 64 entrées **project**.

L'agent peut aussi mémoriser via l'outil `remember(content, scope="user"|"project")` (défaut : `project`).

## API REST (sidecar)

Tous les endpoints mémoire exigent le header `X-Internal-Secret` (loopback uniquement).

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/memory/items?workspace_data_dir=&memory_scope=user\|project` | Liste des souvenirs explicites |
| GET | `/memory/search?query=&memory_scope=user\|project\|all` | Recherche (project = RAG + explicite ; user = explicite seul) |
| POST | `/memory/add` | Ajout manuel (`content`, `memory_scope`) |
| POST | `/memory/forget` | Suppression par `memory_id` |
| DELETE | `/memory` | Effacement (`scope`: `all` / `memories` / `conversations` ; `confirmed: true`) |

Le front appelle ces routes via `front/src/services/aiSidecar.ts` et le composable `useMemory.ts`.

## Interface utilisateur

Le panneau **Mémoire** (`MemoryPanel.vue`) s'ouvre depuis la sidebar (icône cerveau, `WorkspaceSidebar.vue`).

Fonctionnalités :

- onglets **Utilisateur** / **Projet** ;
- ajout manuel d'un souvenir ;
- recherche dans le scope actif ;
- suppression d'une entrée.

## Voir aussi

- [workspace-storage.md](./workspace-storage.md) — arborescence disque
- [architecture.md](./architecture.md) — vue d'ensemble
- [services/ai/README.md](../services/ai/README.md) — catalogue API sidecar
