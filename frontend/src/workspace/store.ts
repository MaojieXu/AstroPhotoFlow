import { defineStore } from 'pinia'

export type WorkspaceSection = 'library' | 'calibration' | 'projects' | 'equipment' | 'capture-profiles'
export type WorkspacePageSize = 10 | 20 | 50 | 'all'

export const useWorkspaceStore = defineStore('astrophotoflow-workspace', {
  state: () => ({
    section: 'library' as WorkspaceSection,
    layout: 'grid' as 'grid' | 'list',
    query: '',
    offset: 0,
    pageSize: 50 as WorkspacePageSize,
    activeProjectId: null as string | null,
    activeProjectRevision: null as number | null
  }),
  actions: {
    selectSection(section: WorkspaceSection) {
      this.section = section
      this.offset = 0
    },
    setQuery(query: string) {
      this.query = query
      this.offset = 0
    },
    movePage(delta: number) {
      this.offset = Math.max(0, this.offset + delta)
    },
    setPageSize(pageSize: WorkspacePageSize) {
      this.pageSize = pageSize
      this.offset = 0
    }
  }
})
