# Anubis UI Guide, Workproba Colors and Themes

Anubis UI is the CSS framework for the Workproba frontend. It provides the `--primary`, `--accent`, `--neutral-*` variables, utility classes (`bg-primary`, `text-accent`…), and light / dark support via `body.body--light` and `body.body--dark`.

## Color architecture

Three layers, one source of truth for the palette:

```
anubis.config.json          ← edit colors here
        │
        ▼  (Vite plugin at startup / build)
anubis/_tokens.scss         ← SCSS tokens ($primary-dark, …)
_anubis.scss                ← CSS variables + generated utility classes
        │
        ▼
workproba.scss              ← shell tokens --wp-* and Quasar --q-* sync
        │
        ▼
.vue components             ← var(--wp-*) in the shell, var(--primary) / Anubis classes elsewhere
```

| File | Role | Editable manually? |
|---------|------|----------------------|
| `front/anubis.config.json` | Full palette `{ light, dark }` per token | **Yes**, this is the source |
| `front/src/css/anubis/_tokens.scss` | Generated from config | No |
| `front/src/css/_anubis.scss` | CSS variables + classes detected in code | No |
| `front/src/css/workproba.scss` | `--wp-*` tokens, shadows, typography, Quasar `--q-*` | Yes (shell only) |
| `front/lib-improba/css/_colors.scss` | Legacy Mastok system (generic blue) | **Not used** at build |

CSS load order (`quasar.config.js`):

```js
css: ['app.scss', '_anubis.scss', 'workproba.scss'],
```

`workproba.scss` is loaded last: it no longer redefines the Anubis palette, only the shell's semantic aliases.

## Workproba palettes

### Light mode, "Paper"

| Role | Token | Value |
|------|-------|--------|
| Branding / selections | `primary` | `#203d52` (teal blue) |
| Action / focus / send | `accent` | `#2bb5c2` (cyan) |
| Application background | `neutral-lower` | `#faf8f5` |
| Card surface | `neutral-lowest` | `#fffcf8` |
| Main text | `text` | `#1e2a32` |
| Success / danger / warning | `success` / `danger` / `warning` | `#2e9e74` / `#d64545` / `#e0a93a` |

### Dark mode, "Warm Charcoal"

| Role | Token | Value |
|------|-------|--------|
| Main accent (gold) | `primary`, `accent` | `#e0a93a` / `#ffcc49` (high) |
| Background | `neutral-lowest` | `#161514` |
| Surfaces | `neutral-lower` → `neutral-low` | `#1f1e1c` → `#2a2825` |
| Text | `text` | `#eceae6` |
| Links | `text-link` | `#ffcc49` |
| Success | `success` | `#4ade80` |

Cyan (`--wp-cyan`) remains available as a stable brand accent (`:root`) but is no longer the main accent in dark mode.

## Changing a color

### 1. Anubis palette (general case)

Edit `front/anubis.config.json`, `"colors"` section:

```json
"primary": { "light": "#203d52", "dark": "#e0a93a" },
"neutral-lowest": { "light": "#ffffff", "dark": "#161514" }
```

Each entry must have `light` and `dark`. If the `"colors"` section is present in `anubis.config.json`, it **fully replaces** the default palette from the `anubis-ui` package (no partial merge).

### 2. Regenerate Anubis files

On the next `yarn dev` / `yarn build`, the Anubis plugin regenerates `_tokens.scss` and `_anubis.scss`.

Manual regeneration without starting Vite:

```bash
cd front
node -e "require('anubis-ui/dist/tools/main').init()"
```

### 3. Workproba shell tokens (`--wp-*`)

For chrome-specific needs (surface-3, fine borders, persona violet, dark shadows), edit `front/src/css/workproba.scss`.

Example: the shell maps surfaces to Anubis in dark mode:

```scss
body.body--dark {
  --wp-bg: var(--neutral-lowest);
  --wp-surface: var(--neutral-lower);
  --wp-surface-2: var(--neutral-low);
  --wp-surface-3: #35322e;  /* no exact equivalent in the neutral scale */
  --wp-accent: var(--accent);
}
```

Do not duplicate the entire palette here: prefer `var(--primary)` and similar.

### 4. Quasar components (`q-btn`, `q-toggle`)

Quasar uses `--q-primary`, etc. These variables are synchronized in `workproba.scss` from Anubis tokens:

