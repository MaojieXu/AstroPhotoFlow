import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProjectCards from '@ui/modules/data/projects/ProjectCards.vue'
import DatasetReferenceTable from '@ui/modules/data/datasets/DatasetReferenceTable.vue'
import FixedDatasetMembers from '@ui/modules/data/datasets/FixedDatasetMembers.vue'
import type { ProjectOut } from '@ui/generated/api/types.gen'
import type { DatasetReferenceRow } from '@ui/modules/data/datasets/DatasetReferenceTable.vue'

const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')

describe('project and dataset views without a Workspace provider', () => {
  it('selects projects and emits selection intent without changing the supplied set', async () => {
    const project: ProjectOut = { id: id(1), name: 'M31', target_name: 'Andromeda', notes: null, status: 'active', revision: 1,
      created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' }
    const selectedIds = new Set([project.id])
    const wrapper = mount(ProjectCards, { props: { projects: [project], selectedId: project.id, selectedIds,
      selectMode: false, allSelected: true, partiallySelected: false, layout: 'list' } })
    try {
      expect(wrapper.text()).toContain('Andromeda')
      await wrapper.get('.apf-record').trigger('click')
      expect(wrapper.emitted('select')).toEqual([[project.id]])
      await wrapper.setProps({ selectMode: true })
      await wrapper.get('.apf-management-record-select input').setValue(false)
      expect(wrapper.emitted('toggle-row')).toEqual([[project.id]])
      expect(selectedIds.has(project.id)).toBe(true)
    } finally { wrapper.unmount() }
  })

  it('keeps the reference, dataset and fixed version identities distinct for preview and member access', async () => {
    const row: DatasetReferenceRow = { recordId: id(2), datasetId: id(3), versionId: id(4), title: 'Fixed group',
      projectFixed: true, classification: 'mixed', count: 52, memberCount: 52, camera: 'Camera', parameters: 'Gain 0',
      exposure: '60 s', temperature: '-10 °C', opticalSystem: 'Telescope', filter: 'Ha', storage: 'Managed', status: 'Active', notes: '—' }
    const wrapper = mount(DatasetReferenceTable, { props: { workspaceId:'/test-workspace', rows: [row], selectedId: row.recordId },
      global: { stubs: { FixedDatasetMembers: true } } })
    try {
      expect(wrapper.getComponent(FixedDatasetMembers).props()).toMatchObject({ datasetId: id(3), versionId: id(4), count: 52 })
      await wrapper.get('.apf-thumb').trigger('click')
      expect(wrapper.emitted('preview')).toEqual([[id(2)]])
      expect(wrapper.emitted('select')).toBeUndefined()
      await wrapper.get('tbody tr').trigger('click')
      expect(wrapper.emitted('select')).toEqual([[id(2)]])
    } finally { wrapper.unmount() }
  })
})
