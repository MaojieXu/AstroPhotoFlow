import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EquipmentFields from '@ui/modules/data/equipment/EquipmentFields.vue'
import type { EquipmentDraft } from '@ui/modules/data/equipment/drafts'

describe('equipment fields without a Workspace provider', () => {
  it('accepts a freely typed channel without a channel select and retains the optional bandwidth', async () => {
    const wrapper = mount(EquipmentFields, { props: { modelValue: { name: 'Filter', kind: 'filter', specs: { bandwidth_nm: 7 } } } })
    try {
      expect(wrapper.find('select[aria-label="Channel（通道）"]').exists()).toBe(false)
      await wrapper.get('input[aria-label="Channel（通道）"]').setValue('Ha + OIII')
      const updated = wrapper.emitted('update:modelValue')?.at(-1)?.[0] as EquipmentDraft
      expect(updated.specs).toEqual({ channel: 'Ha + OIII', bandwidth_nm: 7 })
    } finally { wrapper.unmount() }
  })
  it('edits numeric specifications and preserves an explicit clear', async () => {
    const draft: EquipmentDraft = { name: 'Camera', kind: 'camera', specs: {} }
    const wrapper = mount(EquipmentFields, { props: { modelValue: draft } })
    try {
      const pixelSize = wrapper.findAll('input[type="number"]')[2]
      await pixelSize.setValue('3.76')
      await flushPromises()
      const updated = wrapper.emitted('update:modelValue')?.at(-1)?.[0] as EquipmentDraft
      expect(updated.specs.pixel_size_um).toBe(3.76)
      expect(draft.specs.pixel_size_um).toBeUndefined()
      await wrapper.setProps({modelValue:updated})
      await pixelSize.setValue('')
      expect((wrapper.emitted('update:modelValue')?.at(-1)?.[0] as EquipmentDraft).specs.pixel_size_um).toBeNull()
    } finally {
      wrapper.unmount()
    }
  })
  it('uses pixel arrangement as the camera choice without serial or sensor mode fields', async () => {
    const wrapper = mount(EquipmentFields, { props: { modelValue: { name: 'Camera', kind: 'camera', specs: {} }, kindEditable: true } })
    try {
      expect(wrapper.text()).toContain('像素排列')
      expect(wrapper.text()).not.toContain('序列号')
      expect(wrapper.text()).not.toContain('传感器类型')
      const arrangement = wrapper.find('select[aria-label="像素排列"]')
      await arrangement.setValue('MONO')
      const updated = wrapper.emitted('update:modelValue')?.at(-1)?.[0] as EquipmentDraft
      expect(updated.specs.cfa_pattern).toBe('MONO')
      expect(updated.specs).not.toHaveProperty('sensor_mode')
    } finally { wrapper.unmount() }
  })

  it('keeps telescope accessories editable without an aperture or serial field', async () => {
    const wrapper = mount(EquipmentFields, { props: { modelValue: { name: 'Scope', kind: 'telescope', specs: { native_focal_length_mm: 480, optical_accessories: [] } } } })
    try {
      expect(wrapper.text()).not.toContain('口径')
      expect(wrapper.text()).not.toContain('序列号')
      await wrapper.findAll('button').find(button => button.text() === '添加附件')!.trigger('click')
      const updated = wrapper.emitted('update:modelValue')?.at(-1)?.[0] as EquipmentDraft
      expect(updated.specs.native_focal_length_mm).toBe(480)
      expect(updated.specs.optical_accessories).toEqual([expect.objectContaining({ id: expect.any(String), name: '', factor: 1 })])
    } finally { wrapper.unmount() }
  })

})
