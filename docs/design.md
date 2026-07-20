# Design System

This document describes the design system used in Workproba: the **Anubis UI** palette, the **`--wp-*`** shell tokens, and the **desktop UI shell** as implemented today. **This file and the code are the source of truth.**

## Overview

The project uses **Anubis UI** (`anubis-ui@^1.4.4`), a custom CSS framework that provides:

- A consistent color system with light/dark mode support
- Automatically generated utility classes
- CSS variables for flexible usage
- Seamless integration with Quasar Framework

Workproba adds a dedicated **`--wp-*`** token system on top (defined in `front/src/css/workproba.scss`) for all custom application CSS: typography, focus, spacing, density, surfaces, chat-specific colors, and brand accents.

Icons in the shell use **Lucide** via `Lucide.vue` (Mastok wrapper), with colors mapped to Anubis / `--wp-*` tokens.

## UI shell (desktop layout)

The main layout is `front/src/layouts/WorkprobaLayout.vue`. Root element: `.wp-shell` with `data-density` driven by `useAppSettings.density` (`compact` | `comfortable` | `spacious`).

```
+--------------------------------------------------------------------------------+
| WorkprobaTitleBar (~40px)                                                      |
| [Workproba · workspace · user]     [sidecar] [side chat] [files] [sidebar] …   |
+----------+-------------------------------------------+------------+----------+
| Sidebar  |              Center (router-view)         | RightPanel | SideChat |
| 268px    |  Home · Chat · Settings …                 |  320px     | 380px    |
| rail 56  |  Chat max ~46rem, composer ~34rem        |  tabbed    | optional |
+----------+-------------------------------------------+------------+----------+
```

### Regions

| Region | Component | Role |
|--------|-----------|------|
| **Title bar** | `WorkprobaTitleBar.vue` | Tauri drag region; `WorkprobaBrand` (mark + logo), workspace name, user profile; sidecar status chip (opens settings dialog); toggles for side chat, right panel, sidebar; keyboard shortcuts (`?`); theme toggle |
| **Left sidebar** | `WorkspaceSidebar.vue` | **Tree model**: recent workspaces as expandable nodes, conversations nested under each workspace. Footer: settings, memory, profile. Collapsible to **56px icon rail** (never fully hidden) |
| **Center** | `<router-view />` in `.wp-center` | Home (`EngineOnboardingWizard` on first run), chat (`ChatView`), settings pages. Chat body uses `--wp-font-chat` |
| **Right panel** | `RightPanel.vue` | Collapsible (`Ctrl/Cmd+B`), state per session. **Tabs**: Files (`FileExplorer`), Preview (`DocumentPreview`), Personas (if plugin active), dynamic plugin tabs |
| **Side chat** | `SideChatPanel.vue` | Optional panel (`Ctrl/Cmd+Shift+L`) for plugin side conversations (e.g. Personas). Width 320–420px (default 380px) |

### Responsive breakpoints

Handled in `WorkprobaLayout.vue`:

| Viewport | Behavior |
|----------|----------|
| `< 820px` | Sidebar switches to 56px rail; right panel closed |
| `< 1100px` | Right panel auto-collapsed; opening side chat also closes files panel |

### Keyboard shortcuts (shell)

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd+B` | Toggle right panel (files / preview / …) |
| `Ctrl/Cmd+\` | Toggle sidebar rail |
| `Ctrl/Cmd+Shift+L` | Toggle side chat (if a plugin provides one) |
| `Ctrl/Cmd+R` / `F5` | Reload webview |
| `?` | Toggle keyboard shortcuts help |

See also [architecture.md](./architecture.md) for data flow and plugin integration.

## Brand assets

`WorkprobaBrand.vue` renders the product mark and logo from `front/src/assets/brand/` (SVG mark plus light/dark logo variants). It replaces the former Quasar logo in the title bar and onboarding surfaces. Use the component rather than inlining SVG paths in feature code.

## Workproba Tokens (`--wp-*`)

### Role in the architecture

| Layer | Usage |
|--------|-------|
| **`--wp-*`** | Semantic aliases for the Workproba **shell** (surfaces, borders, typography, focus, chat), defined in `workproba.scss`, often mapped to Anubis (`var(--neutral-lower)`, etc.) |
| **Anubis** (`--primary`, `--neutral-*`, `bg-*` / `text-*` classes) | **Palette source of truth** via `anubis.config.json` → `_anubis.scss` |
| **Quasar** | Structural components; colors via `--q-*` synchronized in `workproba.scss` |

**Contribution rule**: all custom styling in a Workproba component goes through `--wp-*` tokens. No hardcoded colors or sizes (`#203d52`, `14px`, etc.) in component `.vue` / `.scss` files.

