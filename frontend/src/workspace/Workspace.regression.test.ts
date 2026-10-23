import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App.vue'
import { useWorkspaceStore } from './store'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('../assets/host-client', () => ({ assetApi: { get, send } }))

const capabilities = {
  stage: 'foundation', shared_library_read: true, project_assets_read: true,
  project_management: true, equipment_management: true, capture_profile_management: true,
  asset_import: false, asset_reference_write: false, asset_preview: false,
  calibration_matching: false, asset_publish: false
}
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const project = {
  id: '1f740b2c-75f3-4f76-8f85-f08ade40a33f',
  name: 'M31', target_name: null, notes: null, capture_profile_ids: [],
  status: 'active', revision: 1, created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:00Z'
}
const idAt = (index: number) => '00000000-0000-4000-8000-' + String(index).padStart(12, '0')
const profileAt = (index: number) => ({
  id: idAt(index), name: 'Profile ' + index, camera_id: idAt(index + 1000),
  optical_system_id: null, filter_id: null, frame_type: 'light',
  exposure_seconds: null, gain: null, offset: null, sensor_temperature_c: null,
  binning_x: null, binning_y: null, notes: null, status: 'active', revision: 1,
  created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:00Z'
})
const page = (items: unknown[], total = items.length, offset = 0, limit = 50) => ({ items, total, limit, offset })
const url = (path: string) => new URL(path, 'http://comfy.test')

let wrapper: ReturnType<typeof mount>
let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  get.mockReset()
  send.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
})

async function openSettings() {
  await wrapper.get('.apf-nav button[aria-label="设置"]').trigger('click')
  await flushPromises()
}

describe('first-stage regression fixes', () => {
  it('loads every profile page before editing project associations', async () => {
    const profiles = Array.from({ length: 201 }, (_, index) => profileAt(index))
    const existingId = profiles[200].id
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      const request = url(path)
      if (request.pathname.endsWith('/projects')) return page([{ ...project, capture_profile_ids: [existingId] }])
      if (request.pathname.endsWith('/equipment')) return emptyPage
      if (request.pathname.endsWith('/capture-profiles')) {
        const offset = Number(request.searchParams.get('offset'))
        return page(profiles.slice(offset, offset + 200), profiles.length, offset, 200)
      }
      return emptyPage
    })
    send.mockResolvedValue(project)
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await openSettings()
    await wrapper.get('.apf-record').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '编辑项目')!.trigger('click')
    await flushPromises()

    const choices = wrapper.get('select[multiple]')
    expect(choices.find('option[value="' + existingId + '"]').exists()).toBe(true)
    await choices.setValue([existingId, profiles[0].id])
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const savedIds = send.mock.calls[0][3].capture_profile_ids as string[]
    expect(new Set(savedIds)).toEqual(new Set([existingId, profiles[0].id]))
    expect(get.mock.calls.some(([path]) => url(path).searchParams.get('offset') === '200')).toBe(true)
  })

  it('does not display project rows as equipment after the equipment request fails', async () => {
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      const request = url(path)
      if (request.pathname.endsWith('/projects')) return page([project])
      if (request.pathname.endsWith('/equipment')) throw new TypeError('offline')
      return emptyPage
    })
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await openSettings()
    expect(wrapper.findAll('.apf-record')).toHaveLength(1)

    await wrapper.findAll('.apf-management-tabs button')[1].trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('请求失败')
    expect(wrapper.findAll('.apf-record')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('M31')
    expect(wrapper.text()).not.toContain('此处目前没有记录')
  })

  it('resets filtered pages and search pages to offset zero', async () => {
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      const request = url(path)
      if (request.pathname.endsWith('/projects')) return page([], 80, Number(request.searchParams.get('offset')))
      return emptyPage
    })
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await openSettings()
    const store = useWorkspaceStore(pinia)
    store.offset = 50
    await flushPromises()
    expect(url(get.mock.calls.at(-1)![0]).searchParams.get('offset')).toBe('50')

    await wrapper.get('select[aria-label="状态筛选"]').setValue('archived')
    await flushPromises()
    expect(url(get.mock.calls.at(-1)![0]).searchParams.get('offset')).toBe('0')

    store.offset = 50
    await flushPromises()
    await wrapper.get('input[aria-label="搜索"]').setValue('M31 #2')
    await new Promise(resolve => setTimeout(resolve, 300))
    await flushPromises()
    const searchRequest = get.mock.calls.map(([path]) => url(path)).filter(request =>
      request.pathname.endsWith('/projects') && request.searchParams.has('q')
    ).at(-1)!
    expect(searchRequest.searchParams.get('offset')).toBe('0')
    expect(searchRequest.searchParams.get('q')).toBe('M31 #2')
  })

  it('does not let an older search response replace the current query', async () => {
    let finishOldSearch!: (value: ReturnType<typeof page>) => void
    const older = { ...project, id: idAt(3000), name: 'older result' }
    const newer = { ...project, id: idAt(3001), name: 'newer result' }
    get.mockImplementation((path: string) => {
      if (path.endsWith('/capabilities')) return Promise.resolve(capabilities)
      const request = url(path)
      if (request.pathname.endsWith('/projects')) {
        const query = request.searchParams.get('q')
        if (query === 'older') return new Promise(resolve => { finishOldSearch = resolve })
        if (query === 'newer') return Promise.resolve(page([newer]))
        return Promise.resolve(page([project]))
      }
      return Promise.resolve(emptyPage)
    })
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await openSettings()
    const search = wrapper.get('input[aria-label="搜索"]')
    await search.setValue('older')
    await new Promise(resolve => setTimeout(resolve, 300))
    await flushPromises()
    expect(finishOldSearch).toBeTypeOf('function')

    await search.setValue('newer')
    await new Promise(resolve => setTimeout(resolve, 300))
    await flushPromises()
    finishOldSearch(page([older]))
    await flushPromises()

    expect(wrapper.text()).toContain('newer result')
    expect(wrapper.text()).not.toContain('older result')
  })
})
