# Système de design

Ce document décrit le système de design utilisé dans ce projet, centré autour de la bibliothèque **Anubis UI** pour la gestion des couleurs et des styles.

## Vue d'ensemble

Le projet utilise **Anubis UI** (`anubis-ui` v1.3.1), un framework CSS personnalisé qui fournit :

- Un système de couleurs cohérent avec support du mode clair/sombre
- Des classes utilitaires générées automatiquement
- Des variables CSS pour une utilisation flexible
- Une intégration transparente avec Quasar Framework

Workproba ajoute par-dessus un système de tokens dédiés **`--wp-*`** (définis dans `front/src/css/workproba.scss`) pour tout le CSS custom de l'application : typographie, focus, espacement, densité, surfaces et accents de marque.

## Tokens Workproba (`--wp-*`)

### Rôle dans l'architecture

| Couche | Usage |
|--------|-------|
| **`--wp-*`** | Alias sémantiques du **shell** Workproba (surfaces, bordures, typo, focus) — définis dans `workproba.scss`, souvent mappés sur Anubis (`var(--neutral-lower)`, etc.) |
| **Anubis** (`--primary`, `--neutral-*`, classes `bg-*` / `text-*`) | **Source de vérité palette** via `anubis.config.json` → `_anubis.scss` |
| **Quasar** | Composants structurels ; couleurs via `--q-*` synchronisées dans `workproba.scss` |

**Règle de contribution** : tout style custom dans un composant Workproba passe par les tokens `--wp-*`. Pas de couleur ni de taille en dur (`#203d52`, `14px`, etc.) dans les fichiers `.vue` / `.scss` des composants.

### Typographie

| Token | Valeur | Rôle |
|-------|--------|------|
| `--wp-fs-xs` | 12px | Texte tertiaire, labels compacts |
| `--wp-fs-sm` | 13px | Texte secondaire, hints |
| `--wp-fs-base` | 15px | Corps de texte par défaut |
| `--wp-fs-md` | 17px | Sous-titres, titres de section |
| `--wp-fs-lg` | 20px | Titres intermédiaires |
| `--wp-fs-xl` | 24px | Titres de page |
| `--wp-fs-display` | 32px | Affichage hero |
| `--wp-lh-tight` | 1.2 | Titres, labels |
| `--wp-lh-normal` | 1.5 | Corps de texte |
| `--wp-lh-relaxed` | 1.65 | Paragraphes aérés |
| `--wp-font-ui` | Varela Round, … | Police interface |
| `--wp-font-head` | Inter, … | Titres et chat |
| `--wp-font-mono` | JetBrains Mono, … | Code, raccourcis clavier |

### Focus clavier

| Token | Rôle |
|-------|------|
| `--wp-focus-ring` | Anneau `:focus-visible` — `var(--accent-high)` (cyan clair, or sombre) |
| `--wp-focus-offset` | Décalage de l'outline (2px) |

Appliqué globalement sur `.wp-shell` pour titlebar, sidebar, explorateur, composer et boutons.

### Espacement et densité

Les tokens `--wp-space-1` à `--wp-space-6` définissent l'échelle d'espacement. Leur valeur dépend de l'attribut `data-density` sur le layout racine (`.wp-shell`), piloté par `useAppSettings.density` :

| Densité | `--wp-space-1` … `--wp-space-6` | Usage |
|---------|----------------------------------|-------|
| `compact` | 2, 4, 8, 12, 16, 20 px | Power-users, écrans denses |
| `comfortable` (défaut) | 4, 8, 12, 16, 20, 24 px | Parcours guidé / verrouillé |
| `spacious` | 6, 10, 14, 20, 28, 32 px | Lisibilité maximale |

### Surfaces, bordures et accents

| Token | Rôle |
|-------|------|
| `--wp-bg` | Fond global de l'application |
| `--wp-surface`, `--wp-surface-2`, `--wp-surface-3` | Cartes, panneaux, zones surélevées |
| `--wp-border`, `--wp-border-strong` | Séparateurs et contours |
| `--wp-text`, `--wp-text-muted`, `--wp-text-faint` | Hiérarchie de texte |
| `--wp-primary`, `--wp-primary-soft` | Branding : canard (clair) / or (sombre), via `var(--primary)` |
| `--wp-accent`, `--wp-accent-strong`, `--wp-accent-soft` | Actions, focus, onglets actifs : cyan (clair) / or (sombre) |
| `--wp-canard`, `--wp-cyan`, `--wp-gold`, `--wp-violet` | Accents de marque Improba (stables entre thèmes) |
| `--wp-success`, `--wp-danger`, `--wp-danger-soft` | États sémantiques |
| `--wp-r-sm` … `--wp-r-pill` | Rayons de bordure |
| `--wp-shadow-1`, `--wp-shadow-2` | Ombres légères |
| `--wp-ease`, `--wp-dur` | Transitions (180ms) |

