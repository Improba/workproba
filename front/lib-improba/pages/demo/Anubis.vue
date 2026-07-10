<script setup lang="ts">
import { copyToClipboard } from 'quasar';
</script>

<template>
  <div class="flex flex-center q-ma-xl">
    <div class="row q-gutter-md q-mb-md">
      <MCard @click="copyToClipboard('primary-lowest')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-primary-lowest" style="width: 100px; height: 100px;">lowest</MCard>
      <MCard @click="copyToClipboard('primary-lower')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-primary-lower" style="width: 100px; height: 100px;">lower</MCard>
      <MCard @click="copyToClipboard('primary-low')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-primary-low" style="width: 100px; height: 100px;">low</MCard>
      <MCard @click="copyToClipboard('primary')" class="flex flex-center clickable smooth text-neutral hover:border-primary border-neutral-highest-xs bg-primary text-neutral-lowest" style="width: 100px; height: 100px;">primary</MCard>
      <MCard @click="copyToClipboard('primary-high')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-primary-high" style="width: 100px; height: 100px;">high</MCard>
      <MCard @click="copyToClipboard('primary-higher')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-primary-higher" style="width: 100px; height: 100px;">higher</MCard>
      <MCard @click="copyToClipboard('primary-highest')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-primary-highest" style="width: 100px; height: 100px;">highest</MCard>
    </div>
    <div class="row q-gutter-md q-mb-md">
      <MCard @click="copyToClipboard('secondary-lowest')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-secondary-lowest" style="width: 100px; height: 100px;">lowest</MCard>
      <MCard @click="copyToClipboard('secondary-lower')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-secondary-lower" style="width: 100px; height: 100px;">lower</MCard>
      <MCard @click="copyToClipboard('secondary-low')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-secondary-low" style="width: 100px; height: 100px;">low</MCard>
      <MCard @click="copyToClipboard('secondary')" class="flex flex-center clickable smooth text-neutral hover:border-primary border-neutral-highest-xs bg-secondary text-neutral-lowest" style="width: 100px; height: 100px;">secondary</MCard>
      <MCard @click="copyToClipboard('secondary-high')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-secondary-high" style="width: 100px; height: 100px;">high</MCard>
      <MCard @click="copyToClipboard('secondary-higher')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-secondary-higher" style="width: 100px; height: 100px;">higher</MCard>
      <MCard @click="copyToClipboard('secondary-highest')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-secondary-highest" style="width: 100px; height: 100px;">highest</MCard>
    </div>
    <div class="row q-gutter-md q-mb-md">
      <MCard @click="copyToClipboard('neutral-lowest')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-neutral-lowest" style="width: 100px; height: 100px;">lowest</MCard>
      <MCard @click="copyToClipboard('neutral-lower')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-neutral-lower" style="width: 100px; height: 100px;">lower</MCard>
      <MCard @click="copyToClipboard('neutral-low')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-neutral-low" style="width: 100px; height: 100px;">low</MCard>
      <MCard @click="copyToClipboard('neutral')" class="flex flex-center clickable smooth text-neutral hover:border-primary border-neutral-highest-xs bg-neutral text-neutral-lowest" style="width: 100px; height: 100px;">neutral</MCard>
      <MCard @click="copyToClipboard('neutral-high')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-neutral-high" style="width: 100px; height: 100px;">high</MCard>
      <MCard @click="copyToClipboard('neutral-higher')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-neutral-higher" style="width: 100px; height: 100px;">higher</MCard>
      <MCard @click="copyToClipboard('neutral-highest')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-neutral-highest" style="width: 100px; height: 100px;">highest</MCard>
    </div>
    <div class="row q-gutter-md q-mb-md">
      <MCard @click="copyToClipboard('success-lowest')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-success-lowest" style="width: 100px; height: 100px;">lowest</MCard>
      <MCard @click="copyToClipboard('success-lower')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-success-lower" style="width: 100px; height: 100px;">lower</MCard>
      <MCard @click="copyToClipboard('success-low')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-success-low" style="width: 100px; height: 100px;">low</MCard>
      <MCard @click="copyToClipboard('success')" class="flex flex-center clickable smooth text-neutral hover:border-primary border-neutral-highest-xs bg-success text-neutral-lowest" style="width: 100px; height: 100px;">success</MCard>
      <MCard @click="copyToClipboard('success-high')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-success-high" style="width: 100px; height: 100px;">high</MCard>
      <MCard @click="copyToClipboard('success-higher')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-success-higher" style="width: 100px; height: 100px;">higher</MCard>
      <MCard @click="copyToClipboard('success-highest')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-success-highest" style="width: 100px; height: 100px;">highest</MCard>
    </div>
    <div class="row q-gutter-md q-mb-md">
      <MCard @click="copyToClipboard('warning-lowest')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-warning-lowest" style="width: 100px; height: 100px;">lowest</MCard>
      <MCard @click="copyToClipboard('warning-lower')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-warning-lower" style="width: 100px; height: 100px;">lower</MCard>
      <MCard @click="copyToClipboard('warning-low')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-warning-low" style="width: 100px; height: 100px;">low</MCard>
      <MCard @click="copyToClipboard('warning')" class="flex flex-center clickable smooth text-neutral hover:border-primary border-neutral-highest-xs bg-warning text-neutral-lowest" style="width: 100px; height: 100px;">warning</MCard>
      <MCard @click="copyToClipboard('warning-high')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-warning-high" style="width: 100px; height: 100px;">high</MCard>
      <MCard @click="copyToClipboard('warning-higher')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-warning-higher" style="width: 100px; height: 100px;">higher</MCard>
      <MCard @click="copyToClipboard('warning-highest')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-warning-highest" style="width: 100px; height: 100px;">highest</MCard>
    </div>
    <div class="row q-gutter-md q-mb-md">
      <MCard @click="copyToClipboard('danger-lowest')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-danger-lowest" style="width: 100px; height: 100px;">lowest</MCard>
      <MCard @click="copyToClipboard('danger-lower')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-danger-lower" style="width: 100px; height: 100px;">lower</MCard>
      <MCard @click="copyToClipboard('danger-low')" class="flex flex-center clickable smooth text-neutral-high hover:border-primary border-neutral-highest-xs bg-danger-low" style="width: 100px; height: 100px;">low</MCard>
      <MCard @click="copyToClipboard('danger')" class="flex flex-center clickable smooth text-neutral hover:border-primary border-neutral-highest-xs bg-danger text-neutral-lowest" style="width: 100px; height: 100px;">danger</MCard>
      <MCard @click="copyToClipboard('danger-high')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-danger-high" style="width: 100px; height: 100px;">high</MCard>
      <MCard @click="copyToClipboard('danger-higher')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-danger-higher" style="width: 100px; height: 100px;">higher</MCard>
      <MCard @click="copyToClipboard('danger-highest')" class="flex flex-center clickable smooth text-neutral-low hover:border-primary border-neutral-highest-xs bg-danger-highest" style="width: 100px; height: 100px;">highest</MCard>
    </div>
  </div>
</template>
