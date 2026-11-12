import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ProjectDetails from '@ui/modules/data/projects/ProjectDetails.vue'
import type { ProjectOut } from '@ui/generated/api/types.gen'

const project: ProjectOut = { id: '00000000-0000-4000-8000-000000000001', name: 'M31', target_name: null, notes: null,
  status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' }

describe('project details without a Workspace provider', () => {
  it('delegates actions with the displayed project identity and respects archive blocking', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ProjectDetails, { props: { project, blocked: false, saveName: save, saveTarget: save, saveNotes: save } })
    try {
      await wrapper.findAll('button').find(button => button.text() === '移入回收站')!.trigger('click')
      expect(wrapper.emitted('action')).toEqual([['archive', project.id]])
      await wrapper.setProps({ project: { ...project, status: 'archived' }, blocked: true })
      const restore = wrapper.findAll('button').find(button => button.text() === '恢复')!
      expect(restore.attributes('disabled')).toBeDefined()
    } finally { wrapper.unmount() }
  })

  it('preserves an active draft and its original save binding across a background revision change', async () => {
    const originalSave = vi.fn().mockRejectedValue(new Error('Revision changed'))
    const newerSave = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ProjectDetails, { props: { project, blocked: false, saveName: originalSave, saveTarget: newerSave, saveNotes: newerSave } })
    try {
      await wrapper.get('.apf-detail-fields .apf-inline-value').trigger('dblclick')
      await flushPromises()
      await wrapper.get('input').setValue('My retained draft')
      await wrapper.setProps({ project: { ...project, name: 'Remote name', revision: 2 }, saveName: newerSave })
      expect((wrapper.get('input').element as HTMLInputElement).value).toBe('My retained draft')
      await wrapper.get('input').trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(originalSave).toHaveBeenCalledExactlyOnceWith('My retained draft')
      expect(newerSave).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('Revision changed')
      expect((wrapper.get('input').element as HTMLInputElement).value).toBe('My retained draft')
    } finally { wrapper.unmount() }
  })
})
