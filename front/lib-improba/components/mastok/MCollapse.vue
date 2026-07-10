<template>
  <MCard
    class="bg-transparent overflow-hidden"
    style="height: fit-content;"
    :style="{
      pointerEvents: collapsed ? 'none' : 'all'
    }"
  >
    <div
      class="smooth-slower"
      style="display: grid;"
      :style="{
        gridTemplateRows: fluid && collapsed ? '0fr' : '1fr',
        transitionDelay: !collapsed ? '0s' : collapseDelay,
      }"
    >
      <div
        class="smooth-slower overflow-hidden"
        :style="{
          transform: `translateY(${ collapsed ? '-100%' : '0'})`,
          transitionDelay: !collapsed ? collapseDelay : '0s',
        }"
      >
        <slot />
      </div>
    </div>
  </MCard>
  <div />
</template>

<script setup lang="ts">
import MCard from './MCard.vue';

// const emit = defineEmits(['update:collapsed'])
const props = defineProps({
  collapsed: Boolean,

  /** hide the native height of the element */
  fluid: Boolean,

  /** if fluid, delay between the collapse and the native height collapse */
  collapseDelay: {
    type: String,
    default: '0s'
  }
})
</script>
