import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import { useWorkspaceStore } from '@ui/modules/data/workspace/store'
import { equipmentSchema, equipmentSetupSchema } from '@ui/modules/data/api/contracts'
import type { Equipment, EquipmentSetup } from '@ui/modules/data/api/contracts'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), assetApi: { get, send } }))
const timestamp = '2026-10-28T12:00:00Z'
const id = (index: number) => '00000000-0000-4000-8000-' + String(index).padStart(12, '0')
const device = (index: number, kind: 'camera' | 'filter' = 'camera') => equipmentSchema.parse({
  id: id(index), kind, name: 'Device ' + index, model: null, notes: null, specs: {}, status: 'active', revision: 1, created_at: timestamp, updated_at: timestamp
})
const setup = (index: number) => equipmentSetupSchema.parse({
  id: id(index), name: 'Rig ' + index, components: [], notes: null, status: 'active',
  revision: 1, created_at: timestamp, updated_at: timestamp
})
let devices: Equipment[]
let setups: EquipmentSetup[]
let wrapper: VueWrapper<InstanceType<typeof Workspace>> | undefined

beforeEach(() => {
  devices = []
  setups = []
  get.mockReset().mockImplementation(async (path: string) => {
    const url = new URL(path, 'http://test')
    if (url.pathname.endsWith('/capabilities')) return {
      stage: 'ingestion', shared_library_read: true, project_assets_read: true,
      project_management: true, equipment_management: true, asset_import: true,
      asset_reference_write: true, asset_preview: false, asset_metadata_edit: true,
      dataset_management: true, asset_task_management: true, calibration_matching: false,
      asset_publish: false
    }
    const items = url.pathname.endsWith('/equipment')
      ? devices.filter(item => !url.searchParams.get('kind') || item.kind === url.searchParams.get('kind'))
      : url.pathname.endsWith('/equipment-setups') ? setups : []
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const limit = Number(url.searchParams.get('limit') ?? 200)
    return { items: items.slice(offset, offset + limit), total: items.length, offset, limit }
  })
  send.mockReset().mockResolvedValue({ items: [], dependencies: [], blocked: false, preview_fingerprint: 'current' })
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.restoreAllMocks()
})

async function open(section: 'equipment' | 'equipment-setups', pageSize: 10 | 50 = 50) {
  const pinia = createPinia()
  const store = useWorkspaceStore(pinia)
  store.pageSize = pageSize
  const mounted = mount(Workspace, { props: { native: true }, global: { plugins: [pinia] } })
  wrapper = mounted
  await flushPromises()
  await mounted.vm.selectArea('settings', section)
  await flushPromises()
  return { mounted, store }
}

async function click(mounted: VueWrapper, text: string) {
  const button = mounted.findAll('button').find(item => item.text() === text)
  if (!button) throw new Error('Missing button: ' + text)
  await button.trigger('click')
  await flushPromises()
}

