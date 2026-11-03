import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRecordEditor } from '@ui/modules/data/workspace/useRecordEditor'
import { equipmentSchema } from '@ui/modules/data/api/contracts'
import type { ProjectOut } from '@ui/generated/api/types.gen'

const { send } = vi.hoisted(() => ({ send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({
  mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send)
}))
const id = (n: number) => '00000000-0000-4000-8000-' + String(n).padStart(12, '0')
const project = (n: number): ProjectOut => ({ id: id(n), name: 'Project ' + n, target_name: null, notes: null, status: 'active',
  revision: 3, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
beforeEach(() => send.mockReset())
let wrapper:ReturnType<typeof mount>|undefined
afterEach(()=>{wrapper?.unmount();wrapper=undefined})
function createEditor(){
  let editor!:ReturnType<typeof useRecordEditor>
  wrapper=mount(defineComponent({setup(){editor=useRecordEditor('/one');return ()=>null}}))
  return editor
}

describe('typed record editing sessions', () => {
  it('creates and edits an equatorial mount without submitting specifications', async () => {
    const editor = createEditor()
    editor.equipment()
    const current = editor.model.value!
    if (current.kind !== 'equipment') throw new Error('Expected equipment session')
    editor.model.value = { ...current, draft: { ...current.draft, kind: 'mount', name: 'AP1100 GTO', specs: {} } }
    const record = equipmentSchema.parse({ id: id(30), kind: 'mount', name: 'AP1100 GTO', model: null, notes: null, status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
    send.mockResolvedValue(record)
    await editor.submit()
    expect(send.mock.calls[0][3]).toEqual({ kind: 'mount', name: 'AP1100 GTO', model: null, notes: null })
    editor.equipment(record)
    const edit = editor.model.value!
    if (edit.kind !== 'equipment') throw new Error('Expected equipment session')
    editor.model.value = { ...edit, draft: { ...edit.draft, notes: 'Remote observatory' } }
    send.mockResolvedValue({ ...record, notes: 'Remote observatory', revision: 2 })
    await editor.submit()
    expect(send.mock.calls[1][3]).toEqual({ kind: 'mount', base_revision: 1, notes: 'Remote observatory' })
  })
  it('ignores a stale draft update after the editor target changes', () => {
    const editor = createEditor()
    editor.project(project(1))
    const old = editor.model.value!
    if (old.kind !== 'project') throw new Error('Expected project session')
    editor.project(project(2))
    editor.model.value = { ...old, draft: { ...old.draft, name: 'Stale name' } }
    expect(editor.model.value?.id).toBe(id(2))
    expect(editor.model.value?.draft.name).toBe('Project 2')
    expect(editor.dirty.value).toBe(false)
    expect(editor.source.value?.revision).toBe(3)
  })

  it('submits only changed equipment fields and preserves untouched nullable specifications', async () => {
    const record = equipmentSchema.parse({ id: id(3), kind: 'camera', name: 'Camera', model: null, notes: null,
      specs: { pixel_size_um: 3.76 }, status: 'active', revision: 7, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
    if (record.kind !== 'camera') throw new Error('Expected camera fixture')
    send.mockResolvedValue({ ...record, name: 'Renamed', revision: 8 })
    const editor = createEditor()
    editor.equipment(record)
    const current = editor.model.value!
    if (current.kind !== 'equipment') throw new Error('Expected equipment session')
    editor.model.value = { ...current, draft: { ...current.draft, name: 'Renamed' } }
    expect(editor.dirty.value).toBe(true)
    await editor.submit()
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][3]).toEqual({ kind: 'camera', base_revision: 7, name: 'Renamed' })
    expect(record.name).toBe('Camera')
    expect(record.specs.pixel_size_um).toBe(3.76)
  })
  it('includes the telescope accessory list when creating a registered telescope', async () => {
    const accessory = { id: id(99), name: 'Reducer', factor: 0.8 }
    const editor = createEditor()
    editor.equipment()
    const current = editor.model.value!
    if (current.kind !== 'equipment') throw new Error('Expected equipment session')
    editor.model.value = { ...current, draft: { ...current.draft, kind: 'telescope', name: 'Scope', specs: { native_focal_length_mm: 480, optical_accessories: [accessory] } } }
    send.mockResolvedValue({ id: id(5), kind: 'telescope', name: 'Scope', model: null, notes: null, specs: { native_focal_length_mm: 480, optical_accessories: [accessory] }, status: 'active', revision: 1, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
    await editor.submit()
    expect(send.mock.calls[0][3]).toEqual({ kind: 'telescope', name: 'Scope', model: null, notes: null, specs: { native_focal_length_mm: 480, optical_accessories: [accessory] } })
  })

})