### Fichier source

- **Palette** (`--primary`, `--neutral-*`, sémantique) : `front/anubis.config.json` → génère `_anubis.scss`. Voir [anubis-ui.md](./anubis-ui.md).
- **Shell** (`--wp-*`, typo, densité, `--q-*`) : `front/src/css/workproba.scss`, chargé **après** `_anubis.scss`.

## Anubis UI

### Qu'est-ce qu'Anubis UI ?

Anubis UI est une bibliothèque CSS qui génère automatiquement des classes utilitaires et des variables CSS à partir d'une configuration JSON. Elle permet de :

1. **Définir un système de couleurs** avec des variantes pour le mode clair et sombre
2. **Générer des classes utilitaires** (bg, text, border, shadow, etc.) uniquement pour les classes utilisées dans le code
3. **Créer des variables CSS** accessibles dans les styles SCSS/CSS
4. **Supporter le mode clair/sombre** automatiquement via les variables CSS

### Intégration dans le projet

Anubis UI est intégré via :

- **Package npm** : `anubis-ui@^1.4.4` (déclaré dans `front/package.json`)
- **Plugin Vite** : Configuré dans `front/quasar.config.js` via `anubis.plugin`
- **Configuration couleurs** : `front/anubis.config.json` (section `"colors"`) — **source de vérité**
- **Styles générés** : `front/src/css/_anubis.scss`, `front/src/css/anubis/_tokens.scss` (ne pas éditer à la main)
- **Tokens shell** : `front/src/css/workproba.scss` (`--wp-*`, `--q-*` uniquement)

### Fonctionnement

1. **Scan du code** : Anubis scanne les fichiers `.vue` et `*use-mastok.ts` pour détecter les classes utilisées
2. **Génération** : Seules les classes détectées sont générées dans `_anubis.scss`
3. **Variables CSS** : Les couleurs sont exposées comme variables CSS (`--primary`, `--neutral-lower`, etc.)
4. **Mode clair/sombre** : Les variables changent automatiquement selon la classe `body--light` ou `body--dark`

## Système de couleurs

### Palette de couleurs

Le système définit plusieurs palettes avec leurs variantes :

| Couleur | Usage | Exemple |
|---------|-------|---------|
| **Primary** | Couleur principale de l'application | Actions principales, liens importants |
| **Secondary** | Couleur secondaire | Éléments secondaires, bordures |
| **Neutral** | Couleurs neutres | Arrière-plans, textes, séparateurs |
| **Success** | Actions réussies | Messages de succès, validations |
| **Danger** | Erreurs et actions destructives | Messages d'erreur, boutons de suppression |
| **Warning** | Avertissements | Messages d'avertissement, alertes |
| **Accent** | Accents visuels | Éléments mis en avant (identique à primary) |
| **Text** | Couleurs de texte | Texte principal, texte inversé, liens |

### Variantes de couleurs

Chaque couleur dispose de 7 variantes pour créer une hiérarchie visuelle :

| Suffixe | Description | Usage typique |
|---------|-------------|---------------|
| `-lowest` | La plus claire | Arrière-plans très clairs |
| `-lower` | Très claire | Arrière-plans clairs, zones secondaires |
| `-low` | Claire | Bordures subtiles, états hover légers |
| *(sans suffixe)* | Couleur de base | Couleur principale |
| `-medium` | Identique à la base | Alias pour la couleur principale |
| `-high` | Foncée | Textes sur fond clair, éléments importants |
| `-higher` | Très foncée | Textes très contrastés |
| `-highest` | La plus foncée | Textes sur fond clair, maximum de contraste |

### Support du mode clair/sombre

Les couleurs s'adaptent automatiquement au thème :

- **Mode clair** (`body.body--light`) : Utilise les valeurs définies pour `light`
- **Mode sombre** (`body.body--dark`) : Utilise les valeurs définies pour `dark`

Les variantes sont inversées intelligemment : par exemple, `neutral-lowest` est blanc en mode clair et très foncé en mode sombre, garantissant toujours un bon contraste.

### Exemples de couleurs (Workproba)

Valeurs définies dans `front/anubis.config.json` :

```text
// Clair — canard + cyan
primary:       #203d52 / —
accent:        #2bb5c2 / —
neutral-lowest: #ffffff / —
text:          #1c2a36 / —

// Sombre — Charbon chaud + or
primary:       — / #e0a93a
accent:        — / #e0a93a
neutral-lowest: — / #161514
neutral-lower:  — / #1f1e1c
text:          — / #eceae6
text-link:     — / #ffcc49
success:       — / #4ade80
```

Liste complète et procédure de modification : [anubis-ui.md](./anubis-ui.md).

