<template>
  <section class="locked-setup">
    <div class="locked-setup__banner">
      <Lucide name="lock" size="20" color="text-muted" />
      <p>
        Votre administrateur a verrouillé la configuration du modèle.
        Contactez votre service informatique.
      </p>
    </div>
    <button type="button" class="locked-setup__request" @click="onRequestAccess">
      Demander l'accès
    </button>
    <p v-if="requestMessage" class="locked-setup__feedback">
      {{ requestMessage }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Lucide from '@lib-improba/components/mastok/Lucide.vue';

const requestMessage = ref('');

function onRequestAccess(): void {
  requestMessage.value =
    'Demande enregistrée localement (placeholder). Votre administrateur sera notifié dans une prochaine version.';
}
</script>

<style scoped lang="scss">
.locked-setup {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 0;
}

.locked-setup__banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface-2);
  color: var(--wp-text-muted);
  font-size: 14px;

  p {
    margin: 0;
    line-height: 1.45;
  }
}

.locked-setup__request {
  align-self: flex-start;
  padding: 8px 14px;
  border: 1px solid var(--wp-border);
  border-radius: var(--wp-r-md);
  background: var(--wp-surface);
  color: var(--wp-text);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    background: var(--wp-surface-2);
  }
}

.locked-setup__feedback {
  margin: 0;
  font-size: 13px;
  color: var(--wp-text-muted);
}
</style>
