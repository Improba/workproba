# SSR (Server-Side Rendering)

This document describes the SSR setup for the Improba template monorepo's Quasar frontend.
SSR is optional but enabled by default in Docker dev. CSR (client-side rendering) remains available and works as before.

## Principles

- **Static public routes** (showcase pages, demos, error pages) are rendered server-side: fast first HTML render, correct SEO and open-graph, then client hydration.
- **Authenticated routes** (`requiresAuth: true` or `auth: true`), **dynamic routes**, and **unknown paths** are NOT rendered server-side: the server returns a CSR shell (SPA shell) and the browser takes over. This avoids exposing protected pages and polluting server state with tokens.
- A route can explicitly opt out of SSR with `meta.ssr = false` (see `src/router/meta.ts`, constants `CSR_META`, `AUTHENTICATED_CSR_META`, `ADMIN_CSR_META`).

## Files in place

```
front/
├── src-ssr/
│   ├── server.ts                       # Express webserver (create/listen/close/static/preload)
│   └── middlewares/
│       ├── error-page.ts               # branded HTML error pages (404/500), no Vue or i18n
│       ├── render.ts                   # Vue SSR render middleware (+ branded 404/500 fallbacks)
│       └── spa-shell-fallback.ts       # returns CSR shell for non-SSR routes
├── src/
│   ├── router/
│   │   ├── ssr-paths.ts                # route introspection → SSR path set
│   │   └── meta.ts                     # `ssr` meta + CSR_META / *_CSR_META constants
│   ├── pages/
│   │   └── SpaShell.vue                # empty component used to render CSR shell
│   └── router/routes/index.ts          # internal route /__spa_shell__
├── quasar.config.js                    # ssr.middlewares = ['spa-shell-fallback', 'render']
└── package.json                        # dev:ssr / build:ssr scripts + express/compression deps
```

## Commands

```bash
# CSR (original behavior, unchanged)
yarn dev
yarn build

# SSR
yarn dev:ssr        # quasar dev -m ssr
yarn build:ssr      # quasar build -m ssr
```

## Docker dev

Docker dev uses SSR by default via the `QUASAR_DEV_MODE` variable:

```bash
# .env
QUASAR_DEV_MODE=ssr     # default: SSR
# QUASAR_DEV_MODE=csr   # fall back to pure CSR
```

`docker-compose.dev.yml` builds the `quasar dev` command from this variable:

- `ssr` → `quasar dev -m ssr`
- `csr` (or `spa`, or empty) → `quasar dev` (pure CSR; Quasar has no `csr` mode, default without `-m` is already CSR)
- any other value → `quasar dev -m <value>` (e.g. `pwa`)

After changing `.env`, restart the container: `make up`, `sh compose.sh up -d` or `docker compose up -d`.

## Environment variables

| Variable | Default | Role |
|---|---|---|
| `QUASAR_DEV_MODE` | `ssr` | `quasar dev` mode in Docker (see above). |
| `SITE_URL` | `http://localhost:3000` | Public site URL, used for branded error page (404/500) `canonical` link. If absent → relative canonical (`/`). |
| `API_URL` | (none) | API URL. Must be defined server-side so axios boot does not try to access `window`/`self` (see "Points of attention"). |

## How SSR decides what to render

1. **`spa-shell-fallback`** (declared first) inspects the requested path:
   - path in the public SSR route set → `next()` → passes to render middleware;
   - otherwise (auth route, dynamic route, unknown path) → returns CSR shell (renders `/__spa_shell__` with emptied `<div id="q-app">`), and the client router resolves the route (protected page, catch-all 404, etc.).
2. **`render`** (last) performs Vue SSR rendering for paths handed to it. On error:
   - Vue Router redirect → `res.redirect`;
   - 404 (no catch-all) → branded 404 page;
   - dev → Quasar overlay with stack;
   - prod → branded 500 page (static HTML, no Vue or i18n, to stay robust even if the renderer is at fault).

The SSR path set is computed at startup by `collectSsrPaths(routes)` in `src/router/ssr-paths.ts`, which walks the `RouteRecordRaw` tree and excludes:
- routes whose `meta` (or a parent's) is `ssr: false`, `requiresAuth: true` or `auth: true`;
- routes with a dynamic segment (`:` or `*`);
- routes with a `redirect` (whether they have a `component` or not, e.g. root `/`);
- internal routes (`/__...`).

## Adding a public SSR page

1. Create the page in `src/pages/...`.
2. Add the route in `src/router/routes/*.ts` with a **static path** and **no authentication meta** (neither `requiresAuth` nor `auth`).
3. That's it: the route automatically appears in the SSR set and will be rendered server-side.

To force a public route to CSR, add `meta: { ssr: false }` (or reuse `CSR_META`).

## Route examples

With the template's default router:

- **Rendered in SSR** (public, static): `/auth/login`, `/auth/register`, `/auth/reset-password`, `/demo`, `/demo/Sandbox`, `/demo/anubis`, `/demo/mastok`, `/error-not-authorized`.
- **CSR shell** (auth/dynamic/unknown): `/home` (`requiresAuth`), `/adminspace/...` (`ADMIN_META`), `/userspace` (`auth: true`), `/item/:id` (dynamic), any unknown path (resolved client-side by catch-all 404).

> Root `/` has a `redirect` to `home` → excluded from SSR, served as CSR shell; the client router then applies the redirect to `/home`.

## Tests

- `front/test/unit/router/ssr-paths.spec.ts`, covers `collectSsrPaths` (inclusions, exclusions, CSR inheritance) and `matchesPathSet` (trailing slash tolerance).
- `front/test/unit/ssr/error-page.spec.ts`, covers branded pages: `noindex`, `SITE_URL` canonical, HTML escaping, relative fallback.
- `front/test/unit/router/routes.spec.ts`, verifies that internal route `/__spa_shell__` and catch-all coexist with public routes.

## Points of attention

- **Shared state / singletons**: in SSR, a module can be shared between multiple requests. The axios singleton (`src/boot/axios.ts`) stays safe as long as `API_URL` is defined in env (the branch that reads `window`/`self` is never executed server-side). Do not store user state in global singletons.
- **`window` / `document` / `self`**: unavailable server-side. Keep all browser access behind an `if (process.env.CLIENT)` or `typeof window !== 'undefined'` guard.
- **i18n**: vue-i18n messages are compiled by `@intlify/unplugin-vue-i18n`. The `@` character is reserved for linked messages (`@:key`); for a literal `@` in a translation, use the `{'@'}` syntax.
- **Error pages**: `src-ssr/middlewares/error-page.ts` produces branded 404/500 pages in pure HTML (no Vue/i18n) to stay robust even if the renderer is at fault. They include `<meta name="robots" content="noindex">` (no indexing) and a `<link rel="canonical">` based on `SITE_URL` (or `/` as fallback). Adapt text and branding to your project; to localize, detect locale from URL or cookie and wire two variants.

## Disabling SSR

To switch back to pure CSR:
1. Set `QUASAR_DEV_MODE=csr` in `.env` (Docker dev).
2. Use `yarn dev` / `yarn build` (CSR) rather than `yarn dev:ssr` / `yarn build:ssr`.
3. Optionally remove the `ssr` block from `quasar.config.js` and delete `src-ssr/`.

The `src-ssr/` folder and `*:ssr` scripts do not impact CSR commands: `yarn dev` and `yarn build` continue to work identically.
