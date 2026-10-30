<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { setActiveLocale } from '@/i18n'
import { getDefaultLocale } from '@/locales/localeConfig'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useColorPaletteService } from '@/services/colorPaletteService'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'
import GraphView from '@/views/GraphView.vue'
import { useCanvasDataSession } from './useCanvasDataSession'
import { useApp } from '@/scripts/appInstance'
import { registerDataReferenceDisplay } from './dataReferenceDisplay'
import { registerSirilPreviewDisplay } from './sirilPreviewDisplay'
import { registerBundleResultDisplay } from './bundleResultDisplay'

registerDataReferenceDisplay(useApp())
const disposeBundleDisplay = registerSirilPreviewDisplay(useApp())
if (disposeBundleDisplay) onBeforeUnmount(disposeBundleDisplay)
registerBundleResultDisplay(useApp())
useCanvasDataSession()

const settings = useSettingStore()
const paletteService = useColorPaletteService()
const sidebarTabs = useSidebarTabStore()
const route = useRoute()
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
  await settings.load()
  await setActiveLocale(settings.get('Comfy.Locale') ?? getDefaultLocale())
})
</script>

<template>
  <GraphView />
</template>
