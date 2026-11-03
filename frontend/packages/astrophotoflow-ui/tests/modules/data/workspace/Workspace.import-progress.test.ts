import { libraryAsset, libraryDataset } from '../../../fixtures/library-summary'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), assetApi: { get, send } }))
const capabilities = {
  stage: 'ingestion', shared_library_read: true, project_assets_read: true,
  project_management: true, equipment_management: true, asset_import: true, asset_reference_write: false, asset_preview: false,
  asset_metadata_edit: true, dataset_management: true, asset_task_management: true,
  calibration_matching: false, asset_publish: false
}
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const baseTask = {
  id: '00000000-0000-4000-8000-000000000001', status: 'running', dataset_name: 'M31', target_dataset_id: null,
  dataset_id: null, enumeration_completed: true,
  report: { registration: { total: 10, registered: 2, completed: false } }, error: null,
  created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:01Z',
  items_total: 10, items_completed: 9
}
let wrapper: ReturnType<typeof mount> | undefined
beforeEach(() => { localStorage.clear(); get.mockReset(); send.mockReset(); vi.useFakeTimers() })
afterEach(() => { wrapper?.unmount(); wrapper=undefined; vi.useRealTimers(); localStorage.clear() })

describe('workspace import registration progress', () => {
  it('keeps material processing issues while suppressing historical task banners', async () => {
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/health')) return {status:'ok',api_version:'v1',database:'ready',schema_revision:'0001',workspace:'/isolated-test-workspace'}
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/asset-tasks?')) return { ...emptyPage, items: [{ ...baseTask, status: 'completed_with_errors', error: null, report: {} }], total: 1 }
      if (path.includes('/library/items?')) return { ...emptyPage, total: 1, items: [{...libraryAsset({
        id: baseTask.id, name: 'invalid.fit', scope: 'shared', owner_project_id: null, role: 'raw', calibration_level: null,
        current_version_id: null, classification: {}, parameters: {}, equipment_snapshot: {}, value_sources: {}, notes: null,
        status: 'active', revision: 1, created_at: baseTask.created_at, current_version: null
      }), import_issue: '解析失败；预览不可用'}] }
      return emptyPage
    })
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.get('.apf-processing-issue').text()).toContain('解析失败')
    expect(wrapper.get('button[aria-label="invalid.fit处理状态说明"]').attributes('title')).toContain('预览不可用')
    expect(wrapper.get('.apf-processing-issue').text()).toContain('解析失败')
    expect(send).not.toHaveBeenCalled()
    expect(wrapper.find('.apf-import-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('关闭汇总')
    expect(wrapper.findComponent(Workspace).emitted('notify-success')).toBeUndefined()
  })

  it('uses registration counts in the actual row and refreshes on registration and background completion', async () => {
    let current = structuredClone(baseTask)
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/health')) return {status:'ok',api_version:'v1',database:'ready',schema_revision:'0001',workspace:'/isolated-test-workspace'}
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/asset-tasks?')) return { ...emptyPage, items: [current], total: 1 }
      return emptyPage
    })
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.get('.apf-import-progress progress').attributes('value')).toBeUndefined()
    expect(wrapper.get('.apf-import-progress').text()).toContain('2/10 项已登记')
    const reads = () => get.mock.calls.filter(([path]) => String(path).includes('/library/items?')).length
    const before = reads()
    current = { ...current, report: { registration: { total: 10, registered: 10, completed: true } }, items_completed: 0 }
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
    expect(wrapper.get('.apf-import-progress').text()).toContain('10/10 项已登记')
    expect(reads()).toBeGreaterThanOrEqual(before + 1)
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
    expect(reads()).toBeGreaterThanOrEqual(before + 1)
    current = { ...current, status: 'completed', items_completed: 10 }
    await vi.advanceTimersByTimeAsync(1500)
    await flushPromises()
    expect(reads()).toBeGreaterThanOrEqual(before + 2)
    expect(wrapper.find('.apf-import-progress').exists()).toBe(false)
    expect(wrapper.findComponent(Workspace).emitted('notify-success')).toEqual([['M31：导入完成']])
    expect(wrapper.find('.apf-assets-table .apf-import-progress').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('关闭汇总')
    expect(get.mock.calls.filter(([path]) => String(path).includes('/asset-tasks?')).length).toBeGreaterThanOrEqual(4)
  })
})
