<!--
  Composant Lucide - Wrapper pour les icônes Lucide avec intégration Anubis/Mastok
  
  Ce composant est un wrapper autour de la bibliothèque lucide-vue-next qui permet
  d'utiliser les icônes Lucide de manière cohérente avec le système de design Mastok/Anubis.
  
  Fonctionnalités principales :
  - Accès à toutes les icônes Lucide via la prop 'name'
  - Intégration avec le système de couleurs Anubis (utilise var(--color))
  - Tailles prédéfinies : xs (18px), sm (24px), md (32px), lg (38px), xl (46px)
  - Support d'une valeur numérique directe pour la taille
  - Support optionnel d'un label texte à côté de l'icône
  
  Utilisation directe :
  ```vue
  <Lucide name="home" size="md" color="primary" />
  <Lucide name="user" size="sm" color="neutral-highest" label="Profil" />
  ```
  
  Utilisation dans les composants Mastok :
  Les composants MBtn et MBtnDropdown utilisent ce composant via la prop 'lucideIcon' :
  ```vue
  <MBtn lucideIcon="save" primary>Sauvegarder</MBtn>
  <MBtnDropdown lucideIcon="menu" flat />
  ```
  
  Props :
  - name (required): Nom de l'icône Lucide (ex: "home", "user", "save")
  - size: Taille de l'icône - peut être 'xs', 'sm', 'md', 'lg', 'xl' ou un nombre (défaut: '16')
  - color: Couleur Anubis à utiliser (défaut: 'neutral-highest')
  - label: Texte optionnel à afficher à côté de l'icône
  - class: Classes CSS additionnelles
-->
<template>
  <component
    :is="iconComponent"
    :stroke="`var(--${props.color})`"
    :size="calculatedSize"
    :class="{ 'q-mr-sm': props.label }"
  />
  <span v-if="props.label" v-html="label" />
</template>

<script setup lang="ts">
import * as icons from 'lucide-vue-next';
import { computed } from 'vue';
const props = defineProps({
  name: {
    type: String,
    required: true
  },
  size: {
    type: String, Number,
    default: '16'
  },
  color: {
    type: String,
    default: 'neutral-highest'
  },
  label: {
    type: String,
    default: null
  },
  class: {
    type: String
  }
})

const calculatedSize = computed(() => {
  switch (props.size) {
    case 'xs':
      return 18

    case 'sm':
      return 24

    case 'md':
      return 32

    case 'lg':
      return 38

    case 'xl':
      return 46

    default:
      return props.size
  }
})

// lucide-vue-next n'exporte qu'en PascalCase (Send, ChevronRight…).
// On normalise kebab/snake -> PascalCase pour résoudre l'icône.
const iconComponent = computed(() => {
  const pascal = props.name
    .split(/[-_]/)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join('')
  return (icons as Record<string, unknown>)[pascal] ?? null
})
</script>
