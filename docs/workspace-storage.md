# Stockage par workspace

> **Dernière mise à jour :** 09/07/2026

## Principe

Un **workspace** = un dossier utilisateur sur le disque (ex. `~/Clients/Dupont_2026/`).

Les **fichiers métier** restent dans ce dossier, intacts. Les **métadonnées Workproba** (conversations, versions, mémoire RAG) vivent dans un répertoire applicatif dédié, **pas** dans le dossier client.

Ce modèle suit **Claude Cowork** (métadonnées dans Application Support, fichiers utilisateur en place) et évite les pièges de **Cursor** (hash du chemin → perte d’historique au renommage).

## Arborescence

```
# Fichiers utilisateur (inchangés)
~/Clients/Dupont_2026/
├── Rapport.docx
└── Tableau_CA.xlsx

# Métadonnées Workproba (dossier système)
~/.local/share/fr.improba.workproba/          # Linux
~/Library/Application Support/fr.improba.workproba/   # macOS
%LOCALAPPDATA%/fr.improba.workproba/          # Windows
├── registry.json                           # index des workspaces connus
├── last-project.json                       # dernier dossier ouvert
└── workspaces/
    └── ws_a1b2c3d4.../
        └── .workproba/
            ├── manifest.json               # chemin dossier, titre, dates
            ├── config.json                 # instructions projet (phase ultérieure)
            ├── conversations/
            │   └── sess_....json           # une session = un fichier JSON
            ├── versions/                   # snapshots avant modification IA
            └── memory.db                   # index RAG (phase D)
```

## Identification stable

| Champ | Rôle |
|---|---|
| `workspace_id` | UUID stable (`ws_…`), ne change pas si le dossier est renommé |
| `folder_path` | Chemin actuel du dossier (mis à jour à chaque ouverture) |
| `folder_path_normalized` | Chemin canonique pour retrouver le workspace après renommage partiel |

À l’ouverture d’un dossier : lookup par chemin canonique → réutilisation de l’ID existant ou création d’un nouveau workspace.

## Répartition des responsabilités

| Donnée | Emplacement | Accès |
|---|---|---|
| Documents Office/PDF | Dossier utilisateur | Tauri (liste, open) + Python (read/write) |
| Conversations | `.workproba/conversations/` (système) | Tauri → front Quasar |
| Versions fichier | `.workproba/versions/` (système) | Python sidecar |
| Mémoire RAG | `.workproba/memory.db` (système) | Python sidecar (phase D) |
| Registre projets | `registry.json` | Tauri |

Le sidecar Python reçoit `workspace_data_dir` dans le payload `/agent/turn` pour écrire versions et (plus tard) mémoire au bon endroit.

## Migration V1

Les sessions stockées en `localStorage` (`workproba:sessions:{path}`) sont **importées automatiquement** au premier accès d’un workspace, puis supprimées du navigateur.

## Comparaison concurrence

| Outil | Fichiers utilisateur | Métadonnées app |
|---|---|---|
| **Claude Cowork** | Dossier local monté tel quel | `Application Support/Claude-3p/` |
| **Cursor** | `.cursor/` = config seulement | `workspaceStorage/{hash}/` (fragile au déplacement) |
| **Workproba** | Dossier client sans pollution | `{app_data}/workspaces/{uuid}/.workproba/` |

## Voir aussi

- [desktop.md](./desktop.md)
- [architecture.md](./architecture.md)
