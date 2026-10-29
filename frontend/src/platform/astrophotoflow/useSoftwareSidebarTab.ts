import { markRaw } from 'vue'

import SoftwareSidebarTab from './SoftwareSidebarTab.vue'
import type { SidebarTabExtension } from '@/types/extensionTypes'

export function useSoftwareSidebarTab(): SidebarTabExtension {
  return {
    id: 'software',
    icon: 'icon-[lucide--package-check]',
    title: 'apfSoftware.title',
    tooltip: 'apfSoftware.title',
    label: 'apfSoftware.title',
    component: markRaw(SoftwareSidebarTab),
    type: 'vue'
  }
}
