import { watch } from 'vue'

import { useJobHistorySidebarTab } from '@/composables/sidebarTabs/useJobHistorySidebarTab'
import { useNodeLibrarySidebarTab } from '@/composables/sidebarTabs/useNodeLibrarySidebarTab'
import {
  useLibrarySidebarTab,
  useProjectSidebarTab,
  useSoftwareSidebarTab
} from '@/platform/astrophotoflow'
import { useSettingStore } from '@/platform/settings/settingStore'
import { useWorkflowsSidebarTab } from '@/platform/workflow/management/composables/useWorkflowsSidebarTab'
import { useMenuItemStore } from '@/stores/menuItemStore'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

export function registerCoreSidebarTabs() {
  const sidebarTabStore = useSidebarTabStore()
  const settingStore = useSettingStore()
  const jobHistoryTabId = 'job-history'
  const syncJobHistoryTab = (enabled: boolean) => {
    const hasJobHistoryTab = sidebarTabStore.sidebarTabs.some(
      (tab) => tab.id === jobHistoryTabId
    )
    if (enabled && !hasJobHistoryTab) {
      sidebarTabStore.registerSidebarTab(useJobHistorySidebarTab(), {
        prepend: true
      })
    } else if (!enabled && hasJobHistoryTab) {
      sidebarTabStore.unregisterSidebarTab(jobHistoryTabId)
    }
  }

  syncJobHistoryTab(settingStore.get('Comfy.Queue.QPOV2'))
  watch(
    () => settingStore.get('Comfy.Queue.QPOV2'),
    (enabled) => syncJobHistoryTab(enabled)
  )

  sidebarTabStore.registerSidebarTab(useNodeLibrarySidebarTab())
  sidebarTabStore.registerSidebarTab(useLibrarySidebarTab())
  sidebarTabStore.registerSidebarTab(useProjectSidebarTab())
  sidebarTabStore.registerSidebarTab(useWorkflowsSidebarTab())
  sidebarTabStore.registerSidebarTab(useSoftwareSidebarTab())

  const menuStore = useMenuItemStore()

  menuStore.registerCommands(
    ['View'],
    [
      'Workspace.ToggleBottomPanel',
      'Comfy.BrowseTemplates',
      'Workspace.ToggleFocusMode',
      'Comfy.ToggleCanvasInfo',
      'Comfy.Canvas.ToggleMinimap',
      'Comfy.Canvas.ToggleLinkVisibility'
    ]
  )

  menuStore.registerCommands(
    ['View'],
    ['Comfy.Canvas.ZoomIn', 'Comfy.Canvas.ZoomOut', 'Comfy.Canvas.FitView']
  )
}
