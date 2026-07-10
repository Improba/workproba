<!--
  Composant MToggle - Interrupteur Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-toggle de Quasar qui applique le style Mastok
  et intègre le système de couleurs Anubis. Il fournit un interrupteur personnalisé
  avec des styles spécifiques (taille, transitions, etc.).
  
  Variantes de couleur disponibles :
  - primary (défaut) : Couleur primary
  - secondary, tertiary, light, danger, success, warning : Autres variantes
  
  Props :
  - modelValue : Valeur booléenne (true/false)
  - disable : Désactive le composant
  - keepColor : Conserve la couleur même quand désactivé (défaut: true)
  - secondary, tertiary, light, danger, success, warning : Variantes de couleur
  - flat : Style plat
  - lucideIcon : Nom de l'icône Lucide (non utilisé dans ce composant)
  
  Événements :
  - update:model-value : Émis lors du changement de valeur
  
  Utilisation :
  ```vue
  <MToggle v-model="enabled" primary />
  <MToggle v-model="active" success label="Activer" />
  ```
  
  Note : Le composant a un style personnalisé avec des dimensions et transitions spécifiques.
-->
<template>
  <q-toggle
    v-model="state.modelValue"
    v-bind="{
      color: mastok.colorInfos.value.color.replace(/^bg-/, ''),
      keepColor,
      disable
    }"
    class="toggle"
  >
    <!-- @vue-ignore -->
    <template v-for="([slotKey], index) in Object.entries($slots)" :key="index" v-slot:[slotKey]="scope">
      <slot v-if="$slots[slotKey]" :name="slotKey" v-bind="{ ...scope }" />
    </template>
  </q-toggle>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import { defaultMastokProps, useMastok } from './use-mastok';

const emit = defineEmits(['update:model-value'])
const props = defineProps({
  ...defaultMastokProps,
  modelValue: {
    type: Boolean
  },
  disable: {
    type: Boolean
  },
  keepColor: {
    type: Boolean,
    default: true,
  },
});

const state = reactive({
  modelValue: props.modelValue as boolean | null
})

watch(
  () => state.modelValue,
  (v: boolean | null) => {
    if (props.modelValue === v) { return }
    emit('update:model-value', v)
  }
)

watch(
  () => props.modelValue,
  (v: boolean | null) => {
    if (state.modelValue === v) { return }
    state.modelValue = v
  }
)

const mastok = useMastok(props)
</script>

<style scoped lang="scss">
.toggle {
  :deep(.q-toggle__inner) {
    height: fit-content;
    width: fit-content;
  }

  :deep(.q-toggle__track) {
    height: 20px;
    width: 40px;

    border-radius: 20px;

    cursor: pointer;

    transition: 0.2s ease-in-out;
  }

  :deep(.q-toggle__thumb) {
    height: 17px;
    width: 17px;

    border-radius: 50%;
    transition: 0.2s ease-in-out;

    transform: translateY(26%) translateX(33%) !important;

    &:after {
      box-shadow: none;
    }
  }

  &[aria-checked='true'] {
    :deep(.q-toggle__thumb) {
      transform: translateY(26%) translateX(40%) !important;
    }
  }

  &[aria-checked='false'] {
    :deep(.q-toggle__thumb) {
      transform: translateY(26%) translateX(20%) !important;
    }
  }
}
</style>