describe('compact equipment toolbar', () => {
  it.each([
    ['equipment-setups', '新建设备组合', '暂无设备组合'],
    ['equipment', '新建设备', '暂无设备']
  ] as const)('keeps one create action and no empty pagination in %s', async (section, create, empty) => {
    const { mounted } = await open(section)
    expect(mounted.get('h1').text()).toBe('设备管理')
    expect(mounted.get('button[aria-label="返回素材库"]').text()).toBe('')
    expect(mounted.findAll('button').filter(item => item.text() === create)).toHaveLength(1)
    expect(mounted.get('.apf-toolbar').text()).toContain(create)
    expect(mounted.findAll('h2')).toHaveLength(0)
    expect(mounted.text()).toContain(empty)
    expect(mounted.text()).not.toContain('0 条记录')
    expect(mounted.find('.apf-pagination').exists()).toBe(false)
    expect(mounted.findAll('button').some(item => ['筛选', '批量删除'].includes(item.text()))).toBe(false)
    await click(mounted, create)
    expect(mounted.get('[role="dialog"]').text()).toContain('保存')
  })

  it.each(['equipment', 'equipment-setups'] as const)('shows bulk delete only after selecting records in %s', async section => {
    devices = [device(1), device(2)]
    setups = [setup(1), setup(2)]
    const { mounted } = await open(section)
    const name = section === 'equipment' ? 'Device ' : 'Rig '
    const create = section === 'equipment' ? '新建设备' : '新建设备组合'
    expect(mounted.text()).not.toContain('删除所选')
    expect(mounted.find('input[type="checkbox"]').exists()).toBe(false)
    await click(mounted, '批量管理')
    expect(mounted.text()).toContain('已选 0 项')
    expect(mounted.findAll('button').find(button=>button.text()==='删除所选（0）')!.attributes('disabled')).toBeDefined()
    await mounted.get('input[aria-label="选择 ' + name + '1"]').setValue(true)
    expect(mounted.text()).toContain('删除所选（1）')
    await mounted.get('input[aria-label="全选当前页"]').setValue(true)
    await click(mounted, '删除所选（2）')
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/equipment-management/delete-preview', expect.anything(), 'POST', {
      items: [1, 2].map(index => ({ entry_type: section === 'equipment' ? 'equipment' : 'equipment_setup', id: id(index), revision: 1 }))
    })
    await click(mounted, '取消')
    expect(send.mock.calls.some(([path]) => String(path).endsWith('/delete'))).toBe(false)
    await click(mounted, '完成')
    expect(mounted.text()).not.toContain('删除所选')
    expect(mounted.find('input[type="checkbox"]').exists()).toBe(false)
    await click(mounted, '批量管理')
    await mounted.get('input[aria-label="选择 ' + name + '1"]').setValue(true)
    await mounted.get('input[aria-label="选择 ' + name + '1"]').setValue(false)
    expect(mounted.text()).toContain('已选 0 项')
    expect(mounted.find('input[aria-label="全选当前页"]').exists()).toBe(true)
    await click(mounted, '完成')
    await click(mounted, create)
    expect(mounted.find('[role="dialog"]').exists()).toBe(true)
  })

  it('applies the device type directly and clears selections before changing tabs', async () => {
    devices = [device(1), device(2, 'filter')]
    const { mounted } = await open('equipment')
    await click(mounted, '批量管理')
    await mounted.get('input[aria-label="选择 Device 1"]').setValue(true)
    await mounted.get('select[aria-label="设备类别"]').setValue('filter')
    await flushPromises()
    expect(mounted.text()).toContain('Device 2')
    expect(mounted.text()).not.toContain('Device 1')
    expect(mounted.text()).not.toContain('删除所选')
    await mounted.get('select[aria-label="设备类别"]').setValue('telescope')
    await flushPromises()
    expect(mounted.text()).toContain('没有匹配的记录，请调整搜索或设备类别。')
    expect(mounted.find('.apf-pagination').exists()).toBe(false)
    await mounted.get('select[aria-label="设备类别"]').setValue('filter')
    await flushPromises()
    await click(mounted, '批量管理')
    await mounted.get('input[aria-label="选择 Device 2"]').setValue(true)
    await click(mounted, '设备组合')
    expect(mounted.find('select[aria-label="设备类别"]').exists()).toBe(false)
    await click(mounted, '我的设备')
    expect(mounted.text()).toContain('Device 1')
    expect(mounted.text()).not.toContain('删除所选')
  })

  it.each(['equipment', 'equipment-setups'] as const)('uses fixed pages without changing library preferences in %s', async section => {
    devices = Array.from({ length: 51 }, (_, index) => device(index + 1))
    setups = Array.from({ length: 51 }, (_, index) => setup(index + 1))
    const { mounted, store } = await open(section, 10)
    const records=section==='equipment'?'button[aria-label^="选择设备 "]':'button[aria-label^="查看组合 "]'
    expect(mounted.findAll(records)).toHaveLength(50)
    expect(mounted.find('select[aria-label="每页显示数量"]').exists()).toBe(false)
    await click(mounted, '下一页')
    expect(mounted.findAll(records)).toHaveLength(1)
    expect(store.offset).toBe(50)
    expect(store.pageSize).toBe(10)
    await click(mounted, '上一页')
    expect(mounted.findAll(records)).toHaveLength(50)
    await mounted.vm.selectArea('library')
    await flushPromises()
    expect(mounted.get('select[aria-label="每页数量"]').element).toHaveProperty('value', '10')
  })

  it.each(['equipment','equipment-setups'] as const)('exits batch selection on paging and search in %s',async section=>{
    devices=Array.from({length:51},(_,index)=>device(index+1))
    setups=Array.from({length:51},(_,index)=>setup(index+1))
    const {mounted,store}=await open(section)
    await click(mounted,'批量管理')
    await mounted.get('input[aria-label="全选当前页"]').setValue(true)
    expect(mounted.text()).toContain('已选 50 项')
    await click(mounted,'下一页')
    expect(mounted.find('input[type="checkbox"]').exists()).toBe(false)
    expect(mounted.text()).not.toContain('删除所选')
    await click(mounted,'批量管理')
    store.query='target'
    await flushPromises()
    expect(mounted.find('input[type="checkbox"]').exists()).toBe(false)
    expect(mounted.text()).not.toContain('删除所选')
    await mounted.vm.selectArea('library')
    await flushPromises()
  })

  it('refreshes from More, returns from an emptied last page, and closes with Escape', async () => {
    setups = Array.from({ length: 51 }, (_, index) => setup(index + 1))
    const { mounted, store } = await open('equipment-setups')
    await click(mounted, '下一页')
    setups = setups.slice(0, 50)
    const more = mounted.get<HTMLDetailsElement>('details')
    await more.get('summary').trigger('click')
    await click(mounted, '刷新')
    expect(more.element.open).toBe(false)
    expect(store.offset).toBe(0)
    expect(mounted.text()).toContain('Rig 1')
    expect(mounted.find('.apf-pagination').exists()).toBe(false)
    await more.get('summary').trigger('click')
    await more.trigger('keydown', { key: 'Escape' })
    expect(more.element.open).toBe(false)
    await more.get('summary').trigger('click')
    document.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await mounted.vm.$nextTick()
    expect(more.element.open).toBe(false)
  })
})
