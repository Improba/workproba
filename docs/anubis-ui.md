# Guide Anubis UI — couleurs et thèmes Workproba

Anubis UI est le framework CSS du front Workproba. Il fournit les variables `--primary`, `--accent`, `--neutral-*`, les classes utilitaires (`bg-primary`, `text-accent`…) et le support clair / sombre via `body.body--light` et `body.body--dark`.

## Architecture des couleurs

Trois couches, une seule source de vérité pour la palette :

```
anubis.config.json          ← éditer les couleurs ici
        │
        ▼  (plugin Vite au démarrage / build)
anubis/_tokens.scss         ← tokens SCSS ($primary-dark, …)
_anubis.scss                ← variables CSS + classes utilitaires générées
        │
        ▼
workproba.scss              ← tokens shell --wp-* et sync Quasar --q-*
        │
        ▼
Composants .vue             ← var(--wp-*) dans le shell, var(--primary) / classes Anubis ailleurs
```

| Fichier | Rôle | Éditable à la main ? |
|---------|------|----------------------|
| `front/anubis.config.json` | Palette complète `{ light, dark }` par token | **Oui** — c'est la source |
| `front/src/css/anubis/_tokens.scss` | Généré depuis la config | Non |
| `front/src/css/_anubis.scss` | Variables CSS + classes détectées dans le code | Non |
| `front/src/css/workproba.scss` | Tokens `--wp-*`, ombres, typo, `--q-*` Quasar | Oui (shell uniquement) |
| `front/lib-improba/css/_colors.scss` | Ancien système Mastok (bleu générique) | **Non utilisé** au build |

Ordre de chargement CSS (`quasar.config.js`) :

```js
css: ['app.scss', '_anubis.scss', 'workproba.scss'],
```

`workproba.scss` est chargé en dernier : il ne redéfinit plus la palette Anubis, seulement les alias sémantiques du shell.

## Palettes Workproba

### Mode clair — « Papier »

| Rôle | Token | Valeur |
|------|-------|--------|
| Branding / sélections | `primary` | `#203d52` (bleu canard) |
| Action / focus / envoi | `accent` | `#2bb5c2` (cyan) |
| Fond application | `neutral-lower` | `#faf8f5` |
| Surface carte | `neutral-lowest` | `#fffcf8` |
| Texte principal | `text` | `#1e2a32` |
| Succès / danger / warning | `success` / `danger` / `warning` | `#2e9e74` / `#d64545` / `#e0a93a` |

### Mode sombre — « Charbon chaud »

| Rôle | Token | Valeur |
|------|-------|--------|
| Accent principal (or) | `primary`, `accent` | `#e0a93a` / `#ffcc49` (high) |
| Fond | `neutral-lowest` | `#161514` |
| Surfaces | `neutral-lower` → `neutral-low` | `#1f1e1c` → `#2a2825` |
| Texte | `text` | `#eceae6` |
| Liens | `text-link` | `#ffcc49` |
| Succès | `success` | `#4ade80` |

Le cyan (`--wp-cyan`) reste disponible comme accent de marque stable (`:root`) mais n'est plus l'accent principal en sombre.

## Modifier une couleur

### 1. Palette Anubis (cas général)

Éditer `front/anubis.config.json`, section `"colors"` :

```json
"primary": { "light": "#203d52", "dark": "#e0a93a" },
"neutral-lowest": { "light": "#ffffff", "dark": "#161514" }
```

Chaque entrée doit avoir `light` et `dark`. Si la section `"colors"` est présente dans `anubis.config.json`, elle **remplace entièrement** la palette par défaut du package `anubis-ui` (pas de merge partiel).

### 2. Régénérer les fichiers Anubis

Au prochain `yarn dev` / `yarn build`, le plugin Anubis régénère `_tokens.scss` et `_anubis.scss`.

Régénération manuelle sans lancer Vite :

```bash
cd front
node -e "require('anubis-ui/dist/tools/main').init()"
```

### 3. Tokens shell Workproba (`--wp-*`)

Pour des besoins spécifiques au chrome (surface-3, bordures fines, violet personas, ombres sombres), éditer `front/src/css/workproba.scss`.

Exemple : le shell mappe les surfaces sur Anubis en sombre :

```scss
body.body--dark {
  --wp-bg: var(--neutral-lowest);
  --wp-surface: var(--neutral-lower);
  --wp-surface-2: var(--neutral-low);
  --wp-surface-3: #35322e;  /* pas d'équivalent exact dans l'échelle neutral */
  --wp-accent: var(--accent);
}
```

