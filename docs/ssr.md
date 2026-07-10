# SSR (Server-Side Rendering)

Ce document décrit le setup SSR du front Quasar du monorepo template Improba.
Le SSR est optionnel mais activé par défaut en dev Docker. Le CSR (client-side rendering) reste disponible et fonctionne comme avant.

## Principes

- Les **routes publiques statiques** (pages vitrines, démos, pages d'erreur) sont rendues côté serveur : premier rendu HTML rapide, SEO et open-graph corrects, hydratation côté client ensuite.
- Les **routes authentifiées** (`requiresAuth: true` ou `auth: true`), les **routes dynamiques** et les **chemins inconnus** ne sont PAS rendus côté serveur : le serveur renvoie une coquille CSR (SPA shell) et le navigateur prend le relais. On évite ainsi d'exposer des pages protégées et de polluer l'état serveur avec des tokens.
- Une route peut explicitement sortir du SSR avec `meta.ssr = false` (voir `src/router/meta.ts`, constantes `CSR_META`, `AUTHENTICATED_CSR_META`, `ADMIN_CSR_META`).

## Fichiers mis en place

```
front/
├── src-ssr/
│   ├── server.ts                       # webserver Express (create/listen/close/static/preload)
│   └── middlewares/
│       ├── error-page.ts               # pages d'erreur HTML branded (404/500), sans Vue ni i18n
│       ├── render.ts                   # middleware de rendu Vue SSR (+ fallbacks 404/500 branded)
│       └── spa-shell-fallback.ts       # renvoie la coquille CSR pour les routes non-SSR
├── src/
│   ├── router/
│   │   ├── ssr-paths.ts                # introspection des routes → ensemble des chemins SSR
│   │   └── meta.ts                     # méta `ssr` + constantes CSR_META / *_CSR_META
│   ├── pages/
│   │   └── SpaShell.vue                # composant vide utilisé pour rendre la coquille CSR
│   └── router/routes/index.ts          # route interne /__spa_shell__
├── quasar.config.js                    # ssr.middlewares = ['spa-shell-fallback', 'render']
└── package.json                        # scripts dev:ssr / build:ssr + deps express/compression
```

## Commandes

```bash
# CSR (comportement d'origine, inchangé)
yarn dev
yarn build

# SSR
yarn dev:ssr        # quasar dev -m ssr
yarn build:ssr      # quasar build -m ssr
```

## Dev Docker

Le dev Docker utilise le SSR par défaut via la variable `QUASAR_DEV_MODE` :

```bash
# .env
QUASAR_DEV_MODE=ssr     # défaut : SSR
# QUASAR_DEV_MODE=csr   # retomber en CSR pur
```

`docker-compose.dev.yml` construit la commande `quasar dev` à partir de cette variable :

- `ssr` → `quasar dev -m ssr`
- `csr` (ou `spa`, ou vide) → `quasar dev` (CSR pur ; Quasar n'a pas de mode `csr`, le défaut sans `-m` est déjà le CSR)
- toute autre valeur → `quasar dev -m <valeur>` (p. ex. `pwa`)

Après avoir changé `.env`, relancez le conteneur : `make up`, `sh compose.sh up -d` ou `docker compose up -d`.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `QUASAR_DEV_MODE` | `ssr` | Mode `quasar dev` en Docker (voir ci-dessus). |
| `SITE_URL` | `http://localhost:3000` | URL publique du site, utilisée pour le lien `canonical` des pages d'erreur branded (404/500). Absente → canonical relatif (`/`). |
| `API_URL` | — | URL de l'API. Doit être définie côté serveur pour que le boot axios ne tente pas d'accéder à `window`/`self` (voir « Points d'attention »). |

## Comment le SSR décide quoi rendre

1. **`spa-shell-fallback`** (déclaré en premier) inspecte le chemin demandé :
   - chemin dans l'ensemble des routes SSR publiques → `next()` → passe au middleware de rendu ;
   - sinon (route auth, route dynamique, chemin inconnu) → renvoie la coquille CSR (rendu de `/__spa_shell__` dont on vide `<div id="q-app">`), et le routeur côté client résout la route (page protégée, catch-all 404, etc.).
2. **`render`** (dernier) effectue le rendu Vue SSR pour les chemins qui lui sont confiés. En cas d'erreur :
   - redirect Vue Router → `res.redirect` ;
   - 404 (aucune catch-all) → page branded 404 ;
   - dev → overlay Quasar avec la stack ;
   - prod → page branded 500 (HTML statique, sans Vue ni i18n, pour rester robuste même si le renderer est en cause).

L'ensemble des chemins SSR est calculé au démarrage par `collectSsrPaths(routes)` dans `src/router/ssr-paths.ts`, qui parcourt l'arbre des `RouteRecordRaw` et exclut :
- les routes dont la `meta` (ou celle d'un parent) vaut `ssr: false`, `requiresAuth: true` ou `auth: true` ;
- les routes à segment dynamique (`:` ou `*`) ;
- les routes portant un `redirect` (qu'elles aient un `component` ou non — p. ex. la racine `/`) ;
- les routes internes (`/__...`).

## Ajouter une page SSR publique

1. Créer la page dans `src/pages/...`.
2. Ajouter la route dans `src/router/routes/*.ts` avec un **chemin statique** et **sans méta d'authentification** (ni `requiresAuth`, ni `auth`).
3. C'est tout : la route apparaît automatiquement dans l'ensemble SSR et sera rendue côté serveur.

Pour forcer une route publique en CSR, lui ajouter `meta: { ssr: false }` (ou réutiliser `CSR_META`).

## Exemples de routes

Avec le routeur par défaut du template :

- **Rendues en SSR** (publiques, statiques) : `/auth/login`, `/auth/register`, `/auth/reset-password`, `/demo`, `/demo/Sandbox`, `/demo/anubis`, `/demo/mastok`, `/error-not-authorized`.
- **Coquille CSR** (auth/dynamiques/inconnues) : `/home` (`requiresAuth`), `/adminspace/...` (`ADMIN_META`), `/userspace` (`auth: true`), `/item/:id` (dynamique), tout chemin inconnu (résolu côté client par la catch-all 404).

> La racine `/` porte un `redirect` vers `home` → exclue du SSR, servie en coquille CSR ; le routeur client applique alors la redirection vers `/home`.

## Tests

- `front/test/unit/router/ssr-paths.spec.ts` — couvre `collectSsrPaths` (inclusions, exclusions, héritage CSR) et `matchesPathSet` (tolérance slash final).
- `front/test/unit/ssr/error-page.spec.ts` — couvre les pages branded : `noindex`, canonical `SITE_URL`, échappement HTML, fallback relatif.
- `front/test/unit/router/routes.spec.ts` — vérifie que la route interne `/__spa_shell__` et la catch-all coexistent avec les routes publiques.

## Points d'attention

- **État partagé / singletons** : en SSR, un module peut être partagé entre plusieurs requêtes. Le singleton axios (`src/boot/axios.ts`) reste sûr tant que `API_URL` est défini dans l'env (la branche qui lit `window`/`self` n'est jamais exécutée côté serveur). Ne stockez pas d'état utilisateur dans des singletons globaux.
- **`window` / `document` / `self`** : indisponibles côté serveur. Gardez tout accès navigateur derrière une garde `if (process.env.CLIENT)` ou `typeof window !== 'undefined'`.
- **i18n** : les messages vue-i18n sont compilés par `@intlify/unplugin-vue-i18n`. Le caractère `@` est réservé aux messages liés (`@:key`) ; pour un `@` littéral dans une traduction, utiliser la syntaxe `{'@'}`.
- **Pages d'erreur** : `src-ssr/middlewares/error-page.ts` produit des pages 404/500 branded en HTML pur (pas de Vue/i18n) pour rester robustes même si le renderer est en cause. Elles incluent `<meta name="robots" content="noindex">` (pas d'indexation) et un `<link rel="canonical">` basé sur `SITE_URL` (ou `/` en fallback). Adaptez le texte et la marque à votre projet ; pour localiser, détectez la locale depuis l'URL ou un cookie et branchez deux variantes.

## Désactiver le SSR

Pour repasser en CSR pur :
1. Mettre `QUASAR_DEV_MODE=csr` dans `.env` (dev Docker).
2. Utiliser `yarn dev` / `yarn build` (CSR) plutôt que `yarn dev:ssr` / `yarn build:ssr`.
3. Optionnellement retirer le bloc `ssr` de `quasar.config.js` et supprimer `src-ssr/`.

Le dossier `src-ssr/` et les scripts `*:ssr` n'impactent pas les commandes CSR : `yarn dev` et `yarn build` continuent de fonctionner à l'identique.
