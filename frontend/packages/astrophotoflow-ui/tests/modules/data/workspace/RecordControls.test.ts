import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RecordsFeedback from '@ui/modules/data/workspace/RecordsFeedback.vue'
import RecordsPagination from '@ui/modules/data/workspace/RecordsPagination.vue'

describe('record controls without a Workspace provider', () => {
  it('keeps a read failure and request identity visible instead of showing an empty success state', () => {
    const wrapper = mount(RecordsFeedback, { props: { inlineError: '', librarySelecting: false, projectSelecting: false,
      notice: '', loading: false, readError: { message: 'Read failed', requestId: 'request-1' }, emptyMessage: 'No records' } })
    try {
      expect(wrapper.get('[role="alert"]').text()).toContain('Read failed')
      expect(wrapper.text()).toContain('request-1')
      expect(wrapper.text()).not.toContain('No records')
    } finally { wrapper.unmount() }
  })

  it('emits page deltas without changing the supplied offset and disables navigation while blocked', async () => {
    const wrapper = mount(RecordsPagination, { props: { total: 125, offset: 50, pageSize: 50, pageLength: 50,
      library: false, equipmentManagement: false, loading: false, error: false, blocked: false } })
    try {
      const buttons = wrapper.findAll('button')
      await buttons[0].trigger('click')
      await buttons[1].trigger('click')
      expect(wrapper.emitted('move')).toEqual([[-50], [50]])
      expect(wrapper.props('offset')).toBe(50)
      await wrapper.setProps({ blocked: true })
      expect(wrapper.findAll('button').every(button => button.attributes('disabled') !== undefined)).toBe(true)
    } finally { wrapper.unmount() }
  })

  it('delegates explicit all-mode selection and removes page controls when the parent applies it', async () => {
    const wrapper = mount(RecordsPagination, { props: { total: 80, offset: 0, pageSize: 20, pageLength: 20,
      library: false, equipmentManagement: false, loading: false, error: false, blocked: false } })
    try {
      await wrapper.get('select').setValue('all')
      expect(wrapper.emitted('page-size')).toEqual([['all']])
      await wrapper.setProps({ pageSize: 'all', pageLength: 80 })
      expect(wrapper.find('button').exists()).toBe(false)
    } finally { wrapper.unmount() }
  })

  it('only shows equipment paging when a complete visible result needs another page', async () => {
    const wrapper = mount(RecordsPagination, { props: { total: 50, offset: 0, pageSize: 50, pageLength: 50,
      library: false, equipmentManagement: true, loading: false, error: false, blocked: false } })
    try {
      expect(wrapper.find('footer').exists()).toBe(false)
      await wrapper.setProps({ total: 75 })
      expect(wrapper.find('footer').exists()).toBe(true)
      expect(wrapper.find('select').exists()).toBe(false)
      await wrapper.setProps({ error: true })
      expect(wrapper.find('footer').exists()).toBe(false)
    } finally { wrapper.unmount() }
  })
})
