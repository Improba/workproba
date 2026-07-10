# Tests Workproba

Workproba est une application bureau (Tauri + Quasar) avec un sidecar Python. Les tests se répartissent sur trois couches.

> **Node requis :** ≥ 22.22 (Node 24 recommandé). vitest 4 et le build Quasar échouent sur Node 20.

## Sidecar Python (`services/ai/`)

Cadre : **pytest** + `pytest-asyncio`. Les tests hors-ligne sont déterministes (pas de LLM, `TestModel` Pydantic AI en remplacement du modèle réel).

### Organisation

- `tests/conftest.py` — fixtures `FakeProjectClient`, `mistral_config`
- `tests/test_llm_config.py` — `build_model`, `build_model_settings`, `resolve_llm_config`, helpers
- `tests/test_agent_loop.py` — conversion messages (`to_model_messages`), mapping events SSE, robustesse échecs outils (`ModelRetry`), limite itérations
- `tests/test_main_http.py` — `/agent/turn` bout-en-bout via `TestClient` FastAPI (SSE + erreurs de construction)
- `tests/test_rag_store.py` — chunking, `RagStore` sans réseau
- `tests/test_extractor.py` — `is_binary_document`, extraction `.docx`
- `tests/test_live_mistral.py` — **live** (réseau + clé Mistral), ignoré par défaut

### Commandes

```bash
cd services/ai

# Suite hors-ligne (déterministe)
pytest -q

# Tests live contre Mistral (réseau + clé requis)
WP_LIVE_LLM=1 pytest tests/test_live_mistral.py -q
```

### Couverture actuelle

37 tests offline + 2 live. Couvre : config LLM, loop agent (success/échec outils/limite), HTTP SSE, RAG chunking, extraction.

## Frontend (`front/`)

Cadre : **Vitest 4** + `@vue/test-utils`, environment `happy-dom`.

### Organisation

- Unitaires : `front/test/unit/**/*.spec.ts`
- Setup global : `front/test/setup.ts` (i18n + mocks/stubs Quasar)
- Config : `front/vitest.config.ts`
- Composables Workproba : `front/test/unit/composables/useSidecarHealth.spec.ts` (polling santé sidecar)

### Commandes

```bash
cd front

yarn test:unit                 # vitest run + couverture
npx vitest run test/unit --no-coverage   # rapide sans couverture
yarn test:e2e                  # Playwright (smoke)
```

### État connu

- `useSidecarHealth.spec.ts` : 4 cas (connected / error / pas de poll pendant streaming / idempotence).
- Échecs **préexistants** non liés au sidecar : `pages-smoke.spec.ts` et `ssr-paths.spec.ts` (imports de pages non présentes `SpaShell.vue`, `ErrorRouteNotAuthorized.vue`), `layouts.spec.ts` (`StandardLayout` lib-improba).

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
