# Workproba Desktop

> **Statut :** Décision produit — pivot bureau
> **Dernière mise à jour :** 11/07/2026

## Décision

Workproba devient une **application bureau local-first** (type Claude Cowork), multi-plateforme :

| OS | Formats cibles |
|---|---|
| macOS | `.app`, `.dmg` |
| Linux | `.deb`, `.rpm`, `.AppImage` |
| Windows | `.msi`, `.exe` (NSIS) |

Technologie retenue : **Tauri 2** (coque Rust légère + webview système + UI Quasar existante).

L'agent IA reste en **Python** (sidecar). Le Rust ne remplace pas Python : il fournit le pont natif (filesystem, fenêtre, permissions, packaging).

## Métaphore produit (non-codeurs)

L'utilisateur ouvre **un dossier projet** sur son disque. L'Imp (agent) travaille dedans :

- lit et modifie Word, Excel, PDF ;
- exécute du code **sous le capot** dans un sandbox subprocess local ;
- s'appuie sur une **mémoire** indexée à partir des documents du dossier.

Concepts UI principaux :

| Concept affiché | Signification |
|---|---|
| **Dossier** | Le projet client (filesystem local) |
| **Conversation** | L'échange avec l'Imp |
| **Mémoire** | Ce que l'outil sait du dossier (RAG projet + souvenirs user/projet) |
| **Personas** | Regards métiers simulés (plugin V2, avis / réunion / discussion) |

## Architecture bureau

```
┌─────────────────────────────────────────────────────────────┐
│  Quasar + Anubis (webview Tauri)                            │
│  chat · fichiers · résultats                                │
└──────────────┬──────────────────────────┬───────────────────┘
               │ fetch SSE                  │ invoke() Tauri
               ▼                            ▼
┌──────────────────────────┐    ┌─────────────────────────────┐
│  Python sidecar          │    │  Tauri / Rust               │
│  127.0.0.1:8765          │    │  dossier · open_path · etc. │
│  agent · RAG · sandbox   │    └──────────────┬──────────────┘
└──────────────┬───────────┘                   │ read/write
               │                                ▼
               ▼                    ┌─────────────────────────────┐
┌──────────────────────────┐       │  Dossier projet utilisateur │
│  LLM (Ollama/vLLM/…)     │       │  Dossier projet utilisateur │
└──────────────────────────┘       └─────────────────────────────┘
               │
               ▼
┌──────────────────────────┐
│  {app_data}/workspaces/  │
│  {id}/.workproba/          │
└──────────────────────────┘
```

Le chat **ne passe pas par Rust** : la webview Quasar appelle directement le sidecar Python en HTTP/SSE. Tauri intervient pour le filesystem natif (ouvrir dossier, lister fichiers, ouvrir un document).

### Stockage par workspace

Les métadonnées Workproba vivent dans le **dossier applicatif**, pas dans le dossier client. Voir [workspace-storage.md](./workspace-storage.md).

```
{app_data}/workspaces/{workspace_id}/.workproba/
├── manifest.json
├── conversations/
├── versions/
├── attachments/
└── memory.db          # RAG projet + souvenirs explicites

{app_data}/user/memory.db   # souvenirs utilisateur globaux
{app_data}/plugins/         # données plugins (personas, …)
```

## Flux d'un message (bureau)

```
[Quasar webview] --HTTP SSE--> [Python sidecar :8765]
       │
       └── invoke Tauri (dossier, open_path) — hors chemin chat
```

1. L'utilisateur sélectionne un dossier projet (dialogue Tauri).
2. Tauri enregistre le workspace (ID stable + chemin) ; le front garde le chemin et `workspace_id`.
3. L'utilisateur envoie un message dans le chat.
4. Quasar appelle `POST http://127.0.0.1:8765/agent/turn` (SSE direct). Le payload
   embarque la surcharge **modèle + niveau de raisonnement** de la conversation
   (persistée en session), clampée contre les capacités du modèle.