### Typography

Webfonts are embedded offline (Tauri) via `@fontsource` in `workproba.scss`: Varela Round, Inter (400–700), JetBrains Mono.

| Token | Value | Role |
|-------|--------|------|
| `--wp-fs-xs` | 12px | Tertiary text, compact labels |
| `--wp-fs-sm` | 13px | Secondary text, hints |
| `--wp-fs-base` | 15px | Default body text |
| `--wp-fs-md` | 17px | Subtitles, section titles |
| `--wp-fs-lg` | 20px | Intermediate titles |
| `--wp-fs-xl` | 24px | Page titles |
| `--wp-fs-display` | 32px | Hero display (onboarding) |
| `--wp-lh-tight` | 1.2 | Titles, labels |
| `--wp-lh-normal` | 1.5 | Body text |
| `--wp-lh-relaxed` | 1.65 | Spacious paragraphs |
| `--wp-font-ui` | Varela Round, … | General UI chrome (sidebar, buttons, labels) |
| `--wp-font-head` | Inter, … | Headings (`h1`–`h6`, `.wp-head`) |
| `--wp-font-chat` | Inter, … | Chat center zone (`.wp-center`) |
| `--wp-font-mono` | JetBrains Mono, … | Code, keyboard shortcuts |

### Keyboard focus

| Token | Role |
|-------|------|
| `--wp-focus-ring` | `:focus-visible` ring; per theme: `var(--accent-high)` (gold in both themes) |
| `--wp-focus-offset` | Outline offset (2px) |

Applied globally on `.wp-shell` for titlebar, sidebar, explorer, composer, and buttons via the `wp-focus-visible` mixin.

### Spacing and density

The `--wp-space-1` through `--wp-space-6` tokens define the spacing scale. Their values depend on the `data-density` attribute on the root layout (`.wp-shell`), driven by `useAppSettings.density`:

| Density | `--wp-space-1` … `--wp-space-6` | Usage |
|---------|----------------------------------|-------|
| `compact` | 2, 4, 8, 12, 16, 20 px | Power users, dense screens |
| `comfortable` (default) | 4, 8, 12, 16, 20, 24 px | Guided / locked flow |
| `spacious` | 6, 10, 14, 20, 28, 32 px | Maximum readability |

### Surfaces, borders, and accents

Light and dark modes share the same **warm accent family** (gold). Light mode uses a **warm neutral** palette (cream surfaces, visible warm borders). Dark mode uses warm charcoal with the same gold accent logic.

| Token | Role |
|-------|------|
| `--wp-bg` | Global application background (light: `neutral-low` for clearer separation from cards) |
| `--wp-surface`, `--wp-surface-2`, `--wp-surface-3` | Cards, panels, elevated areas |
| `--wp-border`, `--wp-border-strong` | Separators and outlines (light: `neutral-medium` for readable edges) |
| `--wp-text`, `--wp-text-muted`, `--wp-text-faint` | Text hierarchy |
| `--text-muted`, `--text-faint` | Aliases for Lucide `color` prop |
| `--wp-primary`, `--wp-primary-soft` | Structure: canard (light) / soft blue (dark), via `var(--primary)` |
| `--wp-accent`, `--wp-accent-strong`, `--wp-accent-soft` | **Single interactive accent**: gold in both themes (`#d4a017` light / `#e0a93a` dark) |
| `--wp-canard`, `--wp-cyan`, `--wp-gold`, `--wp-violet` | Stable brand accents (see color roles below) |
| `--wp-gold-soft`, `--wp-violet-soft` | Soft backgrounds for Regards métier and memory badges |
| `--wp-warning`, `--wp-warning-soft` | Semantic warning aliases (mapped to Anubis `warning`) |
| `--wp-selection`, `--wp-selection-soft` | Text selection in chat |
| `--wp-user-bubble-bg`, `--wp-user-bubble-text`, `--wp-user-bubble-border` | User message bubbles in chat |
| `--wp-success`, `--wp-success-soft`, `--wp-danger`, `--wp-danger-soft` | Semantic states |
| `--wp-r-sm` … `--wp-r-pill` | Border radii |
| `--wp-shadow-1`, `--wp-shadow-2` | Light shadows (theme-specific values) |
| `--wp-ease`, `--wp-dur` | Transitions (180ms) |

