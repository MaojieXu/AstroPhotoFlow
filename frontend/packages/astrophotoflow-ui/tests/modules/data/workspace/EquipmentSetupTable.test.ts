import { flushPromises, mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import { useWorkspaceStore } from '@ui/modules/data/workspace/store'
import { equipmentSchema, equipmentSetupSchema } from '@ui/modules/data/api/contracts'
import type { Equipment, EquipmentSetup } from '@ui/modules/data/api/contracts'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', () => ({ assetApi: { get, send } }))
const timestamp = '2026-10-28T12:00:00Z'
const id = (value: number) => '00000000-0000-4000-8000-' + String(value).padStart(12, '0')
const setup = (value: number, components: EquipmentSetup['components'] = []) => equipmentSetupSchema.parse({
  id: id(value), name: 'Rig ' + value, components, notes: null, status: 'active',
  revision: 1, created_at: timestamp, updated_at: timestamp
})
let devices: Equipment[]
let setups: EquipmentSetup[]
let wrapper: VueWrapper<InstanceType<typeof Workspace>> | undefined

beforeEach(() => {
  devices = []
  setups = [setup(100)]
  get.mockReset().mockImplementation(async (path: string) => {
    const url = new URL(path, 'http://test')
    if (url.pathname.endsWith('/capabilities')) return {
      stage: 'ingestion', shared_library_read: true, project_assets_read: true,
      project_management: true, equipment_management: true, asset_import: true,
      asset_reference_write: true, asset_preview: false, asset_metadata_edit: true,
      dataset_management: true, asset_task_management: true, calibration_matching: false,
      asset_publish: false
    }
    const items = url.pathname.endsWith('/equipment') ? devices : url.pathname.endsWith('/equipment-setups') ? setups : []
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const limit = Number(url.searchParams.get('limit') ?? 200)
    return { items: items.slice(offset, offset + limit), total: items.length, offset, limit }
  })
  send.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.restoreAllMocks()
})

async function open() {
  const pinia = createPinia()
  const store = useWorkspaceStore(pinia)
  const mounted = mount(Workspace, { props: { native: true }, global: { plugins: [pinia] } })
  wrapper = mounted
  await flushPromises()
  await mounted.vm.selectArea('settings', 'equipment-setups')
  await flushPromises()
  return { mounted, store }
}

async function click(mounted: VueWrapper, label: string) {
  const button = mounted.findAll('button').find(item => item.text() === label)
  if (!button) throw new Error('Missing button: ' + label)
  await button.trigger('click')
  await flushPromises()
}

function latestListQuery() {
  return get.mock.calls.map(([path]) => new URL(String(path), 'http://test'))
    .filter(url => url.pathname.endsWith('/equipment-setups')).at(-1)?.searchParams
}

describe('equipment setup table', () => {
  it('shows six columns, resolves both component sources, and keeps optional columns empty', async () => {
    devices = ['camera', 'optical_system', 'mount', 'filter', 'accessory'].map((kind, index) => equipmentSchema.parse({
      id: id(index + 1), kind, name: ['Camera with a long full name', 'Legacy optics', 'Mount', 'Filter', 'MPCC'][index],
      model: null, serial_number: null, notes: null, specs: {}, status: 'active',
      revision: 1, created_at: timestamp, updated_at: timestamp
    }))
    setups = [setup(100, [
      ...devices.map(item => ({ source: 'registered' as const, equipment_id: item.id })),
      { source: 'inline', equipment: { kind: 'camera', name: 'Inline camera', model: null, serial_number: null, notes: null, specs: {} } }
    ]), setup(101)]
    const { mounted } = await open()
    const table = mounted.get('table[aria-label="设备组合列表"]')
    expect(table.findAll('th').map(item => item.text())).toEqual(['名称', '相机', '望远镜', '赤道仪', '滤镜', '光学附件'])
    expect(table.find('input[type="checkbox"]').exists()).toBe(false)
    const first = table.findAll('tbody tr')[0]
    expect(first.text()).toContain('Camera with a long full name 等 2 件')
    expect(first.text()).toContain('Legacy optics（既有成像系统）')
    expect(first.text()).toContain('MPCC')
    expect(first.findAll('[title]').some(item => item.attributes('title') === 'Camera with a long full name\nInline camera')).toBe(true)
    expect(mounted.find('button[aria-label="设备组合说明"]').exists()).toBe(false)
    expect(table.find('i.pi-info-circle').exists()).toBe(false)
    expect(mounted.find('section[aria-label="组合拍摄预设"]').exists()).toBe(false)
    expect(table.findAll('tbody tr')[1].findAll('td').slice(1).map(item => item.text())).toEqual(['—', '—', '—', '—', '—'])
    await first.trigger('click')
    await flushPromises()
    const actions=mounted.get('[role="group"][aria-label="组合操作"]')
    expect(actions.findAll('button').map(button=>button.text())).toEqual(['新建拍摄预设','编辑设备组合'])
    expect(mounted.findAll('button').filter(button=>button.text()==='编辑设备组合')).toHaveLength(1)
    expect(mounted.find('section[aria-label="设备组合详情"]').exists()).toBe(false)
    const more=mounted.get('details')
    expect(more.findAll('button').map(button=>button.text())).toEqual(['刷新','批量管理','删除组合'])
    await click(mounted,'编辑设备组合')
    expect(mounted.find('form[aria-label="设备组合表单"]').exists()).toBe(true)
    expect(mounted.get('#setup-name').element).toHaveProperty('value','Rig 100')
    expect(mounted.get('select[aria-label="选择滤镜"]').element).toHaveProperty('value',id(4))
    expect(mounted.get('form[aria-label="设备组合表单"]').find('i.pi-info-circle').exists()).toBe(false)
    await click(mounted,'取消')
    expect(mounted.find('form[aria-label="设备组合表单"]').exists()).toBe(false)
    expect(send).not.toHaveBeenCalled()
  })

  it.each([
    ['name', '名称'], ['camera', '相机'], ['telescope', '望远镜'],
    ['mount', '赤道仪'], ['filter', '滤镜'], ['accessory', '光学附件']
  ] as const)('requests global %s sorting, resets paging, and clears selection', async (key, label) => {
    setups = Array.from({ length: 51 }, (_, index) => setup(index + 100))
    const { mounted, store } = await open()
    expect(latestListQuery()?.get('sort_by')).toBe('created_at')
    expect(latestListQuery()?.get('order')).toBe('desc')
    await click(mounted, '下一页')
    await click(mounted, '批量管理')
    await mounted.get('input[aria-label="选择 Rig 150"]').setValue(true)
    const header = mounted.get('table[aria-label="设备组合列表"]').findAll('th').find(item => item.text() === label)
    if (!header) throw new Error('Missing column: ' + label)
    await header.get('button').trigger('click')
    await flushPromises()
    expect(store.offset).toBe(0)
    expect(latestListQuery()?.get('sort_by')).toBe(key)
    expect(latestListQuery()?.get('order')).toBe('asc')
    expect(mounted.text()).not.toContain('删除所选')
    expect(header.attributes('aria-sort')).toBe('ascending')
    await header.get('button').trigger('click')
    await flushPromises()
    expect(latestListQuery()?.get('order')).toBe('desc')
    expect(header.attributes('aria-sort')).toBe('descending')
  })

  it('refreshes registered device names when returning from My Devices', async () => {
    devices = [equipmentSchema.parse({
      id: id(1), kind: 'camera', name: 'Original camera', model: null, serial_number: null,
      notes: null, specs: {}, status: 'active', revision: 1, created_at: timestamp, updated_at: timestamp
    })]
    setups = [setup(100, [{ source: 'registered', equipment_id: id(1) }])]
    const { mounted } = await open()
    expect(mounted.get('table[aria-label="设备组合列表"]').text()).toContain('Original camera')
    await click(mounted, '我的设备')
    devices = [{ ...devices[0], name: 'Renamed camera', revision: 2 }]
    await click(mounted, '设备组合')
    const table = mounted.get('table[aria-label="设备组合列表"]')
    expect(table.text()).toContain('Renamed camera')
    expect(table.text()).not.toContain('Original camera')
  })

  it.each(['组合', '预设'])('blocks sorting while the %s draft is dirty', async editor => {
    const { mounted } = await open()
    await mounted.get('button[aria-label="查看组合 Rig 100"]').trigger('click')
    await flushPromises()
    await click(mounted, editor === '组合' ? '编辑设备组合' : '新建拍摄预设')
    const name=mounted.get(editor === '组合' ? '#setup-name' : '#preset-name')
    await name.setValue('Unsaved name')
    await flushPromises()
    const headers = mounted.get('table[aria-label="设备组合列表"]').findAll('th button')
    expect(headers.every(button => button.attributes('disabled') !== undefined)).toBe(true)
    await headers[1].trigger('click')
    expect(latestListQuery()?.get('sort_by')).toBe('created_at')
    expect(name.element).toHaveProperty('value', 'Unsaved name')
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await click(mounted, '取消')
    expect(headers.every(button => button.attributes('disabled') === undefined)).toBe(true)
  })

  it('blocks sorting while an unchanged setup save is pending', async () => {
    const { mounted } = await open()
    await mounted.get('button[aria-label="查看组合 Rig 100"]').trigger('click')
    await flushPromises()
    await click(mounted, '编辑设备组合')
    let finish!: (value: EquipmentSetup) => void
    send.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await mounted.get('form[aria-label="设备组合表单"]').trigger('submit')
    await flushPromises()
    const sort = mounted.get('table[aria-label="设备组合列表"]').findAll('th button')[1]
    expect(sort.attributes('disabled')).toBeDefined()
    expect(mounted.get('[role="group"][aria-label="组合操作"]').findAll('button').every(button=>button.attributes('disabled')!==undefined)).toBe(true)
    finish({ ...setup(100), revision: 2 })
    await flushPromises()
    expect(sort.attributes('disabled')).toBeUndefined()
  })

  it('keeps row selection separate from bulk deletion and does not change the library sort', async () => {
    const { mounted } = await open()
    await click(mounted, '批量管理')
    await mounted.get('input[aria-label="选择 Rig 100"]').setValue(true)
    expect(mounted.find('section[aria-label="组合拍摄预设"]').exists()).toBe(false)
    expect(mounted.text()).toContain('删除所选（1）')
    await click(mounted, '完成')
    await mounted.get('button[aria-label="查看组合 Rig 100"]').trigger('click')
    await flushPromises()
    expect(mounted.find('section[aria-label="组合拍摄预设"]').exists()).toBe(true)
    await click(mounted, '相机')
    await mounted.vm.selectArea('library')
    await flushPromises()
    const query = get.mock.calls.map(([path]) => new URL(String(path), 'http://test'))
      .filter(url => url.pathname.endsWith('/library/items')).at(-1)?.searchParams
    expect(query?.get('sort_by')).toBe('created_at')
    expect(query?.get('order')).toBe('desc')
  })
})
