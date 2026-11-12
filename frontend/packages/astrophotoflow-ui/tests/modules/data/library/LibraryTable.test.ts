import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import LibraryTable from '@ui/modules/data/library/LibraryTable.vue'

describe('library table without a Workspace provider', () => {
  it('renders explicit columns and delegates sorting without modifying its input', async () => {
    const sort = { by: 'name', order: 'asc' as const }
    const wrapper = mount(LibraryTable, { props: { rows: [], library: true, viewMode: 'detail', sortable: true,
      sort, selectMode: false, selectionAllowed: true, deleting: false, allSelected: false, partiallySelected: false } })
    try {
      expect(wrapper.text()).toContain('累计曝光')
      expect(wrapper.text()).not.toContain('apfUi.total_exposure')
      await wrapper.get('.apf-sort-button').trigger('click')
      expect(wrapper.emitted('sort')).toEqual([['name']])
      expect(sort).toEqual({ by: 'name', order: 'asc' })
    } finally { wrapper.unmount() }
  })
})
