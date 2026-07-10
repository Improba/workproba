<!--
  Composant MBtn - Bouton Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-btn de Quasar qui applique le style Mastok
  et intègre le système de couleurs Anubis. Il supporte les icônes Lucide et toutes
  les variantes de couleurs Mastok.
  
  Variantes de couleur disponibles :
  - primary (défaut) : Bouton principal avec fond primary
  - secondary : Fond neutre avec bordure et texte primary
  - tertiary : Fond neutre avec texte neutre
  - light : Fond neutre clair avec texte sombre
  - danger : Fond danger (rouge)
  - success : Fond success (vert)
  - warning : Fond warning (orange/jaune)
  
  Props Mastok communes :
  - secondary, tertiary, light, danger, success, warning : Variantes de couleur
  - flat : Style plat (sans fond)
  - lucideIcon : Nom de l'icône Lucide à afficher (ex: "save", "delete", "edit")
  
  Utilisation :
  ```vue
  <MBtn primary>Sauvegarder</MBtn>
  <MBtn secondary lucideIcon="edit">Modifier</MBtn>
  <MBtn danger flat lucideIcon="trash">Supprimer</MBtn>
  ```
  
  Le composant supporte tous les slots et événements de q-btn.
-->
<template>
  <q-btn
    class="rounded smooth shadow-none"

    no-caps
    :ripple="false"
    :elevation="0"

    :flat="props.flat"

    :color="mastok.colorInfos.value.color.replace(/^bg-/, '')"
    :class="props.flat || [mastok.colorInfos.value.text, mastok.colorInfos.value.border]"

    @mouseover="state.hover = true"
    @mouseout="state.hover = false"
  >
    <!-- @vue-ignore -->
    <template
      v-for="([slotKey], index) in Object.entries($slots)"
      :key="index"
      v-slot:[slotKey]="scope"
    >
      <slot v-if="$slots[slotKey]" :name="slotKey" v-bind="{ ...scope }"></slot>
    </template>

    <Lucide
      v-if="!!lucideIcon"
      :name="lucideIcon"
      :color="
        props.flat
          ? mastok.colorInfos.value.color
          : mastok.colorInfos.value.text
      "
      class="q-ml-xs"
    />
  </q-btn>
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
