import { flushPromises, mount } from '@vue/test-utils'
import { h } from 'vue'
import { focusManager } from '@tanstack/vue-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ImportTasks from '@ui/modules/data/imports/ImportTasks.vue'
import { taskSchema } from '@ui/modules/data/api/contracts'
import type { AssetTaskSummary } from '@ui/generated/api/types.gen'
import { ApiClientError } from '@ui/modules/data/api/client'

const {get,send}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send}}))
const id='00000000-0000-4000-8000-000000000001'
const base=taskSchema.parse({id,status:'running',sources:[],storage_mode:'managed',classification:{},parameters:{},notes:null,
  dataset_name:'Night',target_dataset_id:null,dataset_base_revision:null,dataset_id:null,enumeration_completed:true,retry_of_task_id:null,
  report:{registration:{total:2,registered:2,completed:true}},error:null,created_at:'2026-10-28T12:00:00Z',updated_at:'2026-10-28T12:00:00Z',items:[],items_total:2,items_completed:0,items_limit:20,items_offset:0})
const content={total:2,succeeded:1,failed:0,skipped:0,metadata_failed:0,bytes_total:100,bytes_copied:50,completed:false}
const preview={total:2,available:0,failed:0,unsupported:0,completed:false}
const page=(value:ReturnType<typeof taskSchema.parse>)=>{ const {id,status,dataset_name,target_dataset_id,dataset_id,enumeration_completed,report,error,created_at,updated_at,items_total,items_completed}=value; return {items:[{id,status,dataset_name,target_dataset_id,dataset_id,enumeration_completed,report,error,created_at,updated_at,items_total,items_completed}],total:1,limit:50,offset:0} }
let wrapper:ReturnType<typeof mount>|undefined
beforeEach(()=>{localStorage.clear();get.mockReset().mockResolvedValue(page(base));send.mockReset().mockResolvedValue({task_id:id,status:'queued'})})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;localStorage.clear();focusManager.setFocused(undefined);vi.useRealTimers()})