### Color roles (semantic discipline)

One accent for all interactive UI. Secondary colors carry **business meaning** only.

| Token | Light value (stable or mapped) | Role | Usage |
|-------|-------------------------------|------|--------|
| `--wp-accent` | `#d4a017` (via Anubis `accent`) | **Action** | Send, primary CTA, focus ring, active tabs, sidebar hovers, composer chip Regards |
| `--wp-primary` | `#203d52` (canard) | **Structure** | Workspace selection, user bubble text, titles, selection states |
| `--wp-cyan` | `#2bb5c2` (stable in `:root`) | **Info / secondary** | Links techniques, badges info, `--q-info`; former main accent in light mode |
| `--wp-gold` | `#e0a93a` (via Anubis `warning`) | **Regards / Personas** | Personas avatars, meeting views, opinion cards; slightly brighter than accent |
| `--wp-violet` | theme-adjusted | **Memory / RAG** | Avatars mémoire, citations, raisonnement marqué |
| `--wp-success` / `--wp-danger` / `--wp-warning` | Anubis semantic | **Feedback** | Confirmations, errors, alerts |

**Rule**: shell components use `--wp-accent` for any hover, focus, or CTA. Reserve `--wp-gold` for the Regards / Personas feature family. Do not mix `--wp-gold` on generic chrome hovers (sidebar icons, titlebar toggles).

**Why light = gold now**: light mode previously used cyan accent + gold hovers + canard structure on warm cream backgrounds, which felt disjoint compared to dark mode (already gold-accented). Unifying on gold aligns both themes; cyan is demoted to informational use.

### Animation utilities

Defined in `workproba.scss`:

| Class | Effect |
|-------|--------|
| `.wp-breathe` | Opacity pulse (1.6s) for "working" / streaming indicators |
| `.wp-fade-in` | Fade + translateY 4px (220ms) for message appearance |
| `.wp-sr-only` | Visually hidden, screen-reader accessible |

### Source files

- **Palette** (`--primary`, `--neutral-*`, semantic): `front/anubis.config.json` → generates `_anubis.scss`. See [anubis-ui.md](./anubis-ui.md).
- **Shell** (`--wp-*`, typography, density, `--q-*`): `front/src/css/workproba.scss`, loaded **after** `_anubis.scss`.

## Anubis UI

### What is Anubis UI?

Anubis UI is a CSS library that automatically generates utility classes and CSS variables from a JSON configuration. It allows you to:

1. **Define a color system** with variants for light and dark mode
2. **Generate utility classes** (bg, text, border, shadow, etc.) only for classes used in the code
3. **Create CSS variables** accessible in SCSS/CSS styles
4. **Support light/dark mode** automatically via CSS variables

### Integration in the project

Anubis UI is integrated via:

- **npm package**: `anubis-ui@^1.4.4` (declared in `front/package.json`)
- **Vite plugin**: Configured in `front/quasar.config.js` via `anubis.plugin`
- **Color configuration**: `front/anubis.config.json` (`"colors"` section), **source of truth**
- **Generated styles**: `front/src/css/_anubis.scss`, `front/src/css/anubis/_tokens.scss` (do not edit manually)
- **Shell tokens**: `front/src/css/workproba.scss` (`--wp-*`, `--q-*` only)

### How it works

1. **Code scan**: Anubis scans `.vue` files and `*use-mastok.ts` to detect used classes
2. **Generation**: Only detected classes are generated in `_anubis.scss`
3. **CSS variables**: Colors are exposed as CSS variables (`--primary`, `--neutral-lower`, etc.)
4. **Light/dark mode**: Variables change automatically based on the `body--light` or `body--dark` class

