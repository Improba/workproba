<template>
  <div class="column q-ma-xl">
    <template
      v-for="component in stateless.components"
      :key="component"
    >
    <div class="q-my-sm">
      <span class="q-my-sm text-h3">
        <MBtn lucide-icon="ChevronDown" flat dense @click="state.collapse[component] = !state.collapse[component]" />
        {{ component }}
      </span>
      <MCollapse fluid collapse-delay="0.2s" :collapsed="state.collapse[component]">
        <div class="row q-gutter-md q-mb-md">
          <component
            :is="component"
            v-for="color in stateless.colors"
            :key="color.label"
            v-bind="color"
            class="col-grow"
          />
        </div>
      </MCollapse>
    </div>
    </template>

    <!-- _ MSLIDER -->
    <div class="q-my-sm">
      <span class="q-my-sm text-h3">
        <MBtn lucide-icon="ChevronDown" flat dense @click="state.collapse['MSlider'] = !state.collapse['MSlider']" />
        MSlider
      </span>
      <MCollapse fluid collapse-delay="0.2s" :collapsed="state.collapse['MSlider']">
        <div class="row q-gutter-md q-mb-md">
          <MSlider
            v-for="color in stateless.colors"
            :key="color.label"
            v-bind="color"
            v-model="state.slider"
            class="col-grow"
          />
        </div>
      </MCollapse>
    </div>

    <!-- _ MRANGE (LAZY) -->
    <div class="q-my-sm">
      <span class="q-my-sm text-h3">
        <MBtn lucide-icon="ChevronDown" flat dense @click="state.collapse['MRange'] = !state.collapse['MRange']" />
        MRange (lazy)
      </span>
      <MCollapse fluid collapse-delay="0.2s" :collapsed="state.collapse['MRange']">
        <div class="row q-gutter-md q-mb-md">
          <MRange
            v-for="color in stateless.colors"
            :key="color.label"
            v-bind="color"
            v-model="state.range"
            lazy
            class="col-grow"
          />
        </div>
      </MCollapse>
    </div>

    <!-- _ MTOGGLE <MBTN DENSE FLAT LIGHT SIZE="SM" LUCIDE-ICON="ROTATECCW" @CLICK="STATE.TOGGLE = NULL" /> -->
    <div class="q-my-sm">
      <span class="q-my-sm text-h3">
        <MBtn lucide-icon="ChevronDown" flat dense @click="state.collapse['MToggle'] = !state.collapse['MToggle']" />
        MToggle <MBtn dense flat light size="sm" lucide-icon="RotateCcw" @click="state.toggle = null" />
      </span>
      <MCollapse fluid collapse-delay="0.2s" :collapsed="state.collapse['MToggle']">
        <div class="row q-gutter-md q-mb-md">
          <MToggle
            v-for="color in stateless.colors"
            :key="color.label"
            v-bind="color"
            v-model="state.toggle"
            class="col-grow"
          />
        </div>
      </MCollapse>
    </div>
  </div>
</template>


<script setup lang="ts">
import { reactive } from 'vue';

const stateless = {
  components: [
    'MBtn', 'MBtnDropdown', 'MChip'
  ],
  colors: [
    { label: 'Primary' },
    { label: 'Secondary', secondary: true },
    { label: 'Tertiary', tertiary: true },
    { label: 'Success', success: true },
    { label: 'Danger', danger: true },
    { label: 'Warning', warning: true },
    { label: 'Light', light: true },
  ]
};

const state = reactive({
  collapse: {
    MBtn: false,
    MBtnDropdown: false,
    MChip: false,
    MSlider: false,
    MRange: false,
    MToggle: false,
  } as any,
  toggle: true as boolean | null,
  slider: 50,
  range: {
    min: 20,
    max: 70
  }
})
</script>
