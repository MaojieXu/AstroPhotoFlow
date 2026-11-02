import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import WorkspaceRecords from '@ui/modules/data/library/WorkspaceRecords.vue'
import type { RecordsPresentation } from '@ui/modules/data/workspace/recordsTypes'
import type { ProjectOut } from '@ui/generated/api/types.gen'

const view = (): RecordsPresentation => ({
  feedback: { inlineError: '', librarySelecting: false, projectSelecting: false, notice: '', loading: false, emptyMessage: 'No catalog entries' },
  body: { kind: 'none' },
  pagination: { total: 0, offset: 0, pageSize: 50, pageLength: 0, library: true, equipmentManagement: false, loading: false, error: false, blocked: false },
  previewUnavailable: false
})

describe('controlled record scenes without a Workspace provider', () => {
  it('renders an explicit empty scene and never needs root state', () => {
    const wrapper = mount(WorkspaceRecords, { props: { view: view() } })
    try {
      expect(wrapper.text()).toContain('No catalog entries')
      expect(wrapper.find('.apf-record').exists()).toBe(false)
    } finally { wrapper.unmount() }
  })

  it('binds only the selected scene component contract and delegates its event', async () => {
    const project: ProjectOut = { id: '00000000-0000-4000-8000-000000000001', name: 'M31', target_name: null,
      notes: null, status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' }
    const onSelect = vi.fn()
    const model = view()
    model.body = { kind: 'projects', props: { projects: [project], selectedIds: new Set(), selectMode: false,
      allSelected: false, partiallySelected: false, layout: 'list', onSelect } }
    model.feedback = { ...model.feedback, emptyMessage: undefined }
    const wrapper = mount(WorkspaceRecords, { props: { view: model } })
    try {
      await wrapper.get('.apf-record').trigger('click')
      expect(onSelect).toHaveBeenCalledExactlyOnceWith(project.id)
      expect(wrapper.find('table').exists()).toBe(false)
    } finally { wrapper.unmount() }
  })
})
