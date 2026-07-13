# Postmortem: empty right file panel (permanent error triangle)

Date: 2026-07-10
Component: `front/src/components/workproba/FileExplorer.vue` + `front/src/composables/useFileTree.ts`

## Symptom

The desktop app right panel (file explorer) permanently displayed an
`alert-triangle` error with a "Retry" button,
but **no error text**, and the tree never rendered, regardless of the
opened folder.

## Expected behavior

When `list_dir_entries` succeeds (as Rust logs confirmed: 3 entries
returned for the `cor` folder), the error branch must not display and
the `RecycleScroller` must show the entries.

## Root cause

Vue 3 bug in the `FileExplorer.vue` template. `tree` is a plain object
returned by `useFileTree()` and `tree.error` / `tree.indexing` are `ref`s.

In Vue 3, `ref`s are **auto-unwrapped** in the template only for
**top-level** setup bindings. They are **not** unwrapped when accessed
via a nested object property (`tree.error`). The expression
`v-else-if="tree.error"` therefore evaluated the **ref object** itself, which is
**always truthy**. The error branch displayed permanently.

Since there was no real error (`tree.error.value` stayed `null`), the
computed `errorMessage` returned `''` (`raw === null` branch), hence the
triangle without text.

The code already showed the right pattern for `flatList`:
```ts
const flatList = computed(() => tree.flatList.value);
```
...precisely because `tree.flatList` does not unwrap on its own. But the same
wrapper was forgotten for `tree.error` and `tree.indexing`.

## Fix

Added top-level auto-unwrapped computeds in `FileExplorer.vue`:
```ts
const treeError = computed(() => tree.error.value);
const treeIndexing = computed(() => tree.indexing.value);
```

Corrected template (3 conditions):
- `v-else-if="tree.error"` -> `v-else-if="treeError"`
- `v-else-if="flatList.length === 0 && !tree.indexing"` -> `... && !treeIndexing`
- `v-if="tree.indexing && !tree.error"` -> `v-if="treeIndexing && !treeError"`

Flow after fix (nominal case, Rust success):
1. `v-if="!activePath"` -> false (folder open)
2. `v-else-if="treeError"` -> `tree.error.value` is `null` -> false
3. `v-else-if="flatList.length === 0 && !treeIndexing"` -> false (3 entries)
4. `v-else` `RecycleScroller` -> displays the tree

## Pitfalls encountered during diagnosis

1. **HMR not working in Tauri webview**: frontend edits are not
   hot-replaced in the Linux webview (webkitgtk). A full reload is
   required to see updated code. Symptom: "the UI does not change" after an edit.

2. **Startup race in `tauri dev`**: the Quasar dev server (`beforeDevCommand`)
   can start a second before the webview. The webview loads during
   initial compilation and picks up a partial bundle. Reloading once the
   dev server is ready fixes the stale state.

3. **No native reload shortcut**: Ctrl+R / F5 are not bound by default
   in a Tauri v2 webview on Linux. Fix: binding added in
   `WorkprobaLayout.vue` calling `getCurrentWindow().reload()` (with
   `location.reload()` fallback). Also reloadable via `location.reload()`
   in DevTools console.

4. **Console noise**: sidecar errors (port 8765 `Connection refused` /
   CORS) flood the console and hide diagnostic logs. The sidecar is
   a separate topic (the file explorer does not depend on it, it uses
   Tauri commands).

## Rule to remember

Always wrap in top-level computeds refs from a composable when
read in the template via a nested property (`tree.x`), or
use `tree.x.value` explicitly. Never do `v-if="tree.refProp"`:
that tests the ref object, not its value.

## Modified files

- `front/src/components/workproba/FileExplorer.vue`: bug fix (computed
  `treeError` / `treeIndexing` + template), "Retry" button, robust
  error message display, diagnostic `console.error`.
- `front/src/composables/useFileTree.ts`: robust catch guaranteeing a
  non-empty message + `console.error`.
- `front/src/layouts/WorkprobaLayout.vue`: Ctrl+R / F5 binding to reload
  the webview.
- `desktop/src-tauri/src/commands/project.rs`: `log::info!` / `log::warn!` on
  `list_dir_entries` for backend diagnostics.