## Color system

### Color palette

The system defines several palettes with their variants:

| Color | Usage | Example |
|---------|-------|---------|
| **Primary** | Main application color | Primary actions, important links |
| **Secondary** | Secondary color | Secondary elements, borders |
| **Neutral** | Neutral colors | Backgrounds, text, separators |
| **Success** | Successful actions | Success messages, validations |
| **Danger** | Errors and destructive actions | Error messages, delete buttons |
| **Warning** | Warnings | Warning messages, alerts |
| **Accent** | Visual accents | Highlighted elements, focus, streaming |
| **Text** | Text colors | Main text, inverted text, links |

### Color variants

Each color has 7 variants to create visual hierarchy:

| Suffix | Description | Typical usage |
|---------|-------------|---------------|
| `-lowest` | Lightest | Very light backgrounds |
| `-lower` | Very light | Light backgrounds, secondary areas |
| `-low` | Light | Subtle borders, light hover states |
| *(no suffix)* | Base color | Main color |
| `-medium` | Same as base | Alias for the main color |
| `-high` | Dark | Text on light backgrounds, important elements |
| `-higher` | Very dark | High-contrast text |
| `-highest` | Darkest | Text on light backgrounds, maximum contrast |

### Light/dark mode support

Colors adapt automatically to the theme:

- **Light mode** (`body.body--light`): Uses values defined for `light`
- **Dark mode** (`body.body--dark`): Uses values defined for `dark`

Variants are intelligently inverted: for example, `neutral-lowest` is white in light mode and very dark in dark mode, always ensuring good contrast.

### Color examples (Workproba)

Values defined in `front/anubis.config.json`:

```text
// Light: warm cream + gold accent + canard structure
primary:        #203d52
accent:         #d4a017
accent-high:    #bb8e02
text:           #1e2a32
text-link:      #bb8e02
neutral-low:    #f3f0ea   ← --wp-bg (shell)
neutral-lowest: #fffcf8   ← --wp-surface (cards)
neutral-medium: #cfc8bc   ← --wp-border (shell)
warning:        #e0a93a   ← --wp-gold (Regards / Personas)

// Dark: warm charcoal + gold accent
primary:        #6b9eb5
accent:         #e0a93a
accent-high:    #ffcc49
neutral-lowest: #161514
neutral-lower:  #1f1e1c
text:           #eceae6
text-link:      #ffcc49
success:        #4ade80

// Stable across themes (:root in workproba.scss)
wp-canard:      #203d52
wp-cyan:        #2bb5c2   ← info / secondary (not main accent)
```

Full list and modification procedure: [anubis-ui.md](./anubis-ui.md).

## Usage

### In Vue templates

**✅ DO**: Use Anubis classes

```vue
<template>
  <div class="bg-neutral-lower text-neutral-highest">
    <q-btn class="bg-primary text-white">Primary action</q-btn>
    <p class="text-warning">Warning message</p>
    <div class="bg-success-lower border-success text-success-high">
      Operation successful
    </div>
  </div>
</template>
```

**✅ DO**: Use `--wp-*` tokens in scoped SCSS for Workproba components

```scss
.my-panel {
  background: var(--wp-surface);
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  padding: var(--wp-space-3);
  font-family: var(--wp-font-ui);
}
```

**❌ AVOID**: Using default Quasar colors

```vue
<template>
  <!-- Do not use -->
  <q-btn color="primary">Action</q-btn>
  <p class="text-grey-7">Text</p>
  <div class="bg-grey-1">Content</div>
</template>
```

### Lucide icons

Use the Mastok wrapper with Anubis or `--wp-*` color names:

```vue
<Lucide name="folder" size="16" color="wp-text-muted" />
<Lucide name="message-square-plus" size="sm" color="wp-accent" />
<Lucide name="users" size="15" color="wp-gold" />  <!-- Regards / Personas only -->
```

Supported aliases: `text-muted`, `text-faint`, `text` → mapped to `--wp-*` in `Lucide.vue`.

### In SCSS/CSS styles

**✅ DO**: Use Anubis CSS variables or `--wp-*` tokens

