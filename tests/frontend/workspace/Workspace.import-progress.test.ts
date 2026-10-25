import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@frontend/App.vue'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@frontend/assets/host-client', () => ({ assetApi: { get, send } }))
const capabilities = {
  stage: 'ingestion', shared_library_read: true, project_assets_read: true,
  project_management: true, equipment_management: true, capture_profile_management: true,
  asset_import: true, asset_reference_write: false, asset_preview: false,
  asset_metadata_edit: true, dataset_management: true, asset_task_management: true,
  calibration_matching: false, asset_publish: false
}
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const baseTask = {
  id: '00000000-0000-4000-8000-000000000001', status: 'running', sources: [], storage_mode: 'managed',
  classification: {}, parameters: {}, notes: null, dataset_name: 'M31', target_dataset_id: null,
  dataset_base_revision: null, dataset_id: null, enumeration_completed: true, retry_of_task_id: null,
  report: { registration: { total: 10, registered: 2, completed: false } }, error: null,
  created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:01Z',
  items: [], items_total: 10, items_completed: 9, items_limit: 20, items_offset: 0
}
let wrapper: ReturnType<typeof mount> | undefined
beforeEach(() => { get.mockReset(); send.mockReset(); vi.useFakeTimers() })
afterEach(() => { wrapper?.unmount(); wrapper=undefined; vi.useRealTimers() })

describe('workspace import registration progress', () => {
  it('uses registration counts in the actual row and refreshes on registration and background completion', async () => {
    let current = structuredClone(baseTask)
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/asset-tasks?')) return { ...emptyPage, items: [current], total: 1 }
      return emptyPage
    })
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.get('.apf-import-row progress').attributes('value')).toBe('20')
    expect(wrapper.get('.apf-import-row').text()).toContain('2 / 10 项已登记')
    const reads = () => get.mock.calls.filter(([path]) => String(path).includes('/library/items?')).length
    const before = reads()
    current = { ...current, report: { registration: { total: 10, registered: 10, completed: true } }, items_completed: 0 }
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
    expect(wrapper.find('.apf-import-row').exists()).toBe(false)
    expect(reads()).toBe(before + 1)
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
    expect(reads()).toBe(before + 1)
    current = { ...current, status: 'completed', items_completed: 10 }
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
    expect(reads()).toBe(before + 2)
    expect(get.mock.calls.filter(([path]) => String(path).includes('/asset-tasks?')).length).toBeGreaterThanOrEqual(4)
  })
})
