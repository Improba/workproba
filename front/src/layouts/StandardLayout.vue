<!--
  @deprecated Legacy Quasar layout — non utilisé par le shell desktop Workproba.
  Conservé temporairement pour les tests unitaires layouts.spec.ts.
-->
<template>
  <q-layout class="bg-neutral-lower" view="hHh lpR fff">
    <q-header>
      <q-toolbar class="bg-neutral-higher text-neutral-lowest">
        <q-tabs class="full-width">
          <q-route-tab no-caps style="flex: none">
            <div
              class="full-height text-bold row items-center justify-center layout-logo"
              :class="`${$q.screen?.lt.sm ? 'text-h6' : 'text-h4'}`"
              @click="$router.push({ name: HOME_ROUTE })"
            >
              {{ i18n.t('shell.brandName') }}
            </div>
          </q-route-tab>

          <q-space />

          <MBtnDropdown light>
            <q-list>
              <q-item
                v-for="item in userMenuItems"
                :key="item.label(i18n)"
                clickable
                v-close-popup
                class="row justify-center"
              >
                <theme-toggler v-if="item.name === 'theme'" />
              </q-item>
            </q-list>
          </MBtnDropdown>
        </q-tabs>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <slot><router-view /></slot>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { userMenuItems } from './menu.items';
import { useI18n } from 'vue-i18n';
import ThemeToggler from '@lib-improba/components/layouts/theme-toggler/ThemeToggler.vue';
import { HOME_ROUTE } from '@router/meta';

const router = useRouter();
const i18n = useI18n();

void router;
</script>

<style scoped lang="scss">
.layout-logo {
  cursor: pointer;
}
</style>