```scss
.my-component {
  color: var(--primary);
  background-color: var(--wp-surface);
  border-color: var(--wp-border);
  
  &:hover {
    background-color: var(--primary-lower);
  }
}
```

**❌ AVOID**: Using Quasar variables or hexadecimal values

```scss
.my-component {
  // Do not use
  color: var(--q-primary);
  background-color: var(--q-grey-2);
  color: #0f84cb; // Hardcoded hexadecimal value
}
```

### Available utility classes

#### Background colors (`bg-*`)

```vue
<div class="bg-primary">Primary background</div>
<div class="bg-primary-lower">Light primary background</div>
<div class="bg-neutral-lowest">Very light neutral background</div>
<div class="bg-success">Success background</div>
<div class="bg-danger-lower">Light danger background</div>
```

#### Text colors (`text-*`)

```vue
<p class="text-primary">Primary text</p>
<p class="text-neutral-highest">Dark neutral text</p>
<p class="text-success">Success text</p>
<p class="text-danger-high">Dark danger text</p>
<p class="text-text-link">Link</p>
```

#### Borders (`border-*`)

```vue
<div class="border-primary">Primary border (1px)</div>
<div class="border-neutral-xs">Thin neutral border (1px)</div>
<div class="border-warning-sm">Warning border (2px)</div>
<div class="border-success-md">Success border (3px)</div>
```

Available variations: `xs` (1px), `sm` (2px), `md` (3px), `lg` (6px), `xl` (8px), `xxl` (10px)

#### Shadows (`shadow-*`)

```vue
<div class="shadow-primary">Primary shadow</div>
<div class="shadow-neutral-xs">Small neutral shadow</div>
<div class="shadow-warning-lg">Large warning shadow</div>
```

Available variations: `xs`, `sm`, `md`, `lg`, `xl`

#### Other utilities

- **Inner borders**: `inner-border-{color}-{size}`
- **Blur**: `blur` (backdrop-filter)
- **Transitions**: `smooth`, `smooth-slow`, `smooth-quick`, etc.
- **Rounded borders**: `rounded`, `rounded-md`, `rounded-lg`, `rounded-full`, etc.
- **Text sizes**: `size-xs`, `size-sm`, `size-md`, `size-lg`, etc.
- **Font weights**: `weight-light`, `weight-normal`, `weight-bold`, etc.

## Configuration

### `anubis.config.json` file

This file defines:

1. **Files to scan**: `**/*.vue` and `**/*use-mastok.ts`
2. **Utilities to generate**: bg, text, border, shadow, blur, smooth, rounded, etc.
3. **Available colors**: All colors with their light/dark variants
4. **Variations**: Sizes, thicknesses, etc. for each utility

### Customizing colors

1. Edit **`front/anubis.config.json`** → `"colors"` section (each token: `{ "light": "…", "dark": "…" }`).
2. Restart the dev server, or run `node -e "require('anubis-ui/dist/tools/main').init()"` in `front/`.
3. For shell-only changes (surfaces, shadows, Quasar `--q-*`): update `front/src/css/workproba.scss`.

The `front/lib-improba/css/_colors.scss` file is legacy Mastok **not imported** at build time; do not use it for Workproba.

Detailed guide: [anubis-ui.md](./anubis-ui.md).

### Class generation

Classes are generated automatically during the build:

- Anubis scans the source code
- Detects used classes (e.g. `bg-primary`, `text-neutral-highest`)
- Generates only detected classes in `front/src/css/_anubis.scss`

**Note**: If you add a new class in your code, it will be automatically generated on the next build.

## Integration with Mastok