describe('managed import stages and one-time notices',()=>{
  it('does not present complete registration as completed original transfer',async()=>{
    wrapper=mount(ImportTasks,{props:{refreshToken:0}});await flushPromises()
    expect(wrapper.text()).toContain('2/2 项已登记')
    expect(wrapper.get('progress').attributes('value')).toBeUndefined()
    expect(wrapper.text()).not.toContain('原件托管完成')
  })

  it('shows original byte and file progress instead of registration progress',async()=>{
    get.mockResolvedValue(page({...base,report:{...base.report,content,preview}}))
    wrapper=mount(ImportTasks,{props:{refreshToken:0}});await flushPromises()
    expect(wrapper.get('progress').attributes('value')).toBe('50')
    expect(wrapper.get('progress').attributes('max')).toBe('100')
    expect(wrapper.text()).toContain('1/2 张')
    expect(wrapper.text()).toContain('正在托管')
  })

  it('notifies when originals finish while keeping background preview progress separate',async()=>{
    wrapper=mount(ImportTasks,{props:{refreshToken:0,workspace:'/workspace'}});await flushPromises()
    get.mockResolvedValue(page({...base,report:{content:{...content,succeeded:2,bytes_copied:100,completed:true},preview}}))
    await wrapper.setProps({refreshToken:1});await flushPromises()
    expect(wrapper.text()).toContain('原件托管完成 · 预览仍在后台生成')
    expect(wrapper.find('progress').exists()).toBe(false)
    expect(wrapper.emitted('notice')).toEqual([[expect.objectContaining({taskId:id,category:'content',kind:'success',title:'Night：原件托管完成'})]])
    expect(wrapper.emitted('completed')).toBeUndefined()
    await wrapper.setProps({refreshToken:2});await flushPromises()
    expect(wrapper.emitted('notice')).toHaveLength(1)
  })

  it.each([{succeeded:1,kind:'warning'},{succeeded:0,kind:'error'}])('sends $kind for a current failed content result without inline summaries',async({succeeded,kind})=>{
    get.mockResolvedValue(page({...base,status:'completed_with_errors',report:{content:{...content,succeeded,failed:2-succeeded,completed:true},preview:{...preview,completed:true}}}))
    wrapper=mount(ImportTasks,{props:{refreshToken:0,watchTaskIds:[id]}});await flushPromises()
    expect(wrapper.emitted('notice')).toEqual([[expect.objectContaining({kind,category:'content',description:expect.stringContaining('项失败')})]])
    expect(wrapper.find('summary').exists()).toBe(false)
    expect(wrapper.find('section').exists()).toBe(false)
    expect(send).not.toHaveBeenCalled()
  })

  it('keeps metadata failure wording separate from original failure',async()=>{
    get.mockResolvedValue(page({...base,report:{content:{...content,succeeded:2,metadata_failed:1,completed:true},preview}}))
    wrapper=mount(ImportTasks,{props:{refreshToken:0,watchTaskIds:[id]}});await flushPromises()
    expect(wrapper.emitted('notice')).toEqual([[expect.objectContaining({kind:'warning',title:'Night：原件已托管，部分资料解析异常'})]])
  })

  it('only adds one late preview warning and preserves the original success',async()=>{
    get.mockResolvedValue(page({...base,report:{content:{...content,succeeded:2,completed:true},preview}}))
    wrapper=mount(ImportTasks,{props:{refreshToken:0,watchTaskIds:[id]}});await flushPromises()
    get.mockResolvedValue(page({...base,status:'completed_with_errors',report:{content:{...content,succeeded:2,completed:true},preview:{...preview,available:1,failed:1,completed:true}}}))
    await wrapper.setProps({refreshToken:1});await flushPromises()
    expect(wrapper.emitted('notice')).toEqual([
      [expect.objectContaining({kind:'success',category:'content'})],
      [expect.objectContaining({kind:'warning',category:'preview',title:'Night：部分预览不可用，已托管原件保留'})]
    ])
    await wrapper.setProps({refreshToken:2});await flushPromises()
    expect(wrapper.emitted('notice')).toHaveLength(2)
  })

  it('does not replay historical successes or failures',async()=>{
    get.mockResolvedValue(page({...base,status:'failed',report:{content:{...content,failed:2,succeeded:0,completed:true},preview}}))
    wrapper=mount(ImportTasks,{props:{refreshToken:0}});await flushPromises()
    expect(wrapper.emitted('notice')).toBeUndefined()
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it('persists deduplication across remounts but keeps workspaces and new task identities independent',async()=>{
    const result={...base,report:{content:{...content,succeeded:2,completed:true},preview}}
    get.mockResolvedValue(page(result))
    wrapper=mount(ImportTasks,{props:{refreshToken:0,watchTaskIds:[id],workspace:'/one'}});await flushPromises()
    expect(wrapper.emitted('notice')).toHaveLength(1)
    wrapper.unmount()
    wrapper=mount(ImportTasks,{props:{refreshToken:0,watchTaskIds:[id],workspace:'/one'}});await flushPromises()
    expect(wrapper.emitted('notice')).toBeUndefined()
    await wrapper.setProps({workspace:'/two'});await flushPromises()
    expect(wrapper.emitted('notice')).toHaveLength(1)
    const other='00000000-0000-4000-8000-000000000002'
    get.mockResolvedValue(page({...result,id:other}))
    await wrapper.setProps({watchTaskIds:[other]});await flushPromises()
    expect(wrapper.emitted('notice')).toHaveLength(2)
  })

  it('keeps persisted paused tasks resumable and reports recovery errors',async()=>{
    get.mockResolvedValue(page({...base,status:'interrupted'}))
    send.mockRejectedValue(new ApiClientError('来源当前不可访问','service',409))
    wrapper=mount(ImportTasks,{props:{refreshToken:0}});await flushPromises()
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/asset-tasks/'+id+'/resume',expect.anything(),'POST',undefined)
    expect(wrapper.get('[role="alert"]').text()).toContain('来源当前不可访问')
  })

  it('forwards recovery state through the existing slot',async()=>{
    get.mockResolvedValue(page({...base,status:'interrupted'}))
    wrapper=mount(ImportTasks,{props:{refreshToken:0},slots:{default:({tasks,resume}:{tasks:AssetTaskSummary[];resume:(task:AssetTaskSummary)=>Promise<void>})=>h('button',{onClick:()=>resume(tasks[0])},'恢复')}})
    await flushPromises();await wrapper.get('button').trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledOnce()
  })

  it('keeps connection failures visible even when the library is empty',async()=>{
    get.mockRejectedValue(new ApiClientError('服务不可用','network'))
    wrapper=mount(ImportTasks,{props:{refreshToken:0}});await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('服务不可用')
  })
  it('stops active polling after completion even when the parent retains watched identities', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    wrapper = mount(ImportTasks, { props: { refreshToken: 0, workspace: '/one', watchTaskIds: [id] } })
    await flushPromises()
    get.mockResolvedValue(page({ ...base, status: 'completed' }))
    await vi.advanceTimersByTimeAsync(1_500)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('completed')).toEqual([[id]])
    await vi.advanceTimersByTimeAsync(6_000)
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('keeps interrupted imports visible without fast polling of a paused process', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    get.mockResolvedValue(page({ ...base, status: 'interrupted' }))
    wrapper = mount(ImportTasks, { props: { refreshToken: 0, watchTaskIds: [id] } })
    await flushPromises()
    expect(wrapper.text()).toContain('继续导入')
    await vi.advanceTimersByTimeAsync(6_000)
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('aborts the old workspace read and cannot replace new workspace results with a late response', async () => {
    let finishOld!: (value: ReturnType<typeof page>) => void
    get.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    wrapper = mount(ImportTasks, { props: { refreshToken: 0, workspace: '/one' } })
    await flushPromises()
    const oldSignal = get.mock.calls[0][2] as AbortSignal
    get.mockResolvedValue(page({ ...base, dataset_name: 'New workspace' }))
    await wrapper.setProps({ workspace: '/two' })
    await flushPromises()
    expect(oldSignal.aborted).toBe(true)
    expect(wrapper.text()).toContain('New workspace')
    finishOld(page({ ...base, dataset_name: 'Old workspace' }))
    await flushPromises()
    expect(wrapper.text()).not.toContain('Old workspace')
  })

  it('cancels a pending transport read when the progress view is closed', async () => {
    get.mockImplementationOnce(() => new Promise(() => {}))
    wrapper = mount(ImportTasks, { props: { refreshToken: 0 } })
    await flushPromises()
    const signal = get.mock.calls[0][2] as AbortSignal
    expect(signal.aborted).toBe(false)
    wrapper.unmount()
    wrapper = undefined
    expect(signal.aborted).toBe(true)
  })

  it('discovers a task submitted by another entry and returns to directory polling after it completes', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    get.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 })
    wrapper = mount(ImportTasks, { props: { refreshToken: 0, workspace: '/one' } })
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(1)
    get.mockResolvedValue(page(base))
    await vi.advanceTimersByTimeAsync(30_000)
    await flushPromises()
    expect(wrapper.text()).toContain('Night')
    expect(get).toHaveBeenCalledTimes(2)
    get.mockResolvedValue(page({ ...base, status: 'completed' }))
    await vi.advanceTimersByTimeAsync(1_500)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(1_500)
    expect(get).toHaveBeenCalledTimes(3)
    await vi.advanceTimersByTimeAsync(28_500)
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(4)
  })

  it('stops directory discovery when the task view is unmounted', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    get.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 })
    wrapper = mount(ImportTasks, { props: { refreshToken: 0, workspace: '/one' } })
    await flushPromises()
    wrapper.unmount()
    wrapper = undefined
    await vi.advanceTimersByTimeAsync(30_000)
    expect(get).toHaveBeenCalledTimes(1)
  })

})