5. Python exécute la loop agent : LLM, tools fichier, recherche locale, sandbox subprocess.
6. Les événements SSE sont affichés dans le chat (tokens, raisonnement avec spinner,
   appels d'outil) ; les sessions sont persistées dans `{app_data}/workspaces/{id}/.workproba/conversations/`.

**Pas de serveur web** dans le chemin produit. L'ancien stack NestJS est dans `legacy/`.

## Rôles par couche

| Couche | Langage | Rôle |
|---|---|---|
| UI | TypeScript / Quasar | Chat, fichiers, résultats, onboarding |
| Coque bureau | Rust / Tauri | Fenêtre, OS APIs, filesystem, packaging |
| Cœur IA | Python / FastAPI | Agent loop, extraction, RAG, sandbox subprocess |
| Données locales | `{app_data}/workspaces/{id}/.workproba/` | Sessions, versions, mémoire |
| Cloud (archivé) | `legacy/` | Ancien stack NestJS |

## Sécurité et confiance (UX)

- **Mode prudent** (défaut, phase ultérieure) : confirmation avant modification.
- **Versions automatiques** : copie dans `.workproba/versions/` avant écriture (Python `LocalProjectClient`).
- **Périmètre** : l'agent ne sort pas du dossier projet.
- **Sandbox** : subprocess Python local, sans réseau, timeout configurable.
- **Sidecar** : joignable sur loopback uniquement (`127.0.0.1`, `::1`).

## Packaging Python (sidecar)

En production : PyInstaller → binaire `workproba-ai-<triple>` dans `desktop/src-tauri/binaries/`, référencé par `bundle.externalBin`.

En développement : `make dev-ai` ou `services/ai/run_dev.sh` (port `8765`).

## Phasage

| Phase | Statut | Contenu |
|---|---|---|
| **A** | Fait | Scaffold Tauri, commandes dossier, doc |
| **B** | Fait | UI open folder, liste fichiers, sessions locales |
| **C** | Fait | SSE direct Python, `LocalProjectClient`, sandbox subprocess |
| **D** | Fait | RAG SQLite, extraction Office, monitoring sidecar |
| **D+** | Fait | Mémoire scopée user/projet, plugins V2 (personas), pièces jointes, aperçu documents, audit |
| **E** | À faire | Packaging multi-OS + PyInstaller sidecar |
| **F** | À faire | Sync cloud optionnelle (NestJS) |

### Phase D — validation

- **Sidecar (Python)** : chat streaming, outils fichier, RAG, mémoire scopée, plugins personas. Suite pytest : voir [testing.md](./testing.md) (`pytest -q` pour le décompte actuel).
- **Coque Rust** : spawn sidecar venv-aware + `ai_sidecar_status` + `protocol-asset` pour aperçu images. `cargo check` OK.
- **Front** : `WorkprobaLayout` (sidebar, panneau droit, side chat), `useSidecarHealth`, plugin personas intégré au compositeur.
- **Run desktop end-to-end** : `make dev`, ouvrir un dossier, tester chat, mémoire, personas, aperçu document.

## Reste à faire

### Produit (phases E & F)

- **Phase E — Packaging multi-OS** : PyInstaller du sidecar (`workproba-ai-<triple>` dans `desktop/src-tauri/binaries/`, référencé par `bundle.externalBin`) ; build `.dmg`/`.app` (macOS), `.deb`/`.rpm`/`.AppImage` (Linux), `.msi`/`.exe` NSIS (Windows) ; CI de build par triple.
- **Phase F — Sync cloud optionnelle** : réutilisation du stack NestJS archivé (`legacy/`) pour synchronisation optionnelle des workspaces.

### Fonctionnel (hors V1, à prioriser)

- **OCR / PDFs scannés** : `LocalExtractor` gère PDF texte (pdfplumber), Word/Excel/PowerPoint. OCR (Docling et/ou Mistral OCR) non implémenté — requis pour PDFs scannés et images. Décision utilisateur déjà actée (« Docling pour l'OCR ») : intégrer Docling comme extracteur lourd avec repli Mistral OCR.
- **Durable (Temporal/Inngest)** : reporté. La loop agent actuelle est synchrone (un tour SSE). Pas de reprise/persistance de workflow long en cas de crash. À réintroduire si des tâches longues (indexation gros corpus, traitements par lots) le justifient.
- **Mode prudent** : confirmation avant modification de fichiers (défaut futur). Actuellement les versions automatiques (`.workproba/versions/`) sont la seule garde-fou.

### Qualité / intégration

- **Run desktop e2e sur machine avec affichage** : valider le tour de chat réel dans la webview (streaming, badge sidecar, rendu des tool calls). Le sidecar est validé en live hors webview.
- **Tests front préexistants** : `pages-smoke.spec.ts` et `ssr-paths.spec.ts` référencent des pages absentes (`SpaShell.vue`, `ErrorRouteNotAuthorized.vue`) ; à corriger ou supprimer. `layouts.spec.ts` (`StandardLayout` lib-improba) en échec.
- **CI** : aucune CI sur le pivot bureau. À mettre en place avec la phase E (`cargo check`, `pytest -q`, `yarn test:unit`, `yarn build`).
- **Lint front** : 7 erreurs préexistantes dans `lib-improba/` (non introduites par le sidecar).

## Développement local

```bash
make dev          # recommandé : sidecar + Tauri/Quasar
# ou
make dev-ai       # terminal 1
make dev-desktop  # terminal 2
```

Rebuild et hot reload (front HMR, Rust recompile + redémarre la fenêtre, Python `--reload` via `dev-ai`) : voir [desktop/README.md § Rebuild et hot reload](../desktop/README.md#rebuild-et-hot-reload).

## Voir aussi

- [architecture.md](./architecture.md)
- [memory.md](./memory.md)
- [plugins.md](./plugins.md)
- [desktop/README.md](../desktop/README.md)
- [intention.md](./intention.md)
