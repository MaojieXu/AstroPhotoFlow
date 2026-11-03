import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import EquipmentSetupTable from '@ui/modules/data/equipment/EquipmentSetupTable.vue'
import { equipmentSchema, equipmentSetupSchema } from '@ui/modules/data/api/contracts'

const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
const timestamp = '2026-10-28T12:00:00Z'
const camera = equipmentSchema.parse({ id: id(1), kind: 'camera', name: 'Camera', model: null, notes: null, specs: {}, status: 'active', revision: 1, created_at: timestamp, updated_at: timestamp })
const setup = equipmentSetupSchema.parse({ id: id(2), name: 'Rig', notes: null, status: 'active', revision: 1,
  created_at: timestamp, updated_at: timestamp, components: [
    { id: id(3), source: 'registered', equipment_id: camera.id },
    { id: id(4), source: 'inline', equipment: { kind: 'filter', name: 'Ha', specs: {} } }
  ] })
const props = () => ({ setups: [setup], selectedId: setup.id, loading: false, equipment: [camera],
  equipmentReady: true, equipmentLoading: false, equipmentError: '', sort: { by: 'created_at' as const, order: 'desc' as const },
  blocked: false, selectMode: false, selectedIds: new Set<string>(), allSelected: false, partiallySelected: false })

describe('controlled setup table without a Workspace provider', () => {
  it('displays registered and inline mounts and emits mount sorting', async () => {
    const registered = equipmentSchema.parse({ id: id(30), kind: 'mount', name: 'AP1100 GTO', model: null, notes: null,
      status: 'active', revision: 1, created_at: timestamp, updated_at: timestamp })
    const rig = equipmentSetupSchema.parse({ ...setup, components: [{ id: id(31), source: 'registered', equipment_id: registered.id }] })
    const inline = equipmentSetupSchema.parse({ ...setup, id: id(40), name: 'Inline rig', components: [{ id: id(41), source: 'inline', equipment: { kind: 'mount', name: 'HAE69C' } }] })
    const wrapper = mount(EquipmentSetupTable, { props: { ...props(), setups: [rig, inline], equipment: [registered] } })
    try {
      expect(wrapper.text()).toContain('AP1100 GTO')
      expect(wrapper.text()).toContain('HAE69C')
      await wrapper.findAll('thead button').find(button => button.text() === '赤道仪')!.trigger('click')
      expect(wrapper.emitted('sort')).toEqual([['mount']])
    } finally { wrapper.unmount() }
  })
  it('renders both device sources and emits navigation and sorting requests', async () => {
    const wrapper = mount(EquipmentSetupTable, { props: props() })
    try {
      expect(wrapper.text()).toContain('Camera')
      expect(wrapper.text()).toContain('Ha')
      await wrapper.get('tbody tr').trigger('click')
      expect(wrapper.emitted('select')).toEqual([[setup.id]])
      await wrapper.get('thead button').trigger('click')
      expect(wrapper.emitted('sort')).toEqual([['name']])
      expect(wrapper.props('sort')).toEqual({ by: 'created_at', order: 'desc' })
    } finally { wrapper.unmount() }
  })

  it('emits selection intent without mutating the selected identity set', async () => {
    const selectedIds = new Set([setup.id])
    const wrapper = mount(EquipmentSetupTable, { props: { ...props(), selectMode: true, selectedIds, allSelected: true } })
    try {
      const boxes = wrapper.findAll('input[type="checkbox"]')
      await boxes[0].setValue(false)
      await boxes[1].setValue(false)
      expect(wrapper.emitted('toggle-page')).toEqual([[false]])
      expect(wrapper.emitted('toggle-row')).toEqual([[setup.id]])
      expect(selectedIds.has(setup.id)).toBe(true)
    } finally { wrapper.unmount() }
  })

  it('keeps unresolved registered devices visible as an error and delegates retry', async () => {
    const wrapper = mount(EquipmentSetupTable, { props: { ...props(), equipment: [], equipmentReady: false, equipmentError: 'metadata unavailable' } })
    try {
      expect(wrapper.get('[role="alert"]').text()).toContain('metadata unavailable')
      await wrapper.get('[role="alert"] button').trigger('click')
      expect(wrapper.emitted('retry-equipment')).toEqual([[]])
    } finally { wrapper.unmount() }
  })
})
