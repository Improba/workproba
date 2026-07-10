<!--
  Composant MRange - Sélecteur de plage Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-range de Quasar qui applique le style Mastok
  et intègre le système de couleurs Anubis. Il permet de sélectionner une plage de valeurs
  avec deux poignées (min et max).
  
  Variantes de couleur disponibles :
  - primary (défaut) : Couleur primary
  - secondary, tertiary, light, danger, success, warning : Autres variantes
  
  Props :
  - modelValue : Objet { min: number, max: number } pour les valeurs min/max
  - label : Label à afficher au-dessus du sélecteur
  - lazy : Si true, n'émet l'événement qu'à la fin du glissement
  - disable : Désactive le composant
  - bind : Objet de props à passer à q-range (markers, min, max, step, etc.)
  - infophrase : Texte d'aide à afficher dans un tooltip
  - infophraseIcon : Icône pour le tooltip d'aide (défaut: 'mdi-help-circle')
  
  Événements :
  - update:modelValue : Émis lors du changement de valeur
  
  Utilisation :
  ```vue
  <MRange 
    v-model="range" 
    label="Plage de prix"
    :bind="{ min: 0, max: 1000, step: 10 }"
  />
  ```
-->
<template>
  <div class="row items-center">
    <label>
      {{ props.label }}
    </label>

    <q-icon class="q-ml-xs" v-if="props.infophrase" :name="props.infophraseIcon">
      <q-tooltip>
        <div v-html="props.infophrase" />
      </q-tooltip>
    </q-icon>

    <div class="col-12">
      <q-range
        v-model="state.modelValue"
        v-bind="{
          color: `${mastok.colorInfos.value.color.replace(/^bg-/, '')}`,
          disable,
          ...props.bind
        }"

        :label="!!props.bind?.label"

        :left-label-value="getLabelValue('min')"
        :right-label-value="getLabelValue('max')"

        @change="$emit('update:modelValue', state.modelValue)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { PropType, reactive, watch } from 'vue';
import { defaultMastokProps, useMastok } from './use-mastok';


const emit = defineEmits(['update:modelValue'])
const props = defineProps({
  ...defaultMastokProps,
  modelValue: {
    type: Object as PropType<{ min?: number|null, max?: number|null }>,
    default: () => {
      0
      10
    }
  },
  label: {
    type: String,
    default: null
  },
  lazy: {
    type: Boolean,
    default: null
  },
  disable: {
    type: Boolean,
    default: null
  },
  bind: {
    type: Object as PropType<any>,
    default: null
  },
  infophrase: {
    type: String,
    default: null
  },
  infophraseIcon: {
    type: String,
    default: 'mdi-help-circle'
  }
})

const state = reactive({
  modelValue: props.modelValue || 0
});

const mastok = useMastok(props)

const getLabelValue = (order: 'min'|'max') => {
  if (!props.bind?.markers) { return state.modelValue[order] || state.modelValue }
  return props.bind.customMarkers?.find((marker: any) => marker.value === state.modelValue[order])?.label
}

watch(
  () => props.modelValue,
  (v: any) => {
    if (JSON.stringify(props.modelValue) === JSON.stringify(state.modelValue)) { return }

    state.modelValue = Object.assign({}, props.modelValue)
  }
);

watch(
  () => state.modelValue,
  (v: any) => {
    if (!props.lazy) { emit('update:modelValue', v); return }
  }
)
</script>
