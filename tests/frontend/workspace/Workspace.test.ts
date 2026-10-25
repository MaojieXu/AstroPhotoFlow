import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '@frontend/App.vue'

const { get } = vi.hoisted(() => ({
  get: vi.fn(async (path: string) => path.endsWith('/capabilities')
    ? {
        stage: 'ingestion', shared_library_read: true, project_assets_read: true,
        project_management: true, equipment_management: true, asset_import: false, asset_reference_write: false, asset_preview: false,
        asset_metadata_edit: true, dataset_management: true, asset_task_management: true, calibration_matching: false, asset_publish: false
      }
    : { items: [], total: 0, limit: 50, offset: 0 })
}))

vi.mock('@frontend/assets/host-client', () => ({
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

  it('shows five side areas and opens each area in the current panel', async () => {
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(wrapper.findAll('input[type="file"]')[0].attributes('accept')).toContain('.heic,.heif,.hif')
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
    await wrapper.get('.apf-nav button[aria-label="设置"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('设置')
    expect(wrapper.get('.apf-management-tabs').text()).toBe('项目设备使用组合')
    await wrapper.findAll('.apf-management-tabs button').at(1)!.trigger('click')
    await flushPromises()
    expect(get.mock.calls.some(([path]) => path.includes('/equipment?'))).toBe(true)
    await wrapper.findAll('.apf-management-tabs button').at(2)!.trigger('click')
    await flushPromises()
    expect(get.mock.calls.some(([path]) => path.includes('/equipment-setups?'))).toBe(true)
    await flushPromises()
    await wrapper.get('.apf-nav button[aria-label="素材库"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.find('.apf-library-tabs').exists()).toBe(false)
    expect(wrapper.get('.apf-heading-actions').text()).toBe('导入刷新批量删除回收站')
    expect(wrapper.text()).not.toContain('后台任务')
    expect(wrapper.text()).not.toContain('数据集')
    expect(get.mock.calls.some(([path]) => path.includes('/projects?'))).toBe(true)
  })

  it('keeps a dirty form when navigation is cancelled', async () => {
    wrapper = mount(App, { global: { plugins: [createPinia()] } })
    await flushPromises()
    await wrapper.get('.apf-nav button[aria-label="设置"]').trigger('click')
    await flushPromises()
    await wrapper.get('.apf-management-tabs button').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button => button.text() === '新建项目')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-editor input').setValue('unsaved draft')
    await flushPromises()

    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    await wrapper.get('.apf-nav button[aria-label="节点仓库"]').trigger('click')
    await flushPromises()
    expect(confirm).toHaveBeenCalledOnce()
    expect((wrapper.get('.apf-editor input').element as HTMLInputElement).value).toBe('unsaved draft')
    expect(wrapper.get('h1').text()).toBe('设置')
  })
})