```scss
body.body--dark {
  --q-primary: var(--primary);
  --q-accent: var(--accent);
  --q-dark-page: var(--neutral-lowest);
}
```

## Light / dark toggle

The toggle calls `quasar.dark.set(isDark)`, which sets `body.body--light` or `body.body--dark` on `<body>`. Anubis then exposes the correct values for each CSS variable.

Relevant files:

- `front/src/utils/uiTheme.ts` (registry, `applyUiTheme`, cache localStorage)
- `front/src/composables/useUiTheme.ts` (watch réactif + toggle persisté)
- `front/lib-improba/components/layouts/theme-toggler/ThemeToggler.vue`
- `front/src/components/workproba/WorkprobaTitleBar.vue` (toggle in the titlebar)

User persistence: Tauri `AppSettings.uiTheme` (`paper` | `charcoal`), miroir `localStorage` (`workproba:uiTheme`) pour le boot sans flash. Chargement au boot via `useImprobaInit` avant le montage du layout. Fallback sans settings : `DEFAULT_COLOR_MODE` (`.env`).

## Usage in code

### Workproba shell (sidebar, titlebar, chat, files)

Use `--wp-*` tokens:

```scss
.wp-panel {
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  color: var(--wp-text);
}

.wp-tab--active {
  color: var(--wp-accent);
  border-bottom-color: var(--wp-accent);
}
```

### Chat, legacy Mastok, utility classes

Anubis variables or generated classes:

```vue
<template>
  <div class="bg-neutral-high text-neutral-lowest">Toast</div>
  <Lucide name="rotate-ccw" color="primary" />
</template>
```

```scss
.bubble-user {
  background: var(--primary);
}
```

`Lucide` (Mastok) reads `var(--${color})` → `color="primary"` uses `--primary`.

### Avoid

- Hardcoded hex colors in shell `.vue` files (`#161514`, `#e0a93a`)
- Editing `anubis/_tokens.scss` or `_anubis.scss` manually (overwritten at build)
- Relying on `lib-improba/css/_colors.scss` (not imported)
- Mixing Quasar `text-grey-7` with the Anubis palette

## Variant scale

Each color has 7 levels:

| Suffix | Typical usage |
|---------|---------------|
| `-lowest` | Deepest background (dark) or lightest (light) |
| `-lower` | Secondary surface |
| `-low` | Light borders, hover |
| *(base)* / `-medium` | Main color |
| `-high` | Strong accent, focus ring |
| `-higher` | Secondary text |
| `-highest` | High-contrast main text |

In warm charcoal dark mode, `neutral-lowest` = background `#161514`, `neutral-highest` = text `#eceae6`.

## Anubis configuration (beyond colors)

`front/anubis.config.json` also defines:

- **`files.targets`**: files scanned to detect classes (`**/*.vue`, `**/*use-mastok.ts`)
- **`utilities`**: generated prefixes (`bg`, `text`, `border`, `shadow`, `rounded`, `size`, `weight`…)

Classes must be **written explicitly** in code (no dynamic `` `bg-${color}` ``). Use `force` in the config if a class must exist without being detected.

## Files generated by Anubis

| File | Content |
|---------|---------|
| `src/css/_anubis.scss` | `@include setRootColors(...)` + utility classes |
| `src/css/anubis/_mixins.scss` | `setRootColors` mixin |
| `src/css/anubis/_tokens.scss` | `$primary`, `$primary-dark`, … |
| `src/css/anubis/_overrides.scss` | Quasar SCSS overrides from utilities (often empty) |

## References

- [design.md](./design.md), `--wp-*` tokens, typography, density, focus, UI shell
- In-app demo page: `demo-anubis` route
- Package: `anubis-ui@^1.4.4`, README in `node_modules/anubis-ui`

## Summary

| Need | Where to act |
|--------|---------|
| Change primary, accent, neutrals, semantic | `anubis.config.json` → regenerate |
| Shell surface, fine border, dark shadow | `workproba.scss` (`--wp-*`) |
| Quasar buttons | `workproba.scss` (`--q-*`) or Anubis tokens |
| New utility class | Write it in a `.vue`, rebuild Anubis |
| Custom shell component CSS | `var(--wp-*)` |
| Custom chat / Mastok CSS | `var(--primary)` or `bg-*` / `text-*` classes |
