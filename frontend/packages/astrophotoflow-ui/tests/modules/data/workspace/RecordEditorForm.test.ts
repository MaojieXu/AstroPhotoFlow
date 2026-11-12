import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import RecordEditorForm from '@ui/modules/data/workspace/RecordEditorForm.vue'
import type { RecordEditorState } from '@ui/modules/data/workspace/editorTypes'

describe('controlled record editor without a Workspace provider', () => {
  it('emits project draft changes and leaves the supplied object unchanged', async () => {
    const model: RecordEditorState = { kind: 'project', draft: { name: '', target_name: null, notes: null } }
    const saveField = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(RecordEditorForm, { props: { modelValue: model, saving: false, savingInline: 0, inlineError: '', saveField } })
    try {
      await wrapper.get('#project-name').setValue('M31')
      const updated = wrapper.emitted('update:modelValue')?.at(-1)?.[0] as RecordEditorState
      expect(updated.draft.name).toBe('M31')
      expect(model.draft.name).toBe('')
      await wrapper.setProps({ modelValue: updated })
      await wrapper.get('form').trigger('submit')
      expect(wrapper.emitted('submit')).toEqual([[]])
      expect(saveField).not.toHaveBeenCalled()
    } finally { wrapper.unmount() }
  })

  it('emits equipment specifications without mutating the parent draft', async () => {
    const model: RecordEditorState = { kind: 'equipment', draft: { kind: 'camera', name: 'Camera', specs: {} } }
    const wrapper = mount(RecordEditorForm, { props: { modelValue: model, saving: false, savingInline: 0, inlineError: '', saveField: vi.fn().mockResolvedValue(undefined) } })
    try {
      await wrapper.findAll('input[type="number"]')[2].setValue('3.76')
      const updated = wrapper.emitted('update:modelValue')?.at(-1)?.[0] as RecordEditorState
      expect(updated.kind).toBe('equipment')
      if (updated.kind !== 'equipment') throw new Error('Expected the equipment editor')
      expect(updated.draft.specs.pixel_size_um).toBe(3.76)
      expect(model.draft.specs.pixel_size_um).toBeUndefined()
    } finally { wrapper.unmount() }
  })

  it('shows only identity fields for an equatorial mount', () => {
    const model: RecordEditorState = { kind: 'equipment', draft: { kind: 'mount', name: 'AP1100 GTO', specs: {} } }
    const wrapper = mount(RecordEditorForm, { props: { modelValue: model, saving: false, savingInline: 0, inlineError: '', saveField: vi.fn() } })
    try {
      expect(wrapper.get('select[aria-label="设备类型"]').element).toHaveProperty('value', 'mount')
      expect(wrapper.find('input[type="number"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('设备参数')
      expect(wrapper.text()).not.toContain('光学附件')
      expect(wrapper.get('input[aria-label="名称"]').element).toHaveProperty('value', 'AP1100 GTO')
    } finally { wrapper.unmount() }
  })
})
