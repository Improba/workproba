<!--
  Composant MInput - Input stylisé Mastok
  
  Ce composant est un wrapper autour de q-input de Quasar avec un style Mastok.
  Il peut être utilisé pour tous les cas d'usage nécessitant un input stylisé.
  
  Fonctionnalités :
  - Support des types text, search, password
  - Affichage conditionnel d'une icône de recherche ou de visibilité pour les mots de passe
  - Style Mastok avec classes Anubis
  - Support des règles de validation Quasar
  - Personnalisation des classes CSS via la prop classes
  
  Utilisation :
  <template>
    <MInput
      v-model="searchQuery"
      type="search"
      placeholder="Rechercher..."
    />
    
    <MInput
      v-model="email"
      label="Email"
      type="text"
      placeholder="exemple@email.com"
      :rules="[val => !!val || 'Email requis']"
    />
    
    <MInput
      v-model="password"
      label="Mot de passe"
      type="password"
      placeholder="Entrez votre mot de passe"
    />
    
    <MInput
      v-model="value"
      :classes="{
        container: 'custom-container',
        input: 'custom-input-class',
        label: 'custom-label-class'
      }"
    />
  </template>
  
  <script setup lang="ts">
  import { MInput } from '@lib-improba/components/mastok';
  import { ref } from 'vue';
  
  const searchQuery = ref('');
  const email = ref('');
  const password = ref('');
  const value = ref('');
  </script>
-->
<template>
  <div :class="classes?.container">
    <span v-if="label" :class="['text-neutral-text-primary medium-small', classes?.label]">
      {{ label }}
    </span>
    <q-input
      :model-value="modelValue"
      @update:model-value="$emit('update:modelValue', $event)"

      :class="['q-pa-none', 'custom-input', classes?.input]"
      :type="computedType"
      :placeholder
      :autocomplete
      dense
      square
      outlined
      clearable
      no-error-icon
      :rules="rules"
    >
      <template v-slot:append>
        <q-icon
          v-if="type === 'password'"
          :name="showPassword ? 'mdi-eye-outline' : 'mdi-eye-closed'"
          class="cursor-pointer"
          color="neutral-bg-primary"
          @click="showPassword = !showPassword"
        />
        <q-icon v-if="type === 'search'" name="search" />
      </template>
    </q-input>
  </div>
</template>

<script setup lang="ts">
import { QInputType } from 'quasar';
import { computed, ref } from 'vue';

/**
 * Props du composant MInput
 */
interface Props {
  /** Valeur du modèle (v-model) */
  modelValue?: string | null;
  
  /** Label affiché au-dessus de l'input */
  label?: string;
  
  /** Type d'input : 'text', 'search', 'password', etc. */
  type?: string;
  
  /** Placeholder text */
  placeholder?: string;
  
  /** Règles de validation Quasar */
  rules?: any;
  
  /** Attribut autocomplete HTML */
  autocomplete?: string;
  
  /** Classes CSS personnalisées pour personnaliser le style */
  classes?: {
    container?: string;
    input?: string;
    label?: string;
  };
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  placeholder: '',
  autocomplete: 'off',
  rules: [],
});

defineEmits(['update:modelValue']);

const showPassword = ref(false);

const computedType = computed(() => {
  if (props.type === 'password') {
    return showPassword.value ? 'text' : 'password';
  }
  return <QInputType>props.type;
});
</script>

