import { markRaw } from 'vue'

import WorkbenchSidebarTab from './WorkbenchSidebarTab.vue'
import type { SidebarTabExtension } from '@/types/extensionTypes'

export function useWorkbenchSidebarTab(): SidebarTabExtension {
  return {
    id: 'workbench',
    icon: 'icon-[lucide--sliders-horizontal]',
    title: 'apfWorkbench.title',
    tooltip: 'apfWorkbench.title',
    label: 'apfWorkbench.title',
    component: markRaw(WorkbenchSidebarTab),
    type: 'vue'
  }
}
