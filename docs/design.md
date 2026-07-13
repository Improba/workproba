# Design System

This document describes the design system used in this project, centered around the **Anubis UI** library for color and style management.

## Overview

The project uses **Anubis UI** (`anubis-ui` v1.3.1), a custom CSS framework that provides:

- A consistent color system with light/dark mode support
- Automatically generated utility classes
- CSS variables for flexible usage
- Seamless integration with Quasar Framework

Workproba adds a dedicated **`--wp-*`** token system on top (defined in `front/src/css/workproba.scss`) for all custom application CSS: typography, focus, spacing, density, surfaces, and brand accents.

## Workproba Tokens (`--wp-*`)

### Role in the architecture

| Layer | Usage |
|--------|-------|
| **`--wp-*`** | Semantic aliases for the Workproba **shell** (surfaces, borders, typography, focus), defined in `workproba.scss`, often mapped to Anubis (`var(--neutral-lower)`, etc.) |
| **Anubis** (`--primary`, `--neutral-*`, `bg-*` / `text-*` classes) | **Palette source of truth** via `anubis.config.json` → `_anubis.scss` |
| **Quasar** | Structural components; colors via `--q-*` synchronized in `workproba.scss` |

**Contribution rule**: all custom styling in a Workproba component goes through `--wp-*` tokens. No hardcoded colors or sizes (`#203d52`, `14px`, etc.) in component `.vue` / `.scss` files.

### Typography

| Token | Value | Role |
|-------|--------|------|
| `--wp-fs-xs` | 12px | Tertiary text, compact labels |
| `--wp-fs-sm` | 13px | Secondary text, hints |
| `--wp-fs-base` | 15px | Default body text |
| `--wp-fs-md` | 17px | Subtitles, section titles |
| `--wp-fs-lg` | 20px | Intermediate titles |
| `--wp-fs-xl` | 24px | Page titles |
| `--wp-fs-display` | 32px | Hero display |
| `--wp-lh-tight` | 1.2 | Titles, labels |
| `--wp-lh-normal` | 1.5 | Body text |
| `--wp-lh-relaxed` | 1.65 | Spacious paragraphs |
| `--wp-font-ui` | Varela Round, … | Interface font |
| `--wp-font-head` | Inter, … | Titles and chat |
| `--wp-font-mono` | JetBrains Mono, … | Code, keyboard shortcuts |

### Keyboard focus

| Token | Role |
|-------|------|
| `--wp-focus-ring` | `:focus-visible` ring, `var(--accent-high)` (light cyan, dark gold) |
| `--wp-focus-offset` | Outline offset (2px) |

Applied globally on `.wp-shell` for titlebar, sidebar, explorer, composer, and buttons.

### Spacing and density

The `--wp-space-1` through `--wp-space-6` tokens define the spacing scale. Their values depend on the `data-density` attribute on the root layout (`.wp-shell`), driven by `useAppSettings.density`:

| Density | `--wp-space-1` … `--wp-space-6` | Usage |
|---------|----------------------------------|-------|
| `compact` | 2, 4, 8, 12, 16, 20 px | Power users, dense screens |
| `comfortable` (default) | 4, 8, 12, 16, 20, 24 px | Guided / locked flow |
| `spacious` | 6, 10, 14, 20, 28, 32 px | Maximum readability |

### Surfaces, borders, and accents

| Token | Role |
|-------|------|
| `--wp-bg` | Global application background |
| `--wp-surface`, `--wp-surface-2`, `--wp-surface-3` | Cards, panels, elevated areas |
| `--wp-border`, `--wp-border-strong` | Separators and outlines |
| `--wp-text`, `--wp-text-muted`, `--wp-text-faint` | Text hierarchy |
| `--wp-primary`, `--wp-primary-soft` | Branding: teal (light) / gold (dark), via `var(--primary)` |
| `--wp-accent`, `--wp-accent-strong`, `--wp-accent-soft` | Actions, focus, active tabs: cyan (light) / gold (dark) |
| `--wp-canard`, `--wp-cyan`, `--wp-gold`, `--wp-violet` | Improba brand accents (stable across themes) |
| `--wp-success`, `--wp-danger`, `--wp-danger-soft` | Semantic states |
| `--wp-r-sm` … `--wp-r-pill` | Border radii |
| `--wp-shadow-1`, `--wp-shadow-2` | Light shadows |
| `--wp-ease`, `--wp-dur` | Transitions (180ms) |

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
| **Accent** | Visual accents | Highlighted elements (same as primary) |
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
// Light: teal + cyan
primary:       #203d52 / n/a
accent:        #2bb5c2 / n/a
neutral-lowest: #ffffff / n/a
text:          #1c2a36 / n/a

// Dark: warm charcoal + gold
primary:       n/a / #e0a93a
accent:        n/a / #e0a93a
neutral-lowest: n/a / #161514
neutral-lower:  n/a / #1f1e1c
text:          n/a / #eceae6
text-link:     n/a / #ffcc49
success:       n/a / #4ade80
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

**❌ AVOID**: Using default Quasar colors

```vue
<template>
  <!-- Do not use -->
  <q-btn color="primary">Action</q-btn>
  <p class="text-grey-7">Text</p>
  <div class="bg-grey-1">Content</div>
</template>
```

### In SCSS/CSS styles

**✅ DO**: Use Anubis CSS variables

```scss
.my-component {
  color: var(--primary);
  background-color: var(--neutral-lower);
  border-color: var(--warning);
  
  &:hover {
    background-color: var(--primary-lower);
  }
}

.custom-card {
  background: var(--neutral-lowest);
  border: 1px solid var(--neutral-low);
  box-shadow: 0px 2px 8px var(--neutral-high-20); // 20% opacity
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

See [Mastok README](../front/lib-improba/components/mastok/README.md) for more details.

## Best practices

### 1. Always use Anubis

Do not mix Anubis colors with default Quasar colors. This ensures:

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

In SCSS/CSS files, always use `var(--color-name)` rather than hexadecimal values:

```scss
// ✅ Good
.my-class {
  color: var(--primary);
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
- **[Mastok Components](../front/lib-improba/components/mastok/README.md)**, UI components using Anubis
- **[Demo page](../front/lib-improba/pages/demo/Anubis.vue)**, visual examples in the application (`demo-anubis` route)

## Summary

- ✅ **Use**: Workproba `--wp-*` tokens for all custom CSS (typography, spacing, surfaces, focus)
- ✅ **Use**: Anubis classes (`bg-primary`, `text-neutral-highest`, etc.)
- ✅ **Use**: Anubis CSS variables (`var(--primary)`, `var(--neutral-lower)`, etc.)
- ✅ **Use**: Mastok components with color props
- ❌ **Avoid**: Hardcoded colors or sizes in Workproba components
- ❌ **Avoid**: Quasar colors (`color="primary"`, `text-grey-7`, etc.)
- ❌ **Avoid**: Hardcoded hexadecimal values in styles
- ❌ **Avoid**: Editing `_anubis.scss` or `anubis/_tokens.scss` manually
- ❌ **Avoid**: `lib-improba/css/_colors.scss` (legacy, not loaded)
