# Guide Anubis UI

Anubis UI est le framework CSS personnalisé utilisé dans ce projet. Il fournit un système de couleurs cohérent, des classes utilitaires et un support pour le mode clair/sombre.

## Vue d'ensemble

Anubis UI est intégré via le package npm `anubis-ui` et configuré dans `front/anubis.config.json`. Les styles sont définis dans `front/lib-improba/css/_colors.scss` et générés automatiquement lors du build.

## Système de couleurs

### Couleurs principales

Anubis UI définit plusieurs palettes de couleurs avec des variantes :

- **Primary** : Couleur principale de l'application (bleu par défaut)
- **Secondary** : Couleur secondaire (bleu-gris par défaut)
- **Neutral** : Couleurs neutres pour les arrière-plans et bordures
- **Success** : Vert pour les actions réussies
- **Danger** : Rouge pour les erreurs et actions destructives
- **Warning** : Ambre/Orange pour les avertissements

### Variantes de couleurs

Chaque couleur a plusieurs variantes :

- `-lowest` : La plus claire
- `-lower` : Très claire
- `-low` : Claire
- `-medium` : Couleur de base (sans suffixe)
- `-high` : Foncée
- `-higher` : Très foncée
- `-highest` : La plus foncée

### Support light/dark mode

Les couleurs Anubis s'adaptent automatiquement au mode clair/sombre via les variables CSS.

## Utilisation

### Dans les templates Vue

**✅ À FAIRE** : Utiliser les classes Anubis

```vue
<template>
  <div class="text-primary bg-neutral-lower">
    <q-btn class="bg-primary text-white">Action</q-btn>
    <p class="text-warning">Attention</p>
  </div>
</template>
```

**❌ À ÉVITER** : Utiliser les couleurs Quasar par défaut

```vue
<template>
  <!-- Ne pas utiliser -->
  <q-btn color="primary">Action</q-btn>
  <p class="text-grey-7">Texte</p>
</template>
```

### Dans les styles SCSS/CSS

**✅ À FAIRE** : Utiliser les variables CSS Anubis

```scss
.my-component {
  color: var(--primary);
  background-color: var(--neutral-lower);
  border-color: var(--warning);
}
```

**❌ À ÉVITER** : Utiliser les variables Quasar

```scss
.my-component {
  // Ne pas utiliser
  color: var(--q-primary);
  background-color: var(--q-grey-2);
}
```

### Classes utilitaires disponibles

#### Couleurs de texte

- `text-primary`, `text-primary-low`, `text-primary-high`, etc.
- `text-secondary`, `text-secondary-low`, etc.
- `text-neutral`, `text-neutral-low`, etc.
- `text-success`, `text-danger`, `text-warning`
- `text-text`, `text-text-invert`, `text-text-link`

#### Couleurs de fond

- `bg-primary`, `bg-primary-lowest`, `bg-primary-lower`, etc.
- `bg-secondary`, `bg-neutral-lower`, etc.
- `bg-success`, `bg-danger`, `bg-warning`

#### Bordures

- `border-primary`, `border-primary-xs`, `border-primary-sm`, etc.
- `border-neutral`, `border-success`, etc.

#### Ombres

- `shadow-primary`, `shadow-primary-xs`, `shadow-primary-sm`, etc.

## Configuration

### Fichier de configuration

Le fichier `front/anubis.config.json` définit :

- Les fichiers à scanner pour la génération des classes
- Les utilitaires à générer (bg, text, border, shadow, etc.)
- Les variations disponibles (xs, sm, md, lg, xl, etc.)

### Personnalisation des couleurs

Les couleurs de base sont définies dans `front/lib-improba/css/_colors.scss` :

```scss
$blue-500: #0f84cb;
$green-500: #00c99e;
// etc.
```

Pour modifier les couleurs, éditez ce fichier et régénérez les classes via le build.

## Exemples pratiques

### Bouton avec style Anubis

```vue
<template>
  <q-btn 
    class="bg-primary text-white"
    label="Valider"
  />
</template>
```

### Carte avec bordures et ombre

```vue
<template>
  <div class="bg-neutral-lower border-neutral-sm shadow-neutral-md rounded-lg p-4">
    Contenu de la carte
  </div>
</template>
```

### Message d'alerte

```vue
<template>
  <div class="bg-warning-lower border-warning text-warning-high p-4 rounded">
    <p class="text-warning">Attention : action irréversible</p>
  </div>
</template>
```

### Tableau avec lignes alternées

```vue
<template>
  <div class="bg-neutral-lower">
    <div 
      v-for="item in items" 
      :key="item.id"
      class="border-neutral-xs p-2"
    >
      {{ item.name }}
    </div>
  </div>
</template>
```

## Migration depuis Quasar

Si vous avez du code existant utilisant les couleurs Quasar :

1. Remplacer `color="primary"` par `class="bg-primary text-white"`
2. Remplacer `text-grey-7` par `text-neutral-high`
3. Remplacer `var(--q-primary)` par `var(--primary)` dans les styles
4. Utiliser `bg-neutral-lower` au lieu de `bg-grey-1`

## Référence complète

Pour voir tous les composants et styles disponibles, consultez la page de démonstration Anubis UI dans l'application (route `demo-anubis`).

## Bonnes pratiques

1. **Toujours utiliser Anubis** : Ne pas mélanger avec les couleurs Quasar
2. **Cohérence** : Utiliser les mêmes variantes de couleurs dans toute l'application
3. **Accessibilité** : Vérifier les contrastes, surtout en mode sombre
4. **Variables CSS** : Préférer les variables dans les styles plutôt que les valeurs hexadécimales

