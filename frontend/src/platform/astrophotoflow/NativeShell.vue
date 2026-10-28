<script setup lang="ts">
import { onMounted } from 'vue'

import { setActiveLocale } from '@/i18n'
import { getDefaultLocale } from '@/locales/localeConfig'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useColorPaletteService } from '@/services/colorPaletteService'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'
import GraphView from '@/views/GraphView.vue'

const settings = useSettingStore()
const paletteService = useColorPaletteService()
useSidebarTabStore().activeSidebarTabId = 'library'

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
