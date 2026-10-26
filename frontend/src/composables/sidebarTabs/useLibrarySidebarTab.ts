import { markRaw } from 'vue'

import LibrarySidebarTab from '@/components/sidebar/tabs/LibrarySidebarTab.vue'
import type { SidebarTabExtension } from '@/types/extensionTypes'

export function useLibrarySidebarTab(): SidebarTabExtension {
  return {
    id: 'library',
    icon: 'icon-[lucide--images]',
    title: 'astrophotoflow.library',
    tooltip: 'astrophotoflow.library',
    label: 'astrophotoflow.library',
    component: markRaw(LibrarySidebarTab),
    type: 'vue'
  }
}