## Utilisation

### Dans les templates Vue

**✅ À FAIRE** : Utiliser les classes Anubis

```vue
<template>
  <div class="bg-neutral-lower text-neutral-highest">
    <q-btn class="bg-primary text-white">Action principale</q-btn>
    <p class="text-warning">Message d'avertissement</p>
    <div class="bg-success-lower border-success text-success-high">
      Opération réussie
    </div>
  </div>
</template>
```

**❌ À ÉVITER** : Utiliser les couleurs Quasar par défaut

```vue
<template>
  <!-- Ne pas utiliser -->
  <q-btn color="primary">Action</q-btn>
  <p class="text-grey-7">Texte</p>
  <div class="bg-grey-1">Contenu</div>
</template>
```

### Dans les styles SCSS/CSS

**✅ À FAIRE** : Utiliser les variables CSS Anubis

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
  box-shadow: 0px 2px 8px var(--neutral-high-20); // Opacité 20%
}
```

**❌ À ÉVITER** : Utiliser les variables Quasar ou valeurs hexadécimales

```scss
.my-component {
  // Ne pas utiliser
  color: var(--q-primary);
  background-color: var(--q-grey-2);
  color: #0f84cb; // Valeur hexadécimale hardcodée
}
```

### Classes utilitaires disponibles

#### Couleurs de fond (`bg-*`)

```vue
<div class="bg-primary">Fond primary</div>
<div class="bg-primary-lower">Fond primary clair</div>
<div class="bg-neutral-lowest">Fond neutre très clair</div>
<div class="bg-success">Fond success</div>
<div class="bg-danger-lower">Fond danger clair</div>
```

#### Couleurs de texte (`text-*`)

```vue
<p class="text-primary">Texte primary</p>
<p class="text-neutral-highest">Texte neutre foncé</p>
<p class="text-success">Texte success</p>
<p class="text-danger-high">Texte danger foncé</p>
<p class="text-text-link">Lien</p>
```

#### Bordures (`border-*`)

```vue
<div class="border-primary">Bordure primary (1px)</div>
<div class="border-neutral-xs">Bordure neutre fine (1px)</div>
<div class="border-warning-sm">Bordure warning (2px)</div>
<div class="border-success-md">Bordure success (3px)</div>
```

Variations disponibles : `xs` (1px), `sm` (2px), `md` (3px), `lg` (6px), `xl` (8px), `xxl` (10px)

#### Ombres (`shadow-*`)

```vue
<div class="shadow-primary">Ombre primary</div>
<div class="shadow-neutral-xs">Ombre neutre petite</div>
<div class="shadow-warning-lg">Ombre warning grande</div>
```

Variations disponibles : `xs`, `sm`, `md`, `lg`, `xl`

#### Autres utilitaires

- **Bordures internes** : `inner-border-{color}-{size}`
- **Blur** : `blur` (backdrop-filter)
- **Transitions** : `smooth`, `smooth-slow`, `smooth-quick`, etc.
- **Bordures arrondies** : `rounded`, `rounded-md`, `rounded-lg`, `rounded-full`, etc.
- **Tailles de texte** : `size-xs`, `size-sm`, `size-md`, `size-lg`, etc.
- **Poids de police** : `weight-light`, `weight-normal`, `weight-bold`, etc.

## Configuration

### Fichier `anubis.config.json`

Ce fichier définit :

1. **Fichiers à scanner** : `**/*.vue` et `**/*use-mastok.ts`
2. **Utilitaires à générer** : bg, text, border, shadow, blur, smooth, rounded, etc.
3. **Couleurs disponibles** : Toutes les couleurs avec leurs variantes light/dark
4. **Variations** : Tailles, épaisseurs, etc. pour chaque utilitaire

### Personnalisation des couleurs

1. Éditer **`front/anubis.config.json`** → section `"colors"` (chaque token : `{ "light": "…", "dark": "…" }`).
2. Relancer le dev server, ou exécuter `node -e "require('anubis-ui/dist/tools/main').init()"` dans `front/`.
3. Pour le shell uniquement (surfaces, ombres, `--q-*` Quasar) : compléter dans `front/src/css/workproba.scss`.

Le fichier `front/lib-improba/css/_colors.scss` est un legacy Mastok **non importé** au build ; ne pas l'utiliser pour Workproba.

Guide détaillé : [anubis-ui.md](./anubis-ui.md).

### Génération des classes

Les classes sont générées automatiquement lors du build :

- Anubis scanne le code source
- Détecte les classes utilisées (ex: `bg-primary`, `text-neutral-highest`)
- Génère uniquement les classes détectées dans `front/src/css/_anubis.scss`

**Note** : Si vous ajoutez une nouvelle classe dans votre code, elle sera automatiquement générée au prochain build.

## Intégration avec Mastok

Les composants **Mastok** (système de composants UI du projet) utilisent Anubis UI pour leurs styles :

- Tous les composants Mastok (`MBtn`, `MCard`, `MChip`, etc.) utilisent les couleurs Anubis
- Les props de couleur (`primary`, `secondary`, `danger`, etc.) correspondent aux couleurs Anubis
- Les composants génèrent automatiquement les classes Anubis nécessaires

Voir [Mastok README](../front/lib-improba/components/mastok/README.md) pour plus de détails.

## Bonnes pratiques

### 1. Toujours utiliser Anubis

Ne pas mélanger les couleurs Anubis avec les couleurs Quasar par défaut. Cela garantit :

- Une cohérence visuelle dans toute l'application
- Un support automatique du mode clair/sombre
- Une maintenance plus facile

### 2. Utiliser les variantes appropriées

Choisissez la variante de couleur adaptée au contexte :

- **Arrière-plans** : Utilisez `-lower` ou `-lowest` pour les fonds
- **Textes** : Utilisez `-highest` ou `-higher` pour un bon contraste
- **Bordures** : Utilisez `-low` pour des bordures subtiles
- **Éléments actifs** : Utilisez la couleur de base ou `-high`

### 3. Préférer les variables CSS dans les styles

Dans les fichiers SCSS/CSS, utilisez toujours `var(--color-name)` plutôt que les valeurs hexadécimales :

```scss
// ✅ Bon
.my-class {
  color: var(--primary);
}

