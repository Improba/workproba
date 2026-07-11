# Workproba

> **Statut :** Pivot bureau local-first
> **Date :** 11/07/2026
> **Décideur :** Syl

## Intention

Construire **Workproba**, un équivalent « maison » de **Claude Cowork**, destiné en priorité à des **utilisateurs non-codeurs**, dans le contexte Improba. Application bureau (macOS, Linux, Windows) : l'utilisateur ouvre un dossier projet, l'Imp (agent) manipule les documents en place, exécute du code sous le capot et s'appuie sur une mémoire indexée localement.

## Décision produit

**Application bureau Tauri 2**, local-first. Voir [desktop.md](./desktop.md).

## Objectifs produit

- Bureau multi-OS : macOS (`.dmg`), Linux (`.AppImage`, `.deb`), Windows (`.msi`).
- Dossier local = workspace (pas d'upload).
- Chat agent léché, cartes d'action en langage humain, streaming SSE.
- Mémoire locale : RAG par projet + souvenirs explicites user (global) et project (workspace).
- Plugin Personas : simulation de regards métiers (avis, réunion, discussion).
- Versions automatiques avant modification de fichiers.
- Souveraineté LLM : Ollama, vLLM, Mistral cloud, URLs changeables.

## Non-objectifs (V1 bureau)

- Produit web principal.
- IDE / éditeur de code.
- Code arbitraire utilisateur.
- Sync cloud obligatoire.

## Stack

- **Coque** : Tauri 2 (Rust) — `desktop/`
- **UI** : Quasar 2 + Vue 3 + Anubis — `front/`
- **IA** : Python 3.12 + FastAPI sidecar — `services/ai/`
- **Données** : SQLite + `.workproba/` par workspace + `{app_data}/user/` pour la mémoire globale
- **Cloud (optionnel, archivé)** : voir `legacy/`

## Phasage

1. Scaffold Tauri + commandes dossier
2. Front : mode bureau, open folder
3. Python sidecar local (port 8765)
4. RAG local, extraction, versions
5. V2 : mémoire scopée, plugins (personas), pièces jointes, aperçu documents
6. Packaging multi-OS
7. Sync cloud optionnelle

## Voir aussi

- [desktop.md](./desktop.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)
- [architecture.md](./architecture.md)
- [../desktop/README.md](../desktop/README.md)
