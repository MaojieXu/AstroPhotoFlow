import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EquipmentSetupManager from '@ui/modules/data/equipment/EquipmentSetupManager.vue'
import { equipmentSetupSchema } from '@ui/modules/data/api/contracts'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({
  catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get),
  mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send)
}))
const rig = equipmentSetupSchema.parse({ id: '00000000-0000-4000-8000-000000000001', name: 'Saved rig', notes: null,
  status: 'active', revision: 1, components: [], created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
let wrapper: ReturnType<typeof mount<typeof EquipmentSetupManager>> | undefined
beforeEach(() => { get.mockReset().mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 }); send.mockReset() })
afterEach(() => { wrapper?.unmount(); wrapper = undefined })

async function open() {
  wrapper = mount(EquipmentSetupManager, {
    props: { workspace: '/one', recordsLoading: false, viewKey: 'one', changeToken: 0 },
    global: { stubs: { WorkspaceRecords: true } }
  })
  await flushPromises()
  wrapper.vm.beginSetup(null)
  await flushPromises()
  await wrapper.get('form[aria-label="设备组合表单"] input[required]').setValue('New rig')
}

describe('setup editor without a Workspace provider', () => {
  it('saves through the typed service and emits confirmed data with the original view identity', async () => {
    send.mockResolvedValue(rig)
    await open()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit')
    await flushPromises()
    expect(wrapper!.emitted('saved')).toEqual([[rig, 'one']])
    expect(wrapper!.emitted('dirty')).toContainEqual([true])
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('does not apply a late save after the view identity has changed', async () => {
    let finish!: (value: typeof rig) => void
    send.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    await open()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit')
    await flushPromises()
    await wrapper!.setProps({ viewKey: 'two' })
    finish(rig)
    await flushPromises()
    expect(wrapper!.emitted('saved')).toBeUndefined()
    expect(wrapper!.emitted('saving')?.at(-1)).toEqual([false])
  })

  it('does not show an old save failure in another workspace and never replays it', async () => {
    let reject!: (cause: Error) => void
    send.mockImplementation(() => new Promise((_resolve, fail) => { reject = fail }))
    await open()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit')
    await flushPromises()
    await wrapper!.setProps({ workspace: '/two' })
    reject(new Error('Old workspace outcome unknown'))
    await flushPromises()
    expect(wrapper!.text()).not.toContain('Old workspace outcome unknown')
    expect(wrapper!.emitted('saved')).toBeUndefined()
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('retains the submitted setup draft after an uncertain response and does not replay', async () => {
    send.mockRejectedValue(new Error('Save outcome unknown'))
    await open()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit')
    await flushPromises()
    expect(wrapper!.get<HTMLInputElement>('form[aria-label="设备组合表单"] input[required]').element.value).toBe('New rig')
    expect(wrapper!.text()).toContain('Save outcome unknown')
    expect(send).toHaveBeenCalledTimes(1)
  })
})