// ❌ Mauvais
.my-class {
  color: #0f84cb;
}
```

### 4. Vérifier les contrastes

En mode sombre, certaines combinaisons peuvent avoir un contraste insuffisant. Testez toujours votre interface en mode clair et sombre.

### 5. Utiliser les classes utilitaires quand possible

Préférez les classes utilitaires dans les templates plutôt que d'écrire du CSS personnalisé :

```vue
<!-- ✅ Bon -->
<div class="bg-primary text-white rounded-md p-4">

<!-- ❌ Moins bon -->
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

## Exemples pratiques

### Carte avec style Anubis

```vue
<template>
  <div class="bg-neutral-lower border-neutral-sm rounded-md p-4 shadow-neutral-md">
    <h3 class="text-primary-higher weight-bold size-lg mb-2">Titre</h3>
    <p class="text-neutral-high">Description de la carte</p>
  </div>
</template>
```

### Bouton avec variantes

```vue
<template>
  <MBtn primary>Sauvegarder</MBtn>
  <MBtn secondary>Annuler</MBtn>
  <MBtn danger flat>Supprimer</MBtn>
  <MBtn success>Valider</MBtn>
</template>
```

### Message d'alerte

```vue
<template>
  <div class="bg-warning-lower border-warning-sm text-warning-high rounded p-4">
    <p class="weight-bold mb-1">Attention</p>
    <p>Cette action est irréversible.</p>
  </div>
</template>
```

### Tableau avec lignes alternées

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

## Migration depuis Quasar

Si vous avez du code existant utilisant les couleurs Quasar :

| Quasar | Anubis |
|--------|--------|
| `color="primary"` | `class="bg-primary text-white"` |
| `text-grey-7` | `text-neutral-high` |
| `bg-grey-1` | `bg-neutral-lower` |
| `var(--q-primary)` | `var(--primary)` |
| `text-blue-6` | `text-primary` |

## Références

- **[Guide Anubis UI complet](./anubis-ui.md)** — Documentation détaillée avec tous les exemples
- **[Mastok Components](../front/lib-improba/components/mastok/README.md)** — Composants UI utilisant Anubis
- **[Page de démonstration](../front/lib-improba/pages/demo/Anubis.vue)** — Exemples visuels dans l'application (route `demo-anubis`)

## Résumé

- ✅ **Utiliser** : Tokens Workproba `--wp-*` pour tout CSS custom (typo, espacement, surfaces, focus)
- ✅ **Utiliser** : Classes Anubis (`bg-primary`, `text-neutral-highest`, etc.)
- ✅ **Utiliser** : Variables CSS Anubis (`var(--primary)`, `var(--neutral-lower)`, etc.)
- ✅ **Utiliser** : Composants Mastok avec props de couleur
- ❌ **Éviter** : Couleurs ou tailles en dur dans les composants Workproba
- ❌ **Éviter** : Couleurs Quasar (`color="primary"`, `text-grey-7`, etc.)
- ❌ **Éviter** : Valeurs hexadécimales hardcodées dans les styles
- ❌ **Éviter** : Éditer `_anubis.scss` ou `anubis/_tokens.scss` à la main
- ❌ **Éviter** : `lib-improba/css/_colors.scss` (legacy, non chargé)

