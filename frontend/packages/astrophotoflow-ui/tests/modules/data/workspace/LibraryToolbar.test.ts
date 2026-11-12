import { assetFixture } from '../../../fixtures/library-members'
import { libraryAsset, libraryDataset } from '../../../fixtures/library-summary'
import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import LibraryMenu from '@ui/modules/data/components/LibraryMenu.vue'
import { assetSchema } from '@ui/modules/data/api/contracts'
import { useWorkspaceStore } from '@ui/modules/data/workspace/store'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), assetApi: { get, send } }))
const timestamp = '2026-10-28T12:00:00Z'
const asset = assetSchema.parse(assetFixture({
                                  id: '00000000-0000-4000-8000-000000000001',
                                  name: 'M31.fit',
                                  scope: 'shared',
                                  owner_project_id: null,
                                  role: 'raw',
                                  calibration_level: null,
                                  classification: { frame_class: 'subframe', frame_type: 'light' },
                                  parameters: {},
                                  equipment_snapshot: {},
                                  value_sources: {},
                                  notes: null,
                                  status: 'active',
                                  revision: 1,
                                  created_at: timestamp,
                                  availability: 'unknown',
                                  content_hash: null,
                                  byte_size: null
                                }))
const capabilities = {
  stage: 'ingestion', shared_library_read: true, project_assets_read: true, project_management: true,
  equipment_management: true, asset_import: true, asset_reference_write: false, asset_preview: false,
  asset_metadata_edit: true, dataset_management: true, asset_task_management: true, calibration_matching: false, asset_publish: false
}
let wrapper: VueWrapper<InstanceType<typeof Workspace>> | undefined
let total = 1
let pinia: ReturnType<typeof createPinia>
beforeEach(() => {
  pinia = createPinia()
  total = 1
  get.mockReset().mockImplementation(async (path: string) => {
    if (path.endsWith('/capabilities')) return capabilities
    const url = new URL(path, 'http://test')
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const limit = Number(url.searchParams.get('limit') ?? 50)
    return { items: path.includes('/library/items?') && total > 0 ? [libraryAsset(asset)] : [], total: path.includes('/library/items?') ? total : 0, limit, offset }
  })
  send.mockReset()
})
afterEach(() => { wrapper?.unmount(); wrapper = undefined })
async function open() {
  const mounted = mount(Workspace, { props: { native: true }, global: { plugins: [pinia] } })
  wrapper = mounted
  await flushPromises()
  return mounted
}

describe('minimal library toolbar', () => {
  it('keeps import and equipment beside a menu and removes the view and page-size toolbar buttons', async () => {
    const mounted = await open()
    expect(mounted.findAll('.apf-toolbar-actions .apf-import, .apf-toolbar-actions .apf-equipment').map(button => button.text())).toEqual(['导入', '设备管理'])
    expect(mounted.getComponent(LibraryMenu).props('items').map(item => item.label)).toEqual(['刷新', '批量管理', '回收站', '显示方式', '每页数量'])
    expect(mounted.findAll('.apf-library-categories [role="tab"]')).toHaveLength(3)
    expect(mounted.find('input[aria-label="搜索"]').exists()).toBe(true)
    expect(mounted.find('.apf-pagination select').exists()).toBe(false)
    expect(mounted.find('.apf-pagination button').exists()).toBe(false)
    expect(mounted.get('.apf-pagination').text()).toContain('1 条记录')
    expect(mounted.find('.apf-library-view').exists()).toBe(false)
    expect(mounted.find('input[type="checkbox"]').exists()).toBe(false)
  })

  it('enters explicit bulk mode, keeps confirmation cancellation safe and clears selection on completion', async () => {
    const mounted = await open()
    await mounted.findAll('details button').find(button => button.text() === '批量管理')!.trigger('click')
    await flushPromises()
    expect(mounted.get('.apf-toolbar-actions').text()).toContain('已选 0 项')
    const remove = mounted.findAll('.apf-toolbar-actions button').find(button => button.text() === '删除')!
    expect(remove.attributes('disabled')).toBeDefined()
    await mounted.get('input[aria-label="选择 M31.fit"]').setValue(true)
    expect(mounted.get('.apf-toolbar-actions').text()).toContain('已选 1 项')
    await remove.trigger('click')
    await mounted.findAll('.apf-trash-confirm button').find(button => button.text() === '取消')!.trigger('click')
    expect(send).not.toHaveBeenCalled()
    expect(mounted.get('input[aria-label="选择 M31.fit"]').element).toHaveProperty('checked', true)
    await mounted.findAll('.apf-toolbar-actions button').find(button => button.text() === '完成')!.trigger('click')
    expect(mounted.find('input[type="checkbox"]').exists()).toBe(false)
    expect(mounted.find('.apf-import').exists()).toBe(true)
    await mounted.findAll('details button').find(button => button.text() === '批量管理')!.trigger('click')
    await flushPromises()
    expect(mounted.get('.apf-toolbar-actions').text()).toContain('已选 0 项')
  })

  it('uses menu radio selections for display and page size while retaining server pagination', async () => {
    total = 51
    const mounted = await open()
    const store = useWorkspaceStore(pinia)
    await mounted.get('select[aria-label="显示方式"]').setValue('detail')
    expect(mounted.get('.apf-table-scroll').classes()).toContain('detail')
    await mounted.get('select[aria-label="每页数量"]').setValue('10')
    await flushPromises()
    expect(store.pageSize).toBe(10)
    expect(store.offset).toBe(0)
    expect(mounted.findAll('.apf-pagination button')).toHaveLength(2)
    await mounted.findAll('.apf-pagination button').find(button => button.text() === '下一页')!.trigger('click')
    await flushPromises()
    expect(store.offset).toBe(10)
    expect(get.mock.calls.some(([path]) => String(path).includes('offset=10'))).toBe(true)
    await mounted.get('select[aria-label="每页数量"]').setValue('all')
    await flushPromises()
    expect(store.pageSize).toBe('all')
    expect(mounted.find('.apf-pagination button').exists()).toBe(false)
    expect(send).not.toHaveBeenCalled()
  })

  it('keeps zero-record pagination quiet and opens trash only from the menu', async () => {
    total = 0
    const mounted = await open()
    expect(mounted.get('.apf-pagination').text()).toContain('0 条记录')
    expect(mounted.find('.apf-pagination button').exists()).toBe(false)
    expect(mounted.find('[role="dialog"]').exists()).toBe(false)
    await mounted.findAll('details button').find(button => button.text() === '回收站')!.trigger('click')
    await flushPromises()
    expect(mounted.get('[role="dialog"]').text()).toContain('回收站')
    expect(send).not.toHaveBeenCalled()
  })
})


it('aborts an actual library read when the page unmounts', async () => {
  await open()
  const original = get.getMockImplementation()!
  let observedSignal: AbortSignal | undefined
  let announceStarted: (() => void) | undefined
  const started = new Promise<void>(resolve => { announceStarted = resolve })
  get.mockImplementation((path: string, schema: unknown, signal?: AbortSignal) => {
    if (path.includes('/library/items?') && new URL(path, window.location.origin).searchParams.get('q') === 'slow') {
      observedSignal = signal
      announceStarted?.()
      return new Promise((_resolve, reject) => signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true }))
    }
    return original(path, schema, signal)
  })
  useWorkspaceStore(pinia).setQuery('slow')
  await started
  wrapper!.unmount()
  wrapper = undefined
  await flushPromises()
  expect(observedSignal?.aborted).toBe(true)
})
