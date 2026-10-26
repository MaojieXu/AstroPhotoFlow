<script setup lang="ts">
import { defineAsyncComponent, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { onBeforeRouteUpdate, RouterLink, useRoute } from 'vue-router'

import { setActiveLocale } from '@/i18n'
import { getDefaultLocale } from '@/locales/localeConfig'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useColorPaletteService } from '@/services/colorPaletteService'

import Workspace from '../../../src/astrophotoflow/frontend/workspace/Workspace.vue'

const { page } = defineProps<{
  page: 'library' | 'workflows' | 'settings'
}>()
const { t } = useI18n()
const route = useRoute()
const workspace = ref<InstanceType<typeof Workspace>>()
const graphOpened = ref(page === 'workflows')
const GraphView = defineAsyncComponent(() => import('./GraphView.vue'))
const pages = ['library', 'workflows', 'settings'] as const
const settingStore = useSettingStore()
const paletteService = useColorPaletteService()

onBeforeRouteUpdate(async (to) => {
  const destination = to.params.page
  if (destination === 'workflows') return workspace.value!.leavePage()
  if (destination !== workspace.value!.activeArea) {
    return workspace.value!.selectArea(destination as 'library' | 'settings')
  }
  return true
})

onMounted(async () => {
  const palette = paletteService.getActiveColorPalette()
  paletteService.loadComfyColorPalette(
    palette.colors.comfy_base,
    palette.light_theme === true
  )
  await settingStore.load()
  await setActiveLocale(settingStore.get('Comfy.Locale') ?? getDefaultLocale())
  document.getElementById('splash-loader')?.remove()
  if (page === 'settings') await workspace.value!.selectArea('settings')
})

watch(
  () => page,
  async (value) => {
    if (value === 'workflows') {
      graphOpened.value = true
      await nextTick()
      window.dispatchEvent(new Event('resize'))
    }
  }
)
</script>

<template>
  <div
    class="flex h-dvh w-full flex-col overflow-hidden bg-base-background text-base-foreground"
  >
    <header
      class="z-40 flex h-14 shrink-0 items-center gap-8 border-b border-interface-stroke bg-comfy-menu-bg px-5"
    >
      <strong class="text-base font-semibold tracking-wide"
        >AstroPhotoFlow</strong
      >
      <nav
        class="flex h-full items-center gap-2"
        :aria-label="t('astrophotoflow.navigation')"
      >
        <RouterLink
          v-for="destination in pages"
          :key="destination"
          :to="{ path: '/' + destination, query: route.query }"
          class="rounded-md px-4 py-2 text-sm no-underline transition-colors hover:bg-comfy-menu-secondary-bg"
          :class="
            page === destination
              ? 'bg-comfy-menu-secondary-bg font-semibold text-base-foreground'
              : 'text-muted-foreground'
          "
          :aria-current="page === destination ? 'page' : undefined"
          >{{ t('astrophotoflow.' + destination) }}</RouterLink
        >
      </nav>
    </header>
    <main class="relative min-h-0 flex-1 overflow-hidden">
      <section v-show="page !== 'workflows'" class="h-full min-h-0">
        <Workspace ref="workspace" native />
      </section>
      <section
        v-if="graphOpened"
        v-show="page === 'workflows'"
        class="relative h-full min-h-0"
      >
        <GraphView />
      </section>
    </main>
  </div>
</template>
