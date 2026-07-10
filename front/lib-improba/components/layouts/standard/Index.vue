<!--
  Composant Index - Point d'entrée du layout standard
  
  Ce composant sert de wrapper autour de StandardLayout et permet de :
  - Transmettre toutes les props via v-bind="$attrs"
  - Transmettre tous les slots dynamiquement (toolbar, toolbar-logo, default, etc.)
  
  Utilisation :
  ```vue
  <Layout :menuItems="customMenuItems">
    <template #toolbar>
      Contenu personnalisé dans la toolbar
    </template>
    <template #toolbar-logo>
      Logo personnalisé
    </template>
    Contenu de la page
  </Layout>
  ```
  
  Ce composant est exporté comme composant principal du layout standard,
  permettant une utilisation simple avec des props et slots personnalisés.
-->
<template>
  <StandardLayout v-bind="$attrs">
    <template v-for="(_, slot) in $slots" #[slot]="scope">
      <slot :name="slot" v-bind="scope" />
    </template>
  </StandardLayout>
</template>

<script setup lang="ts">
import StandardLayout from './StandardLayout.vue';
</script>
