import { ref } from 'vue'
import { expect, it } from 'vitest'
import { useSetupEditor } from '@ui/modules/data/equipment/useSetupEditor'
import { equipmentInput } from '@ui/modules/data/equipment/drafts'
import {
  equipmentSetupSchema,
  equipmentSchema
} from '@ui/modules/data/api/contracts'

const id = (n: number) =>
  '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
const camera = equipmentSchema.parse({
  id: id(1),
  kind: 'camera',
  name: 'Camera',
  model: null,
  notes: null,
  specs: { pixel_size_um: 3.76 },
  status: 'active',
  revision: 1,
  created_at: '2026-10-28T12:00:00Z',
  updated_at: '2026-10-28T12:00:00Z'
})
const rig = equipmentSetupSchema.parse({
  id: id(2),
  name: 'Rig',
  notes: null,
  status: 'active',
  revision: 3,
  components: [
    { id: id(3), source: 'registered', equipment_id: camera.id },
    {
      id: id(4),
      source: 'inline',
      equipment: {
        kind: 'filter',
        name: 'Ha',
        model: null,
        notes: null,
        specs: { bandwidth_nm: 7 }
      }
    }
  ],
  created_at: '2026-10-28T12:00:00Z',
  updated_at: '2026-10-28T12:00:00Z'
})

it('edits a cloned setup draft while retaining member identity, order and source facts', () => {
  const equipment = ref([camera])
  const editor = useSetupEditor(equipment)
  editor.beginSetup(rig)
  editor.setRegistered('camera', [camera.id])
  editor.editInline(1)
  editor.deviceEditor.value!.equipment.name = 'Ha draft'
  editor.setupDraft.value.name = 'My draft'
  equipment.value = [{ ...camera, name: 'External rename', revision: 2 }]
  expect(
    editor.setupDraft.value.components.map((component) => component.id)
  ).toEqual([id(3), id(4)])
  expect(editor.setupDraft.value.name).toBe('My draft')
  expect(rig.name).toBe('Rig')
  expect(
    rig.components[1].source === 'inline' && rig.components[1].equipment.name
  ).toBe('Ha')
  expect(editor.dirty.value).toBe(true)
  editor.reset()
  expect(editor.dirty.value).toBe(false)
})

it('counts registered and inline hardware together and only repairs duplicates after an explicit selection', () => {
  const editor = useSetupEditor(ref([camera]))
  editor.beginSetup(rig)
  editor.setupDraft.value.components.push({ source: 'inline', equipment: { kind: 'camera', name: 'Inline camera', specs: {} } })
  expect(editor.invalidCounts.value).toBe(true)
  expect(editor.setupDraft.value.components).toHaveLength(3)
  editor.setSingle('camera', camera.id)
  expect(editor.invalidCounts.value).toBe(false)
  expect(editor.setupDraft.value.components.map(item => item.id)).toEqual([id(3), id(4)])
  editor.setSingle('camera', '')
  expect(editor.count('camera')).toBe(0)
  expect(editor.count('filter')).toBe(1)
})

it('rejects changing an inline device to an already occupied hardware slot', () => {
  const editor = useSetupEditor(ref([camera]))
  editor.beginSetup(rig)
  expect(editor.applyInline(1, { kind: 'camera', name: 'Second camera', specs: {} })).toBe(false)
  expect(editor.componentKind(editor.setupDraft.value.components[1])).toBe('filter')
})

it('replaces a telescope explicitly without carrying its old accessory selection', () => {
  const telescope = equipmentSchema.parse({ ...camera, id: id(7), kind: 'telescope', specs: {} })
  const replacement = equipmentSchema.parse({ ...telescope, id: id(8), name: 'Replacement' })
  const editor = useSetupEditor(ref([camera, telescope, replacement]))
  editor.beginSetup(rig)
  editor.setupDraft.value.components.push({ id: id(9), source: 'registered', equipment_id: telescope.id, optical_accessory_id: id(10) })
  editor.addRegistered('telescope', replacement.id)
  const selected = editor.setupDraft.value.components.find(item => editor.componentKind(item) === 'telescope')
  expect(editor.count('telescope')).toBe(1)
  expect(selected?.optical_accessory_id).toBeNull()
  expect(selected?.source === 'registered' && selected.equipment_id).toBe(replacement.id)
})

it('keeps a single mount across registered and inline sources and preserves other members', () => {
  const mount = equipmentSchema.parse({ id: id(30), kind: 'mount', name: 'AP1100 GTO', model: null, notes: null,
    status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
  const editor = useSetupEditor(ref([camera, mount]))
  editor.beginSetup(rig)
  editor.setupDraft.value.components.push({ id: id(31), source: 'registered', equipment_id: mount.id })
  expect(editor.applyInline(1, { kind: 'mount', name: 'Second mount', specs: {} })).toBe(false)
  editor.setupDraft.value.components.push({ source: 'inline', equipment: { kind: 'mount', name: 'Inline mount', specs: {} } })
  expect(editor.invalidCounts.value).toBe(true)
  editor.setSingle('mount', mount.id)
  expect(editor.invalidCounts.value).toBe(false)
  expect(editor.setupDraft.value.components.map(item => item.id)).toEqual([id(3), id(4), id(31)])
  editor.setSingle('mount', '')
  expect(editor.setupDraft.value.components.map(item => item.id)).toEqual([id(3), id(4)])
  expect(equipmentInput({ kind: 'mount', name: 'Inline mount', specs: {} })).toEqual({ kind: 'mount', name: 'Inline mount' })
})
