<!--
  Composant MChip - Badge/Puce Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-chip de Quasar qui applique le style Mastok
  et intègre le système de couleurs Anubis. Il est utilisé pour afficher des badges,
  tags ou labels avec différentes variantes de couleurs.
  
  Variantes de couleur disponibles :
  - primary (défaut) : Badge principal avec fond primary
  - secondary : Fond neutre avec bordure et texte primary
  - tertiary : Fond neutre avec texte neutre
  - light : Fond neutre clair avec texte sombre
  - danger : Fond danger (rouge)
  - success : Fond success (vert)
  - warning : Fond warning (orange/jaune)
  
  Props Mastok communes :
  - secondary, tertiary, light, danger, success, warning : Variantes de couleur
  - flat : Style plat (sans fond)
  - lucideIcon : Nom de l'icône Lucide à afficher
  
  Utilisation :
  ```vue
  <MChip primary>Nouveau</MChip>
  <MChip success>Actif</MChip>
  <MChip danger>Inactif</MChip>
  <MChip secondary lucideIcon="tag">Tag</MChip>
  ```
  
  Le composant supporte tous les slots de q-chip.
-->
<template>
  <q-chip
    :ripple="false"
    class="not-selectable rounded-md"
    :class="[mastok.colorInfos.value.color, mastok.colorInfos.value.text, mastok.colorInfos.value.border]"
  >
    <template
      v-for="([slotKey], index) in Object.entries($slots)"
      :key="index"
      v-slot:[slotKey]="scope"
    >
      <slot v-if="$slots[slotKey]" :name="slotKey" v-bind="{ ...scope }"></slot>
    </template>
  </q-chip>
</template>


<script setup lang="ts">
import { reactive } from 'vue';
import { defaultMastokProps, useMastok } from './use-mastok';

const props = defineProps(defaultMastokProps)

const state = reactive({
  hover: false
});

const mastok = useMastok(props)
</script>
