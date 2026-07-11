# Plugins Workproba (V2)

> **Dernière mise à jour :** 11/07/2026

Workproba V2 étend le cœur agent par un **système de plugins** : outils agent, endpoints HTTP, emplacements UI et stockage namespacé. Le registre côté sidecar (`services/ai/app/plugins/registry.py`) est aligné avec la persistance Tauri (`desktop/src-tauri/src/commands/plugins.rs`).

## Plugins builtin

| ID | Activé par défaut | Rôle |
|---|---|---|
| `workproba.personas` | oui | Personas métiers (avis, réunion, discussion) |
| `workproba.projet` | non | Projets internes, publication d'artefacts |
| `workproba.browser` | non | Navigation web automatisée (expérimental) |
| `workproba.cloud` | non | Sync cloud optionnelle (expérimental) |

L'activation effective dépend des réglages utilisateur (`active_plugins` dans les settings Tauri). Un preset enterprise peut restreindre la liste (`plugins_allowed`).

## Données plugin

Chaque plugin stocke ses données sous :

```
{app_data}/plugins/{plugin_id}/
```

Exemple personas :

```
{app_data}/plugins/workproba.personas/
├── sets.json
├── meetings/{meeting_id}/transcript.json
└── discussions/{discussion_id}/messages.json
```

## Intégration UI

| Emplacement | Fichiers clés | Usage |
|---|---|---|
| Panneau droit | `RightPanel.vue` | Onglet Personas, onglets plugins dynamiques (`usePluginSlots`) |
| Compositeur chat | `ChatView.vue` | Menu « + » : pièces jointes + actions personas |
| Side chat | `SideChatPanel.vue`, `PersonasSideChat.vue` | Discussion / avis en panneau latéral (`Ctrl+Shift+L`) |
| Actions partagées | `usePersonasActions.ts` | Bascule vers une session chat puis déclenche l'action |

Raccourcis utiles : `Ctrl+B` (panneau droit), `Ctrl+Shift+L` (side chat).

## Plugin Personas (`workproba.personas`)

### Concept

Simuler des **regards métiers complémentaires** sur un sujet : RH, juriste, DAF, ingénieur, etc. Le set builtin **Improba** (`id: default`) est fourni en code et non éditable. Des sets personnalisés peuvent être créés via l'API.

### Limites

| Paramètre | Valeur |
|---|---|
| Personas max par session | 5 |
| Rounds réunion max | 5 |
| Rounds réunion par défaut | 3 |

### Modes

| Mode | Endpoint SSE | Description |
|---|---|---|
| Avis | `POST /plugins/personas/ask` | Chaque persona donne son opinion |
| Réunion | `POST /plugins/personas/meeting` | Simulation multi-tours |
| Discussion | `POST /plugins/personas/discuss` | Échange guidé multi-personas |

Paramètre optionnel `include_memory` + `workspace_data_dir` : enrichit le contexte via la recherche mémoire projet (`search_combined`).

### Outils agent

Si le plugin est actif : `ask_personas`, `simulate_meeting`.

### Endpoints CRUD

| Méthode | Route |
|---|---|
| GET/POST | `/plugins/personas/sets` |
| DELETE | `/plugins/personas/sets/{set_id}` |
| GET | `/plugins/personas/meetings`, `/plugins/personas/meetings/{id}` |
| GET | `/plugins/personas/discussions`, `/plugins/personas/discussions/{id}` |
| POST | `/plugins/personas/estimate-cost` |

### Flux UX typique

1. **Depuis le compositeur** : menu « + » → action personas → bascule sur une session chat → `ChatPage` exécute l'action via `usePersonasNavigation`.
2. **Depuis le panneau droit** : onglet Personas → choix du set et de l'action → `usePersonasActions` assure la navigation.
3. **Reprise** : identifiants de réunion/discussion stockés en `sessionStorage` pour relancer ou reprendre.

## Plugin Projet (`workproba.projet`)

Gestion de projets internes et publication d'artefacts depuis l'explorateur ou l'aperçu document.

Endpoints principaux : `/plugins/projet/projects`, `/plugins/projet/publish`, `/plugins/projet/artefacts`.

## Plugins expérimentaux

- **Browser** : `/plugins/browser/navigate`, `/snapshot`, `/action`, `/close`, `/status`
- **Cloud** : `/plugins/cloud/status`, `/config`, `/sync`

Désactivés par défaut ; réservés au dev et aux presets avancés.

## Voir aussi

- [memory.md](./memory.md) — mémoire scopée (utilisée par personas avec `include_memory`)
- [architecture.md](./architecture.md) — shell UI (sidebar, panneau droit)
- [services/ai/README.md](../services/ai/README.md) — catalogue complet des endpoints
