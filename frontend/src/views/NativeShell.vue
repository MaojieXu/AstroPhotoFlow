<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  nextTick,
  onMounted,
  ref,
  watch
} from 'vue'
import { useI18n } from 'vue-i18n'
import {
  onBeforeRouteUpdate,
  RouterLink,
  useRoute,
  useRouter
} from 'vue-router'

import SideToolbar from '@/components/sidebar/SideToolbar.vue'
import { useAppMode } from '@/composables/useAppMode'
import config from '@/config'
import { setActiveLocale } from '@/i18n'
import { getDefaultLocale } from '@/locales/localeConfig'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import { useColorPaletteService } from '@/services/colorPaletteService'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

import Workspace from '@astrophotoflow/workspace/Workspace.vue'

const { page } = defineProps<{
  page: 'library' | 'workflows' | 'equipment'
}>()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const workspace = ref<InstanceType<typeof Workspace>>()
const graphOpened = ref(page === 'workflows')
const graphReady = ref(false)
const GraphView = defineAsyncComponent(() => import('./GraphView.vue'))
const pages = ['library', 'workflows'] as const
const activePage = computed(() => (page === 'equipment' ? 'library' : page))
const settingStore = useSettingStore()
const paletteService = useColorPaletteService()
const sidebarTabs = useSidebarTabStore()
const canvasStore = useCanvasStore()
const coreWorkspace = useWorkspaceStore()
const { isBuilderMode } = useAppMode()

onBeforeRouteUpdate(async (to) => {
  const destination = to.params.page
  if (destination === 'workflows') return workspace.value!.leavePage()
  const area = destination === 'equipment' ? 'settings' : 'library'
  if (area !== workspace.value!.activeArea) {
    return workspace.value!.selectArea(area, 'equipment')
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
  if (page === 'equipment')
    await workspace.value!.selectArea('settings', 'equipment')
})

watch(
  () => page,
  async (value) => {
    if (value === 'workflows') {
      graphOpened.value = true
      sidebarTabs.activeSidebarTabId = 'workflows'
      await nextTick()
      window.dispatchEvent(new Event('resize'))
    }
  },
  { immediate: true }
)
</script>

<template>
  <div
    class="flex h-dvh w-full overflow-hidden bg-base-background text-base-foreground"
  >
    <aside
      class="z-40 flex w-16 shrink-0 flex-col items-center border-r border-interface-stroke bg-comfy-menu-bg"
    >
      <RouterLink
        :to="{ path: '/library', query: route.query }"
        :aria-label="config.app_title"
        :title="config.app_title"
        class="flex h-14 w-full shrink-0 items-center justify-center text-base-foreground no-underline"
      >
        <i class="icon-[lucide--orbit] size-6" aria-hidden="true" />
      </RouterLink>
      <nav
        class="flex w-full shrink-0 flex-col gap-1 p-1"
        :aria-label="t('astrophotoflow.navigation')"
        data-testid="native-navigation"
      >
        <RouterLink
          v-for="destination in pages"
          :key="destination"
          :to="{ path: '/' + destination, query: route.query }"
          class="flex min-h-14 flex-col items-center justify-center gap-1 rounded-md px-1 py-2 text-xs no-underline hover:bg-(--comfy-menu-secondary-bg)"
          :class="
            activePage === destination
              ? 'bg-(--comfy-menu-secondary-bg) font-semibold text-base-foreground'
              : 'text-muted-foreground'
          "
          :aria-current="activePage === destination ? 'page' : undefined"
          @click="
            page === 'workflows' &&
            destination === 'workflows' &&
            sidebarTabs.toggleSidebarTab('workflows')
          "
        >
          <i
            :class="
              destination === 'library'
                ? 'icon-[lucide--images] size-5'
                : 'icon-[lucide--workflow] size-5'
            "
            aria-hidden="true"
          />
          <span>{{ t('astrophotoflow.' + destination) }}</span>
        </RouterLink>
      </nav>
      <SideToolbar
        v-if="graphReady"
        v-show="
          page === 'workflows' &&
          !canvasStore.linearMode &&
          !isBuilderMode &&
          !coreWorkspace.focusMode &&
          settingStore.get('Comfy.UseNewMenu') !== 'Disabled'
        "
        force-connected
        :visible-tab-ids="['job-history', 'node-library']"
        class="min-h-0 flex-1"
      />
    </aside>
    <main class="relative min-h-0 min-w-0 flex-1 overflow-hidden">
      <section v-show="page !== 'workflows'" class="h-full min-h-0">
        <Workspace
          ref="workspace"
          native
          @manage-equipment="
            router.push({ path: '/equipment', query: route.query })
          "
          @back-to-library="
            router.push({ path: '/library', query: route.query })
          "
        />
      </section>
      <section
        v-if="graphOpened"
        v-show="page === 'workflows'"
        class="relative h-full min-h-0"
      >
        <GraphView @ready="graphReady = true" />
      </section>
    </main>
  </div>
</template>