**Mastok** components (the project's UI component system) use Anubis UI for their styles:

- All Mastok components (`MBtn`, `MCard`, `MChip`, etc.) use Anubis colors
- Color props (`primary`, `secondary`, `danger`, etc.) correspond to Anubis colors
- Components automatically generate the required Anubis classes
- **`Lucide.vue`** is the standard icon component in the Workproba shell

See [Mastok README](../front/lib-improba/components/mastok/README.md) for more details.

## Best practices

### 1. Always use Anubis and `--wp-*`

Do not mix Anubis colors with default Quasar colors. In Workproba shell components, prefer `--wp-*` for surfaces and spacing. This ensures:

- Visual consistency across the application
- Automatic light/dark mode support
- Easier maintenance

### 2. Use appropriate variants

Choose the color variant suited to the context:

- **Backgrounds**: Use `-lower` or `-lowest` for backgrounds
- **Text**: Use `-highest` or `-higher` for good contrast
- **Borders**: Use `-low` for subtle borders
- **Active elements**: Use the base color or `-high`

### 3. Prefer CSS variables in styles

In SCSS/CSS files, always use `var(--color-name)` or `var(--wp-*)` rather than hexadecimal values:

```scss
// ✅ Good
.my-class {
  color: var(--wp-text);
  background: var(--wp-surface);
}

// ❌ Bad
.my-class {
  color: #0f84cb;
}
```

### 4. Check contrast

In dark mode, some combinations may have insufficient contrast. Always test your interface in both light and dark mode.

### 5. Use utility classes when possible

Prefer utility classes in templates rather than writing custom CSS:

```vue
<!-- ✅ Good -->
<div class="bg-primary text-white rounded-md p-4">

<!-- ❌ Less good -->
<div class="custom-card">
```

```scss
.custom-card {
  background: var(--primary);
  color: white;
  border-radius: 8px;
  padding: 1rem;
}
```

## Practical examples

### Card with Anubis styling

```vue
<template>
  <div class="bg-neutral-lower border-neutral-sm rounded-md p-4 shadow-neutral-md">
    <h3 class="text-primary-higher weight-bold size-lg mb-2">Title</h3>
    <p class="text-neutral-high">Card description</p>
  </div>
</template>
```

### Button with variants

```vue
<template>
  <MBtn primary>Save</MBtn>
  <MBtn secondary>Cancel</MBtn>
  <MBtn danger flat>Delete</MBtn>
  <MBtn success>Confirm</MBtn>
</template>
```

### Alert message

```vue
<template>
  <div class="bg-warning-lower border-warning-sm text-warning-high rounded p-4">
    <p class="weight-bold mb-1">Warning</p>
    <p>This action is irreversible.</p>
  </div>
</template>
```

### Table with alternating rows

```vue
<template>
  <div class="bg-neutral-lower rounded">
    <div 
      v-for="(item, index) in items" 
      :key="item.id"
      :class="[
        'border-neutral-xs p-3',
        index % 2 === 0 ? 'bg-neutral-lowest' : 'bg-neutral-lower'
      ]"
    >
      {{ item.name }}
    </div>
  </div>
</template>
```

## Migration from Quasar

If you have existing code using Quasar colors:

| Quasar | Anubis |
|--------|--------|
| `color="primary"` | `class="bg-primary text-white"` |
| `text-grey-7` | `text-neutral-high` |
| `bg-grey-1` | `bg-neutral-lower` |
| `var(--q-primary)` | `var(--primary)` |
| `text-blue-6` | `text-primary` |

## References

- **[Complete Anubis UI guide](./anubis-ui.md)**, detailed documentation with all examples
- **[Architecture](./architecture.md)**, UI shell overview and message flow
- **[Mastok Components](../front/lib-improba/components/mastok/README.md)**, UI components using Anubis
- **[Demo page](../front/lib-improba/pages/demo/Anubis.vue)**, visual examples in the application (`demo-anubis` route)

## Summary

- ✅ **Use**: Workproba `--wp-*` tokens for all custom CSS (typography, spacing, surfaces, focus, chat)
- ✅ **Use**: Anubis classes (`bg-primary`, `text-neutral-highest`, etc.)
- ✅ **Use**: Anubis CSS variables (`var(--primary)`, `var(--neutral-lower)`, etc.)
- ✅ **Use**: Mastok components with color props; `Lucide` for icons
- ❌ **Avoid**: Hardcoded colors or sizes in Workproba components
- ❌ **Avoid**: Quasar colors (`color="primary"`, `text-grey-7`, etc.)
- ❌ **Avoid**: Hardcoded hexadecimal values in styles
- ❌ **Avoid**: Editing `_anubis.scss` or `anubis/_tokens.scss` manually
- ❌ **Avoid**: `lib-improba/css/_colors.scss` (legacy, not loaded)
