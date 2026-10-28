<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { WorkbenchSettings, createWorkbenchClient } from '@astrophotoflow/ui'

import { setActiveLocale } from '@/i18n'
import { getDefaultLocale } from '@/locales/localeConfig'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useColorPaletteService } from '@/services/colorPaletteService'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'
import GraphView from '@/views/GraphView.vue'

const settings = useSettingStore()
const { t } = useI18n()
const settingsDialog = ref<HTMLDialogElement>()
const settingsOpen = ref(false)
const workbenchClient = createWorkbenchClient((path, init) => fetch(path, init))
const paletteService = useColorPaletteService()
useSidebarTabStore().activeSidebarTabId = 'library'

function openWorkbenchSettings() {
  settingsOpen.value = true
  settingsDialog.value?.showModal()
}

onMounted(async () => {
  const palette = paletteService.getActiveColorPalette()
  paletteService.loadComfyColorPalette(
    palette.colors.comfy_base,
    palette.light_theme === true
  )
  await settings.load()
  await setActiveLocale(settings.get('Comfy.Locale') ?? getDefaultLocale())
})
</script>

<template>
  <GraphView />
  <button
    type="button"
    data-testid="workbench-settings-button"
    class="fixed top-1 right-16 z-[1002] rounded-lg border border-current/20 bg-base-background px-4 py-2 text-base-foreground shadow-lg hover:bg-interface-panel-hover-surface"
    @click="openWorkbenchSettings"
  >
    {{ t('apfWorkbench.title') }}
  </button>
  <dialog
    ref="settingsDialog"
    :aria-label="t('apfWorkbench.title')"
    class="m-auto max-h-[90vh] w-[min(800px,94vw)] overflow-y-auto rounded-xl border border-current/20 bg-base-background p-6 text-base-foreground shadow-2xl backdrop:bg-black/50"
    @close="settingsOpen = false"
  >
    <button
      type="button"
      :aria-label="t('g.close')"
      class="absolute top-3 right-3 rounded px-3 py-2 hover:bg-interface-panel-hover-surface"
      @click="settingsDialog?.close()"
    >
      ×
    </button>
    <WorkbenchSettings
      v-if="settingsOpen"
      :client="workbenchClient"
      :translate="t"
    />
  </dialog>
</template>
