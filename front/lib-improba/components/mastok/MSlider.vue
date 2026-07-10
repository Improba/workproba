<!--
  Composant MSlider - Curseur Mastok avec intégration Anubis
  
  Ce composant est un wrapper autour de q-slider de Quasar qui applique le style Mastok
  et intègre le système de couleurs Anubis. Il permet de sélectionner une valeur unique
  dans une plage donnée.
  
  Variantes de couleur disponibles :
  - primary (défaut) : Couleur primary
  - secondary, tertiary, light, danger, success, warning : Autres variantes
  
  Props :
  - modelValue : Valeur numérique du curseur
  - label : Label à afficher au-dessus du curseur
  - lazy : Si true, n'émet l'événement qu'à la fin du glissement
  - disable : Désactive le composant
  - bind : Objet de props à passer à q-slider (markers, min, max, step, etc.)
  - infophrase : Texte d'aide à afficher dans un tooltip
  - infophraseIcon : Icône pour le tooltip d'aide (défaut: 'mdi-help-circle')
  
  Événements :
  - update:modelValue : Émis lors du changement de valeur
  
  Utilisation :
  ```vue
  <MSlider 
    v-model="value" 
    label="Volume"
    :bind="{ min: 0, max: 100, step: 1 }"
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
      <q-slider
        v-if="!props.lazy"
        v-model="state.modelValue"
        v-bind="{
          color: `${mastok.colorInfos.value.color.replace(/^bg-/, '')}`,
          disable,
          ...props.bind
        }"
        :label="!!props.bind?.label"
      />
      <q-slider
        v-else

        :model-value="state.modelValue"
        @change="(val: number) => state.modelValue = val"
        v-bind="{
          color: `${mastok.colorInfos.value.color.replace(/^bg-/, '')}`,
          disable,
          ...props.bind
        }"
        :label="!!props.bind?.label"
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
    type: Number,
    default: null
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

watch(
  () => state.modelValue,
  (v: any) => {
    if (v === props.modelValue) { return }
    emit('update:modelValue', v)
  }
)

watch(
  () => props.modelValue,
  (v: any) => {
    if (v === state.modelValue) { return }
    state.modelValue = v
  }
)
</script>
