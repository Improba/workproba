<!--
  Composant MDialog - Dialogue modal Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-dialog de Quasar qui utilise MCard pour
  le contenu et applique le style Mastok. Il fournit une structure standardisée
  pour les modales avec titre, description, contenu et boutons d'action.
  
  Boutons d'action :
  - Confirm : Bouton de confirmation (affiché par défaut)
  - Cancel : Bouton d'annulation (optionnel)
  - Close : Bouton de fermeture (optionnel)
  
  Props :
  - modelValue : Contrôle l'ouverture/fermeture de la modale (v-model)
  - title : Titre de la modale
  - description : Description de la modale
  - width, height : Dimensions de la modale
  - row, column : Orientation du contenu (column par défaut)
  - align : Alignement vertical ('start', 'center', 'end')
  - justify : Justification horizontale ('start', 'center', 'end', 'between', 'around')
  - showConfirm, showCancel, showClose : Afficher/masquer les boutons
  - confirmBtnLabel, cancelBtnLabel, closeBtnLabel : Labels des boutons
  - delay : Délai en ms avant fermeture automatique (optionnel)
  
  Événements :
  - update:modelValue : Émis lors de la fermeture
  - confirm : Émis lors du clic sur le bouton de confirmation
  - cancel : Émis lors du clic sur le bouton d'annulation
  - close : Émis lors du clic sur le bouton de fermeture
  
  Utilisation :
  ```vue
  <MDialog v-model="showDialog" title="Confirmer" description="Êtes-vous sûr ?">
    <template #content>
      Contenu de la modale
    </template>
  </MDialog>
  ```
-->
<template>
  <q-dialog v-model="state.open">
    <MCard
      :title
      :description

      :class="`
        ${column && !row && 'column'}
        ${row && 'row'}

        justify-${justify}
        items-${align}
      `"
      :style="{ width, height }"
    >
      <template #actions>
        <q-card-actions>
            <template v-if="showConfirm">
              <slot name="btn:confirm">
                <MBtn :label="confirmBtnLabel" @click="methods.handleConfirm()" />
              </slot>
            </template>

            <template v-if="showCancel">
              <slot name="btn:cancel">
                <MBtn secondary outline :label="cancelBtnLabel" @click="methods.handleCancel()" />
              </slot>
            </template>

            <template v-if="showClose">
              <slot name="btn:close">
                <MBtn tertiary :label="closeBtnLabel" @click="methods.handleClose()" />
              </slot>
            </template>

          </q-card-actions>
      </template>
    </MCard>
  </q-dialog>
</template>

<script lang="ts">
import { defineComponent, onMounted, reactive, watch } from 'vue';

export default defineComponent({
  props: {
    modelValue: { type: Boolean },

    // <!-- _ CONTENT - TITLE / DESCRIPTION -->
    title: { type: String },
    description: { type: String },

    // <!-- _ COMPORTEMENT - CLOSE DELAY -->
    delay: { type: Number },

    // <!-- _ STYLE - WIDTH / HEIGHT -->
    width: { type: String },
    height: { type: String },

    // <!-- _ STYLE - ALIGNEMENT -->
    row: { type: Boolean, default: false },
    column: { type: Boolean, default: true },

    align: { type: String, default: 'start', enum: ['start', 'center', 'end'] },
    justify: { type: String, default: 'between', enum: ['start', 'center', 'end', 'between', 'around'] },

    // <!-- _ BTN - CONFIRM -->
    showConfirm: { type: Boolean, default: true },
    confirmBtnLabel: {
      type: String,
      default: 'Confirmer'
    },

    // <!-- _ BTN - CANCEL -->
    showCancel: { type: Boolean, default: false },
    cancelBtnLabel: {
      type: String,
      default: 'Annuler'
    },

    // <!-- _ BTN - CLOSE -->
    showClose: { type: Boolean, default: false },
    closeBtnLabel: {
      type: String,
      default: 'Fermer'
    },
  },
  emits: [
    'update:modelValue',
    'confirm',
    'cancel',
    'close'
  ],
  setup(props, { emit }) {

    const stateless = {
    };

    const state = reactive({
      open: props.modelValue
    });

    const methods = {
      handleConfirm() {
        emit('update:modelValue', false)
        emit('confirm')
      },
      handleCancel() {
        emit('update:modelValue', false)
        emit('cancel')
      },
      handleClose() {
        emit('update:modelValue', false)
        emit('close')
      },
    };

    const computedState = {
    };


    watch(
      () => props.modelValue,
      (modelValue: boolean) => {
        if (state.open !== modelValue) {
          state.open = modelValue
        }

        if (modelValue && props.delay) {
          setTimeout(() => {
            emit('update:modelValue', false)
          }, props.delay)
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
