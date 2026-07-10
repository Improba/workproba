# Postmortem: panneau fichier droit vide (triangle d'erreur permanent)

Date: 2026-07-10
Composant: `front/src/components/workproba/FileExplorer.vue` + `front/src/composables/useFileTree.ts`

## Symptôme

Le panneau droit de l'app desktop (explorateur de fichiers) affichait en
permanence un triangle d'erreur `alert-triangle` avec un bouton « Réessayer »,
mais **aucun texte d'erreur**, et l'arborescence ne s'affichait jamais, quelle
que soit le dossier ouvert.

## Comportement attendu

Quand `list_dir_entries` réussit (ce que le log Rust confirmait: 3 entrées
renvoyées pour le dossier `cor`), la branche erreur ne doit pas s'afficher et
le `RecycleScroller` doit afficher les entrées.

## Cause racine

Bug Vue 3 dans le template de `FileExplorer.vue`. `tree` est un objet plain
retourné par `useFileTree()` et `tree.error` / `tree.indexing` sont des `ref`.

Dans Vue 3, les `ref` sont **auto-déballées** dans le template uniquement pour
les bindings **top-level** du setup. Elles ne le sont **pas** quand on y accède
via une propriété nichée d'un objet (`tree.error`). L'expression
`v-else-if="tree.error"` évaluait donc l'**objet ref** lui-même, qui est
**toujours truthy**. La branche erreur s'affichait en permanence.

Comme il n'y avait aucune erreur réelle (`tree.error.value` restait `null`), le
computed `errorMessage` retournait `''` (branche `raw === null`), d'où le
triangle sans texte.

Le code montrait déjà la bonne pratique pour `flatList`:
```ts
const flatList = computed(() => tree.flatList.value);
```
...précisément parce que `tree.flatList` ne se déballle pas seul. Mais le même
wrapper avait été oublié pour `tree.error` et `tree.indexing`.

## Fix

Ajout de computed top-level auto-déballés dans `FileExplorer.vue`:
```ts
const treeError = computed(() => tree.error.value);
const treeIndexing = computed(() => tree.indexing.value);
```

Template corrigé (3 conditions):
- `v-else-if="tree.error"` -> `v-else-if="treeError"`
- `v-else-if="flatList.length === 0 && !tree.indexing"` -> `... && !treeIndexing`
- `v-if="tree.indexing && !tree.error"` -> `v-if="treeIndexing && !treeError"`

Flux après fix (cas nominal, succès Rust):
1. `v-if="!activePath"` -> faux (dossier ouvert)
2. `v-else-if="treeError"` -> `tree.error.value` est `null` -> faux
3. `v-else-if="flatList.length === 0 && !treeIndexing"` -> faux (3 entrées)
4. `v-else` `RecycleScroller` -> affiche l'arbre

## Pièges rencontrés pendant le diagnostic

1. **HMR non fonctionnel dans la webview Tauri**: les éditions frontend ne
   sont pas hot-replacées dans la webview Linux (webkitgtk). Un rechargement
   complet est nécessaire pour voir le code à jour. Symptôme: « l'interface ne
   bouge pas » après une édition.

2. **Race au démarrage `tauri dev`**: le dev server Quasar (`beforeDevCommand`)
   peut démarrer une seconde avant la webview. La webview charge pendant la
   compilation initiale et récupère un bundle partiel. Un rechargement une fois
   le dev server prêt résout l'état stale.

3. **Pas de raccourci reload natif**: Ctrl+R / F5 ne sont pas bindés par défaut
   dans une webview Tauri v2 sur Linux. Fix: binding ajouté dans
   `WorkprobaLayout.vue` qui appelle `getCurrentWindow().reload()` (avec
   fallback `location.reload()`). Rechargeable aussi via `location.reload()`
   dans la console DevTools.

4. **Bruit console**: les erreurs du sidecar (port 8765 `Connection refused` /
   CORS) inondent la console et masquent les logs de diagnostic. Le sidecar est
   un sujet séparé (l'explorateur de fichiers n'en dépend pas, il utilise des
   commandes Tauri).

## Règle à retenir

Toujours wrappers en computed top-level les refs issues d'un composable quand
elles sont lues dans le template via une propriété nichée (`tree.x`), ou
utiliser `tree.x.value` explicitement. Ne jamais faire `v-if="tree.refProp"`:
cela teste l'objet ref, pas sa valeur.

## Fichiers modifiés

- `front/src/components/workproba/FileExplorer.vue`: fix du bug (computed
  `treeError` / `treeIndexing` + template), bouton « Réessayer », affichage
  robuste du message d'erreur, `console.error` de diagnostic.
- `front/src/composables/useFileTree.ts`: catch robuste garantissant un
  message non vide + `console.error`.
- `front/src/layouts/WorkprobaLayout.vue`: binding Ctrl+R / F5 pour recharger
  la webview.
- `desktop/src-tauri/src/commands/project.rs`: `log::info!` / `log::warn!` sur
  `list_dir_entries` pour diagnostic backend.
