import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ImportIssueDialog from '@ui/modules/data/imports/ImportIssueDialog.vue'
import { taskSchema } from '@ui/modules/data/api/contracts'

const {get,send}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send}}))
const id='00000000-0000-4000-8000-000000000001'
const time='2026-10-28T12:00:00Z'
const item={id, task_id:id, root_item_id:id, retry_of_item_id:null, root_id:'science', source_path:'bad.fit', position:0, status:'failed', content_status:'failed', metadata_status:'pending', preview_status:'pending', asset_id:null, error:{message:'来源已变化'}, created_at:time, updated_at:time}
const task=taskSchema.parse({id,status:'completed_with_errors',sources:[],storage_mode:'managed',classification:{},parameters:{},notes:null,dataset_name:'Night',target_dataset_id:null,dataset_base_revision:null,dataset_id:null,enumeration_completed:true,retry_of_task_id:null,report:{},error:null,created_at:time,updated_at:time,items:[item],items_total:1,items_completed:1,items_limit:200,items_offset:0})
let wrapper:ReturnType<typeof mount>|undefined
beforeEach(()=>{get.mockReset().mockResolvedValue(task);send.mockReset().mockResolvedValue({task_id:id,status:'queued'})})
afterEach(()=>{wrapper?.unmount();wrapper=undefined})

describe('one-time import notice details',()=>{
  it('reports an incomplete page sequence instead of presenting partial failures as complete',async()=>{
    get.mockResolvedValueOnce({...task,items_total:2}).mockResolvedValue({...task,items:[],items_total:2,items_offset:1})
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/test-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('ended before its declared total')
    expect(wrapper.text()).not.toContain('此阶段没有失败文件')
    expect(get).toHaveBeenCalledTimes(2)
    expect(send).not.toHaveBeenCalled()
  })

  it('cancels a pending report when changing workspace and ignores its late failure rows',async()=>{
    let finishOld!: (value:unknown)=>void
    get.mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve})).mockResolvedValue({...task,items:[],items_total:0})
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/old-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    const signal=get.mock.calls[0][2] as AbortSignal
    await wrapper.setProps({workspaceId:'/new-workspace'});await flushPromises()
    expect(signal.aborted).toBe(true)
    finishOld(task);await flushPromises()
    expect(wrapper.text()).not.toContain('bad.fit')
    expect(send).not.toHaveBeenCalled()
  })

  it('does not close a newly selected issue when an older retry acceptance arrives',async()=>{
    let accept!: (value:unknown)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{accept=resolve}))
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/test-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='重试失败项')!.trigger('click');await flushPromises()
    await wrapper.setProps({issue:{taskId:id,category:'preview'}});await flushPromises()
    accept({task_id:id,status:'queued'});await flushPromises()
    expect(wrapper.emitted('retried')).toBeUndefined()
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('shows file reasons and retries only failed items through the existing endpoint',async()=>{
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/test-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    expect(wrapper.text()).toContain('bad.fit：来源已变化')
    expect(send).not.toHaveBeenCalled()
    await wrapper.findAll('button').find(button=>button.text()==='重试失败项')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/asset-tasks/'+id+'/retry',expect.anything(),'POST',{item_ids:[id]})
    expect(wrapper.emitted('retried')).toEqual([[id]])
  })

  it('keeps a running task read-only and cancellation does not mutate task data',async()=>{
    get.mockResolvedValue({...task,status:'running'})
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/test-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    expect(wrapper.findAll('button').find(button=>button.text()==='重试失败项')!.attributes('disabled')).toBeDefined()
    await wrapper.findAll('button').find(button=>button.text()==='关闭')!.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(send).not.toHaveBeenCalled()
  })

  it('keeps request errors and the selected task available after a failed retry',async()=>{
    send.mockRejectedValue(new Error('任务状态已变化'))
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/test-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='重试失败项')!.trigger('click');await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('任务状态已变化')
    expect(wrapper.emitted('retried')).toBeUndefined()
    expect(wrapper.get('[role="dialog"]').text()).toContain('bad.fit')
  })

  it('refreshes a notification detail opened before the background task ended',async()=>{
    get.mockResolvedValueOnce({...task,status:'running'}).mockResolvedValue(task)
    wrapper=mount(ImportIssueDialog,{props:{workspaceId:'/test-workspace',issue:{taskId:id,category:'content'}}});await flushPromises()
    expect(wrapper.findAll('button').find(button=>button.text()==='重试失败项')!.attributes('disabled')).toBeDefined()
    await wrapper.findAll('button').find(button=>button.text()==='刷新状态')!.trigger('click');await flushPromises()
    expect(wrapper.findAll('button').find(button=>button.text()==='重试失败项')!.attributes('disabled')).toBeUndefined()
    expect(send).not.toHaveBeenCalled()
  })
})
