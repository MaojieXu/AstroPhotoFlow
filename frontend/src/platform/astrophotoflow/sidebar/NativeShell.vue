<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { setActiveLocale } from '@/i18n'
import { getDefaultLocale } from '@/locales/localeConfig'
import { getWorkspaceLocale } from '@astrophotoflow/ui'
import { useToast } from '@/components/ui/toast/toastStore'
import { t } from '@/i18n'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useColorPaletteService } from '@/services/colorPaletteService'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'
import GraphView from '@/views/GraphView.vue'
import { useCanvasDataSession } from '../canvas/session'
import { useApp } from '@/scripts/appInstance'
import { registerDataReferenceDisplay } from '../canvas/dataReferenceDisplay'
import { registerSirilPreviewDisplay } from '../results/sirilPreviewDisplay'
import { registerBundleResultDisplay } from '../results/bundleDisplay'
import { useAutomaticResults } from '../results/automatic'

registerDataReferenceDisplay(useApp())
const disposeBundleDisplay = registerSirilPreviewDisplay(useApp())
if (disposeBundleDisplay) onBeforeUnmount(disposeBundleDisplay)
registerBundleResultDisplay(useApp())
useCanvasDataSession()
useAutomaticResults()

const settings = useSettingStore()
const paletteService = useColorPaletteService()
const sidebarTabs = useSidebarTabStore()
const route = useRoute()
const toast = useToast()
sidebarTabs.activeSidebarTabId = route.query.apf_panel === 'software' ? 'software' : 'library'

watch(() => route.query.apf_panel, (panel) => {
  if (panel === 'software') sidebarTabs.activeSidebarTabId = 'software'
})

onMounted(async () => {
  const palette = paletteService.getActiveColorPalette()
  paletteService.loadComfyColorPalette(
    palette.colors.comfy_base,
    palette.light_theme === true
  )
  try {
    await getWorkspaceLocale(fetch)
    await settings.load()
    const locale = await setActiveLocale(settings.get('Comfy.Locale') ?? getDefaultLocale())
    if (!settings.exists('Comfy.Locale') || settings.get('Comfy.Locale') !== locale) {
      await settings.set('Comfy.Locale', locale)
    }
  } catch (error) {
    toast.error(t('g.error'), { description: error instanceof Error ? error.message : String(error) })
  }
})
</script>

<template>
  <GraphView />
</template>
