import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EquipmentCards from '@ui/modules/data/equipment/EquipmentCards.vue'
import { equipmentSchema } from '@ui/modules/data/api/contracts'

const device = equipmentSchema.parse({ id: '00000000-0000-4000-8000-000000000001', kind: 'camera', name: 'Camera', model: 'Model A',
  notes: null, specs: {}, status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
const props = () => ({ equipment: [device], selectedId: device.id, selectedIds: new Set<string>(), selectMode: false,
  allSelected: false, partiallySelected: false, blocked: false, loading: false, layout: 'list' as const })

describe('equipment cards without a Workspace provider', () => {
  it('renders typed device details and delegates select and edit by stable identity', async () => {
    const wrapper = mount(EquipmentCards, { props: props() })
    try {
      expect(wrapper.text()).toContain('Model A')
      await wrapper.get('.apf-record').trigger('click')
      await wrapper.get('.apf-equipment-edit-slot button').trigger('click')
      expect(wrapper.emitted('select')).toEqual([[device.id]])
      expect(wrapper.emitted('edit')).toEqual([[device.id]])
    } finally { wrapper.unmount() }
  })

  it('emits selection intent while preserving the parent identity set', async () => {
    const selectedIds = new Set([device.id])
    const wrapper = mount(EquipmentCards, { props: { ...props(), selectMode: true, selectedIds } })
    try {
      await wrapper.findAll('input[type="checkbox"]')[1].setValue(false)
      expect(wrapper.emitted('toggle-row')).toEqual([[device.id]])
      expect(selectedIds.has(device.id)).toBe(true)
      expect(wrapper.get('.apf-record').attributes('disabled')).toBeDefined()
    } finally { wrapper.unmount() }
  })
})
