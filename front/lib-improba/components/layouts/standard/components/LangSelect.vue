<!--
  Composant LangSelect - Sélecteur de langue
  
  Ce composant permet à l'utilisateur de changer la langue de l'application.
  Il affiche un dropdown avec les langues disponibles et synchronise la sélection
  avec le système i18n de l'application.
  
  Langues disponibles :
  - Français (fr)
  - English (en-US)
  
  Fonctionnement :
  - Au montage : initialise la langue actuelle depuis i18n.locale
  - Au changement : met à jour la langue via setLang() qui persiste le choix
  
  Utilisation :
  ```vue
  <LangSelect />
  ```
  
  Note : Ce composant utilise QSelect (Quasar natif) pour l'affichage.
  Il peut être intégré dans le menu utilisateur ou dans la toolbar.
-->
<template>
  <div>
    <q-select
      class="q-pa-none"
      v-model="state.lang"
      :options="stateless.languages"
      map-options
      emit-value
      dense
      color="accent-medium"
      popup-content-class="popup-labels-de-emphasize"
      style="min-width: 8rem"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, watch, onMounted } from 'vue';
import { i18n, setLang } from '@boot/i18n';

/**
 * Liste des langues disponibles dans l'application
 * Chaque langue a un label (affiché) et une value (code de locale)
 */
const stateless = {
  languages: [
    {
      label: 'Français',
      value: 'fr',
    },
    {
      label: 'English',
      value: 'en-US',
    },
  ],
};

/**
 * État réactif pour la langue sélectionnée
 */
const state = reactive({
  lang: null as string | null,
});

/**
 * Initialise la langue actuelle depuis i18n.locale
 * Appelée au montage du composant pour synchroniser l'affichage
 */
function init() {
  const locale = i18n.locale;
  state.lang = locale as string;
}

/**
 * Met à jour la langue de l'application via setLang()
 * Cette fonction persiste le choix de l'utilisateur
 * 
 * @param value - Code de la langue à activer (ex: 'fr', 'en-US')
 */
function setLangValue(value: string) {
  setLang(value);
}

// Initialiser la langue au montage
onMounted(() => {
  init();
});

// Surveiller les changements de langue et mettre à jour i18n
watch(
  () => state.lang,
  (val) => {
    if (val) {
      setLangValue(val);
    }
  }
);
</script>

<style lang="scss">
.popup-labels-de-emphasize {
  .q-item:not(.q-item--active) {
    color: var(--neutral-medium);
  }
}
</style>

