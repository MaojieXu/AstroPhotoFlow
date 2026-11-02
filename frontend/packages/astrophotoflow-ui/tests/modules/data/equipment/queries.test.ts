import { flushPromises, mount } from '@vue/test-utils'
import { h, ref } from 'vue'
import { focusManager } from '@tanstack/vue-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useEquipmentChoices, useEquipmentManagementQuery } from '@ui/modules/data/equipment/queries'
import { equipmentSchema } from '@ui/modules/data/api/contracts'

const { get } = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({
  catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get)
}))

const device = (index: number) => equipmentSchema.parse({
  id: '00000000-0000-4000-8000-' + String(index).padStart(12, '0'),
  name: 'Camera ' + index, kind: 'camera', model: null, notes: null, specs: {}, status: 'active', revision: 1,
  created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z'
})
const page = (items: ReturnType<typeof device>[], total: number, offset = 0) =>
  ({ items, total, offset, limit: 200 })
let wrapper: ReturnType<typeof mount> | undefined
beforeEach(() => get.mockReset())
afterEach(() => { wrapper?.unmount(); wrapper = undefined; focusManager.setFocused(undefined); vi.useRealTimers() })

function open(workspace = ref('/one')) {
  wrapper = mount({ setup() {
    const query = useEquipmentChoices(workspace)
    return () => h('p', query.isError.value ? 'error' : query.data.value?.map(item => item.name).join(',') ?? 'loading')
  } })
  return workspace
}

describe('complete equipment choice catalog', () => {
  it('reads beyond 200 devices before publishing the complete selector catalog', async () => {
    get.mockResolvedValueOnce(page(Array.from({ length: 200 }, (_, i) => device(i)), 201))
      .mockResolvedValueOnce(page([device(200)], 201, 200))
    open()
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(get.mock.calls[1][0]).toContain('offset=200')
    expect(wrapper!.text()).toContain('Camera 0,')
    expect(wrapper!.text()).toContain('Camera 200')
  })

  it('reports a later page failure instead of adopting a partial catalog', async () => {
    get.mockResolvedValueOnce(page(Array.from({ length: 200 }, (_, i) => device(i)), 201))
      .mockRejectedValueOnce(new Error('The second page is unavailable'))
    open()
    await flushPromises()
    expect(wrapper!.text()).toBe('error')
    expect(wrapper!.text()).not.toContain('Camera 0')
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('cancels a pending page on workspace change and ignores the old complete result', async () => {
    let finish!: (value: ReturnType<typeof page>) => void
    get.mockResolvedValueOnce(page(Array.from({ length: 200 }, (_, i) => device(i)), 201))
      .mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
      .mockResolvedValue(page([device(900)], 1))
    const workspace = open()
    await flushPromises()
    expect(wrapper!.text()).toBe('loading')
    const oldSignal = get.mock.calls[1][2] as AbortSignal
    workspace.value = '/two'
    await flushPromises()
    expect(oldSignal.aborted).toBe(true)
    expect(wrapper!.text()).toBe('Camera 900')
    finish(page([device(200)], 201, 200))
    await flushPromises()
    expect(wrapper!.text()).toBe('Camera 900')
  })
  it('keeps management draft data stable during background polling and refreshes after editing ends', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    const paused = ref(false)
    get.mockResolvedValue({ ...page([device(1)], 1), limit: 50 })
    wrapper = mount({ setup() {
      const query = useEquipmentManagementQuery(() => ({ workspaceId: '/one', kind: 'equipment', query: { limit: 50, offset: 0 } }), paused)
      return () => h('p', query.data.value?.items.map(item => item.name).join(',') ?? 'loading')
    } })
    await flushPromises()
    expect(wrapper.text()).toBe('Camera 1')
    paused.value = true
    await flushPromises()
    get.mockResolvedValue({ ...page([device(2)], 1), limit: 50 })
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(wrapper.text()).toBe('Camera 1')
    expect(get).toHaveBeenCalledTimes(1)
    paused.value = false
    await flushPromises()
    expect(wrapper.text()).toBe('Camera 2')
    expect(get).toHaveBeenCalledTimes(2)
  })

})
