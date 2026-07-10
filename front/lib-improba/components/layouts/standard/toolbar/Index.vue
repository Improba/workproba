<!--
  Composant Index (Toolbar) - Wrapper pour StandardToolbar
  
  Ce composant sert de point d'entrée pour la toolbar standard et permet de :
  - Transmettre les props à StandardToolbar
  - Gérer les slots logo et default pour personnaliser la toolbar
  
  Utilisation :
  ```vue
  <StandardToolbarWrapper
    :menuItems="menuItems"
    :userMenuItems="userMenuItems"
  >
    <template #logo>
      <CustomLogo />
    </template>
    <MBtn>Action personnalisée</MBtn>
  </StandardToolbarWrapper>
  ```
  
  Ce composant est utilisé par StandardLayout pour afficher la toolbar.
-->
<template>
  <StandardToolbar
    :menuItems="props.menuItems"
    :userMenuItems="props.userMenuItems"
    :roleTitle="props.roleTitle"
    :themeLabel="props.themeLabel"
  >
    <template #logo v-if="$slots.logo">
      <slot name="logo" />
    </template>
    <template #default>
      <slot />
    </template>
  </StandardToolbar>
</template>

<script setup lang="ts">
import StandardToolbar from './StandardToolbar.vue';
import type { StandardToolbarProps } from '../types/toolbar-props.types';

const props = defineProps<StandardToolbarProps>();
</script>

