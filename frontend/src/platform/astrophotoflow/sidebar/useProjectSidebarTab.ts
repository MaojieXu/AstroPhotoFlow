import { markRaw } from 'vue'
import type { SidebarTabExtension } from '@/types/extensionTypes'
import ProjectSidebarTab from './ProjectSidebarTab.vue'

export function useProjectSidebarTab(): SidebarTabExtension {
  return {
    id: 'projects',
    icon: 'icon-[lucide--folder-open]',
    title: 'apfUi.project',
    tooltip: 'apfUi.project',
    label: 'apfUi.project',
    component: markRaw(ProjectSidebarTab),
    type: 'vue'
  }
}
