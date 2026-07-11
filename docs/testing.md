# Tests Workproba

Workproba est une application bureau (Tauri + Quasar) avec un sidecar Python. Les tests se répartissent sur trois couches.

> **Node requis :** ≥ 22.22 (Node 24 recommandé). vitest 4 et le build Quasar échouent sur Node 20.

## Sidecar Python (`services/ai/`)

Cadre : **pytest** + `pytest-asyncio`. Les tests hors-ligne sont déterministes (pas de LLM, `TestModel` Pydantic AI en remplacement du modèle réel).

### Organisation

- `tests/conftest.py` — fixtures partagées
- `tests/test_llm_config.py` — `build_model`, settings, helpers
- `tests/test_agent_loop.py` — conversion messages, events SSE, robustesse outils
- `tests/test_agent_remember.py` — outil `remember`, injection mémoire
- `tests/test_main_http.py` — `/agent/turn`, CORS preflight, erreurs HTTP
- `tests/test_rag_store.py` — chunking, `RagStore` sans réseau
- `tests/test_memory_scope.py`, `test_memory_extended.py` — scopes user/projet
- `tests/test_plugin_personas.py`, `test_personas_estimate_cost.py` — plugin personas
- `tests/test_plugin_projet.py`, `test_plugin_projet_http.py` — plugin projet
- `tests/test_plugin_browser.py`, `test_plugin_cloud.py` — plugins expérimentaux
- `tests/test_documents_preview.py`, `test_preview_change.py` — aperçu documents
- `tests/test_attachments.py`, `test_reprocess_attachment.py` — pièces jointes
- `tests/test_audit.py`, `test_audit_export.py` — journal d'audit
- `tests/test_versions.py` — versions fichier
- `tests/test_extractor.py` — extraction `.docx`, binaire
- `tests/test_live_mistral.py` — **live** (réseau + clé Mistral), ignoré par défaut

### Commandes

```bash
cd services/ai

# Suite hors-ligne (déterministe)
.venv/bin/pytest -q

# Tests live contre Mistral (réseau + clé requis)
WP_LIVE_LLM=1 .venv/bin/pytest tests/test_live_mistral.py -q
```

### Couverture actuelle

Exécuter `pytest -q` pour le décompte à jour (environ **336 tests** offline + quelques skips, plus 2 live). Couvre : agent, mémoire scopée, plugins, documents, audit, attachments, RAG, HTTP SSE.

## Frontend (`front/`)

Cadre : **Vitest 4** + `@vue/test-utils`, environment `happy-dom`.

### Organisation

- Unitaires : `front/test/unit/**/*.spec.ts`
- Setup global : `front/test/setup.ts` (i18n + mocks/stubs Quasar)
- Config : `front/vitest.config.ts`
- Composables Workproba : `useSidecarHealth.spec.ts`, etc.

### Commandes

```bash
cd front

yarn test:unit                 # vitest run + couverture
npx vitest run test/unit --no-coverage   # rapide sans couverture
yarn test:e2e                  # Playwright (smoke)
```

### État connu

- `useSidecarHealth.spec.ts` : polling santé sidecar (connected / error / streaming).
- Échecs **préexistants** non liés au sidecar : `pages-smoke.spec.ts` et `ssr-paths.spec.ts` (imports de pages absentes), `layouts.spec.ts` (`StandardLayout` lib-improba).

### Sélection des tests par risque

- **Composables / utils** : Vitest unitaire avec mocks (`vi.fn`, mock des services).
- **Composants** : Vitest + Vue Test Utils (props, emits, slots, états observables).
- **Pages** : Vitest ciblé rendu + interactions ; e2e Playwright si flux critique.
- Privilégier des tests rapides et déterministes ; limiter les e2e au parcours métier critique.

## Coque Tauri (`desktop/`)

Pas de suite automatisée. Vérification de compilation :

```bash
cd desktop/src-tauri && cargo check
```

## CI

Pas de CI configurée pour le pivot bureau (à mettre en place avec la phase E / packaging). Cibles futures : `cargo check`, `pytest -q`, `yarn test:unit`, `yarn build`.

## Référence

- [Vue.js Testing Guide](https://vuejs.org/guide/scaling-up/testing)
- [Pydantic AI testing](https://ai.pydantic.dev/testing/)
