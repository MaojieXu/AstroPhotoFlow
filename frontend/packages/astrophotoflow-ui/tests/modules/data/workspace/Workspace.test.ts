import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'

const { get } = vi.hoisted(() => ({
  get: vi.fn(async (path: string) => path.endsWith('/capabilities')
    ? {
        stage: 'ingestion', shared_library_read: true, project_assets_read: true,
        project_management: true, equipment_management: true, asset_import: false, asset_reference_write: false, asset_preview: false,
        asset_metadata_edit: true, dataset_management: true, asset_task_management: true, calibration_matching: false, asset_publish: false
      }
    : { items: [], total: 0, limit: 50, offset: 0 })
}))

vi.mock('@ui/modules/data/api/index', () => ({
  assetApi: { get, send: vi.fn() }
}))

describe('workspace panel', () => {
  let wrapper: ReturnType<typeof mount> | undefined

  afterEach(async () => {
    vi.restoreAllMocks()
    wrapper?.unmount()
    wrapper = undefined
    document.body.innerHTML = ''
  })

  it('opens native equipment management from beside import and starts on equipment combinations', async () => {
    const native = mount(Workspace, { props: { native: true }, global: { plugins: [createPinia()] } })
    wrapper = native
    await flushPromises()
    expect(native.find('.apf-nav').exists()).toBe(false)
    const button = native.get('.apf-equipment')
    expect(button.element.previousElementSibling?.classList.contains('apf-import')).toBe(true)
    await button.trigger('click')
    expect(native.emitted('manage-equipment')).toHaveLength(1)
    await native.vm.selectArea('settings')
    await flushPromises()
    expect(native.get('h1').text()).toBe('设备管理')
    expect(native.get('.apf-management-tabs button[aria-current="page"]').text()).toBe('设备组合')
    expect(native.text()).toContain('新建设备组合')
    await native.get('.apf-heading > button').trigger('click')
    expect(native.emitted('back-to-library')).toHaveLength(1)
  })

  it('shows five side areas and opens each area in the current panel', async () => {
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    expect(wrapper.find('dialog').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('打开资产工作区')
    expect(wrapper.get('.apf-nav').findAll('button')).toHaveLength(5)
    expect(wrapper.get('.apf-nav').text()).toBe('')
    expect(wrapper.get('.apf-import').text()).toBe('导入')
    expect((wrapper.get('.apf-import').element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.get('.apf-nav button[aria-label="节点仓库"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('节点仓库')
    expect(wrapper.text()).toContain('节点仓库区域已预留')
    await wrapper.get('.apf-nav button[aria-label="可安装软件"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('可安装软件')
    expect(wrapper.text()).toContain('软件目录和安装功能尚未接入')
    await wrapper.get('.apf-nav button[aria-label="Agent 聊天"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('Agent 聊天')
    expect(wrapper.text()).toContain('聊天功能尚未接入')
    await wrapper.get('.apf-nav button[aria-label="设备管理"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('设备管理')
    expect(wrapper.get('.apf-management-tabs').text()).toBe('设备组合我的设备')
    await wrapper.findAll('.apf-management-tabs button').at(1)!.trigger('click')
    await flushPromises()
    expect(get.mock.calls.some(([path]) => path.includes('/equipment?'))).toBe(true)
    await wrapper.findAll('.apf-management-tabs button').at(0)!.trigger('click')
    await flushPromises()
    expect(get.mock.calls.some(([path]) => path.includes('/equipment-setups?'))).toBe(true)
    await flushPromises()
    await wrapper.get('.apf-nav button[aria-label="素材库"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.find('.apf-library-tabs').exists()).toBe(false)
    expect(wrapper.get('.apf-heading-actions > button').text()).toBe('导入')
    expect(wrapper.get('.apf-heading-actions details').text()).toContain('批量管理')
    expect(wrapper.find('.apf-library-view').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('后台任务')
    expect(wrapper.text()).not.toContain('图像组')
    expect(get.mock.calls.some(([path]) => path.includes('/projects?'))).toBe(false)
  })

  it('keeps a dirty form when navigation is cancelled', async () => {
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    await wrapper.get('.apf-nav button[aria-label="设备管理"]').trigger('click')
    await flushPromises()
    await wrapper.get('.apf-management-tabs button').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '新建设备组合')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-editor input').setValue('unsaved draft')
    await flushPromises()

    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    await wrapper.get('.apf-nav button[aria-label="节点仓库"]').trigger('click')
    await flushPromises()
    expect(confirm).toHaveBeenCalledOnce()
    expect((wrapper.get('.apf-editor input').element as HTMLInputElement).value).toBe('unsaved draft')
    expect(wrapper.get('h1').text()).toBe('设备管理')
  })
})