Ne pas dupliquer ici toute la palette : préférer `var(--primary)` et consorts.

### 4. Composants Quasar (`q-btn`, `q-toggle`)

Quasar utilise `--q-primary`, etc. Ces variables sont synchronisées dans `workproba.scss` à partir des tokens Anubis :

```scss
body.body--dark {
  --q-primary: var(--primary);
  --q-accent: var(--accent);
  --q-dark-page: var(--neutral-lowest);
}
```

## Bascule clair / sombre

Le toggle appelle `quasar.dark.set(isDark)`, ce qui pose `body.body--light` ou `body.body--dark` sur `<body>`. Anubis expose alors les bonnes valeurs pour chaque variable CSS.

Fichiers concernés :

- `front/lib-improba/composables/use-theme.ts`
- `front/lib-improba/components/layouts/theme-toggler/ThemeToggler.vue`
- `front/src/components/workproba/WorkprobaTitleBar.vue` (toggle dans la titlebar)

Persistance utilisateur : prévue côté API (`preferDarkTheme`), pas encore active ; le défaut vient de `DEFAULT_COLOR_MODE` (`.env`).

## Utilisation dans le code

### Shell Workproba (sidebar, titlebar, chat, fichiers)

Utiliser les tokens `--wp-*` :

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

### Chat, legacy Mastok, classes utilitaires

Variables Anubis ou classes générées :

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

`Lucide` (Mastok) lit `var(--${color})` → `color="primary"` utilise `--primary`.

### À éviter

- Couleurs hex en dur dans les `.vue` du shell (`#161514`, `#e0a93a`)
- Modifier `anubis/_tokens.scss` ou `_anubis.scss` à la main (écrasés au build)
- Compter sur `lib-improba/css/_colors.scss` (non importé)
- Mélanger `text-grey-7` Quasar avec la palette Anubis

## Échelle des variantes

Chaque couleur dispose de 7 niveaux :

| Suffixe | Usage typique |
|---------|---------------|
| `-lowest` | Fond le plus profond (sombre) ou le plus clair (clair) |
| `-lower` | Surface secondaire |
| `-low` | Bordures légères, hover |
| *(base)* / `-medium` | Couleur principale |
| `-high` | Accent fort, focus ring |
| `-higher` | Texte secondaire |
| `-highest` | Texte principal contrasté |

En sombre charbon, `neutral-lowest` = fond `#161514`, `neutral-highest` = texte `#eceae6`.

## Configuration Anubis (hors couleurs)

`front/anubis.config.json` définit aussi :

- **`files.targets`** : fichiers scannés pour détecter les classes (`**/*.vue`, `**/*use-mastok.ts`)
- **`utilities`** : préfixes générés (`bg`, `text`, `border`, `shadow`, `rounded`, `size`, `weight`…)

Les classes doivent être **écrites explicitement** dans le code (pas de `` `bg-${color}` `` dynamique). Utiliser `force` dans la config si une classe doit exister sans être détectée.

## Fichiers générés par Anubis

| Fichier | Contenu |
|---------|---------|
| `src/css/_anubis.scss` | `@include setRootColors(...)` + classes utilitaires |
| `src/css/anubis/_mixins.scss` | Mixin `setRootColors` |
| `src/css/anubis/_tokens.scss` | `$primary`, `$primary-dark`, … |
| `src/css/anubis/_overrides.scss` | Overrides Quasar SCSS depuis utilitaires (souvent vide) |

## Références

- [design.md](./design.md) — tokens `--wp-*`, typo, densité, focus
- [design/design-system.md](./design/design-system.md) — maquettes chrome et parcours UX
- Page démo in-app : route `demo-anubis`
- Package : `anubis-ui@^1.4.4` — README dans `node_modules/anubis-ui`

## Résumé

| Besoin | Où agir |
|--------|---------|
| Changer primary, accent, neutrals, sémantique | `anubis.config.json` → régénérer |
| Surface shell, bordure fine, ombre sombre | `workproba.scss` (`--wp-*`) |
| Boutons Quasar | `workproba.scss` (`--q-*`) ou tokens Anubis |
| Classe utilitaire nouvelle | L'écrire dans un `.vue`, rebuild Anubis |
| CSS custom composant shell | `var(--wp-*)` |
| CSS custom chat / Mastok | `var(--primary)` ou classes `bg-*` / `text-*` |
