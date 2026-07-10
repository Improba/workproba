<!--
  Composant MCard - Carte Mastok avec intégration Anubis

  Ce composant est un wrapper autour de q-card de Quasar qui applique le style Mastok
  et utilise les classes typographiques Anubis. Il fournit une structure standardisée
  pour les cartes avec titre, description et contenu.

  Slots disponibles :
  - default : Contenu principal de la carte (remplace le contenu par défaut)
  - header : En-tête personnalisé (remplace titre + description)
  - title : Titre personnalisé
  - description : Description personnalisée
  - content : Contenu de la carte
  - actions : Actions en bas de la carte (boutons, etc.)

  Props :
  - title : Titre de la carte (affiché dans le slot title par défaut)
  - description : Description de la carte (affichée dans le slot description par défaut)

  Utilisation :
  ```vue
  <MCard title="Mon titre" description="Ma description">
    <template #content>
      Contenu de la carte
    </template>
    <template #actions>
      <MBtn primary>Action</MBtn>
    </template>
  </MCard>
  ```
-->
<template>
  <q-card style="min-width: fit-content !important;" class="shadow-none">
    <slot>
      <q-card-section>
        <div class="column justify-between">
          <slot name="header">
            <span class="title-font text-h4 font-weight-600">
              <slot name="title">
                {{ title }}
              </slot>
            </span>

            <span class="body-font text-neutral-higher" style="font-size: 18px;">
              <slot name="description">
                {{ description }}
              </slot>
            </span>
          </slot>
        </div>
      </q-card-section>

      <slot name="content" />

      <slot name="actions">
        <!-- <q-card-actions /> -->
      </slot>
    </slot>
  </q-card>
</template>

<script lang="ts">
import { defineComponent, onMounted, reactive, watch } from 'vue';

export default defineComponent({
  props: {
    modelValue: { type: Boolean },

    // <!-- _ CONTENT - TITLE / DESCRIPTION -->
    title: { type: String },
    description: { type: String }
  },
  emits: [],
  setup(props) {

    const stateless = {
    };

    const state = reactive({
    });

    const methods = {
    };

    const computedState = {
    };


    watch(
      () => state,
      (v: any) => {
        if (v) {
          // do something
        }
      }
    );

    onMounted(() => {
    });

    return {
      props,
      stateless,
      state,
      methods,
      computedState
    };
  },
});
</script>
