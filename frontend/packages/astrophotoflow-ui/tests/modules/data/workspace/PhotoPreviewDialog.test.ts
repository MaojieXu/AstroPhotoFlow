import { fixedMemberFixture } from '../../../fixtures/library-members'
import { metadataForMembers } from '../../../fixtures/library-summary'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PhotoPreviewDialog from '@ui/modules/data/media/PhotoPreviewDialog.vue'
import FixedDatasetMembers from '@ui/modules/data/datasets/FixedDatasetMembers.vue'
import App from '@ui/modules/data/App.vue'
import { ApiClientError } from '@ui/core/api/errors'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import { createPinia } from 'pinia'
import { displayPreviewSchema } from '@ui/modules/data/api/contracts'

const { get, send, getBlob } = vi.hoisted(() => ({get:vi.fn(),send:vi.fn(),getBlob:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), displayPreviewApi: (await import('../../../fixtures/library-api')).createDisplayPreviewApiFixture(get,send,getBlob),assetApi:{get,send,getBlob}}))
const assetId='00000000-0000-4000-8000-000000000001'
const versionId='00000000-0000-4000-8000-000000000002'
const photo={assetId,versionId,title:'Pinned photo',basePath:`/astrophotoflow/api/v1/library/assets/${assetId}/versions/${versionId}/previews`}
const recipe={algorithm:'auto-mtf-1',input_offset:0,white_balance:[2,1,3],shadows:10,highlights:900,midtones:.1}
const state=(status:string,error:unknown=null)=>({asset_version_id:versionId,size:'display',status,width:status==='available'?1080:null,height:status==='available'?720:null,error,stretch:status==='available'?recipe:null})
let wrapper:ReturnType<typeof mount>|undefined
let createUrl:ReturnType<typeof vi.fn>
let revokeUrl:ReturnType<typeof vi.fn>
beforeEach(()=>{
  vi.useFakeTimers();get.mockReset();send.mockReset();getBlob.mockReset()
  createUrl=vi.fn(()=> 'blob:display');revokeUrl=vi.fn()
  class BrowserURL extends URL {}
  Object.assign(BrowserURL,{createObjectURL:createUrl,revokeObjectURL:revokeUrl})
  vi.stubGlobal('URL',BrowserURL)
  getBlob.mockResolvedValue(new Blob(['jpeg'],{type:'image/jpeg'}))
})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.useRealTimers();vi.unstubAllGlobals()})

describe('lightweight photo preview',()=>{
  it('stops polling after a status failure without resubmitting generation',async()=>{
    send.mockResolvedValue(state('generating'))
    get.mockRejectedValue(new ApiClientError('Preview status unavailable','service',503,'PREVIEW_STATUS_UNAVAILABLE'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    await vi.advanceTimersByTimeAsync(500);await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Preview status unavailable')
    await vi.advanceTimersByTimeAsync(3000);await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledTimes(1)
    expect(getBlob).not.toHaveBeenCalled()
  })

  it('clears a display decode failure before an explicit retry',async()=>{
    send.mockResolvedValue(state('available'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    await wrapper.get('img').trigger('error')
    expect(wrapper.get('[role="alert"]').text()).toContain('无法显示预览')
    await wrapper.findAll('button').find(button=>button.text()==='重试')!.trigger('click');await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.get('img').attributes('src')).toBe('blob:display')
    expect(send).toHaveBeenCalledTimes(2)
  })

  it('automatically computes this photo once and notifies thumbnail consumers when ready',async()=>{
    send.mockResolvedValue(state('generating'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    expect(wrapper.findAll('input[type="range"]')).toHaveLength(0)
    expect(wrapper.find('footer').exists()).toBe(false)
    expect(wrapper.find('.apf-auto-stretch').exists()).toBe(false)
    expect(send).toHaveBeenCalledTimes(1)
    const parameters={algorithm:'auto-mtf-1',input_offset:0,white_balance:[2,1,3],shadows:10,highlights:900,midtones:.1}
    get.mockResolvedValue({...state('available'),stretch:parameters})
    expect(send).toHaveBeenLastCalledWith(expect.stringContaining('/display/auto-stretch'),displayPreviewSchema,'POST',undefined)
    expect(wrapper.emitted('updated')).toBeUndefined()
    await vi.advanceTimersByTimeAsync(500);await flushPromises()
    expect(wrapper.emitted('updated')).toEqual([[photo]])
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(send).toHaveBeenCalledTimes(1)
    expect(getBlob).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('button')).toHaveLength(1)
  })
  it('reads the saved per-photo recipe when reopened without recomputing',async()=>{
    const parameters={algorithm:'auto-mtf-1',input_offset:0,white_balance:[1],shadows:10,highlights:900,midtones:.1}
    expect(displayPreviewSchema.parse({...state('available'),stretch:parameters}).stretch).toEqual(parameters)
    send.mockResolvedValue({...state('available'),stretch:parameters})
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    expect(wrapper.get('img').attributes('src')).toBe('blob:display')
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][0]).toMatch(/previews\/display\/auto-stretch$/)
  })
  it('reports an automatic stretch failure and retries from the error action',async()=>{
    send.mockRejectedValueOnce(new Error('分析失败')).mockResolvedValue(state('available'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('分析失败')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.get('button[aria-label="关闭大图预览"]').attributes('disabled')).toBeUndefined()
    await wrapper.findAll('button').find(button=>button.text()==='重试')!.trigger('click');await flushPromises()
    expect(wrapper.emitted('updated')).toEqual([[photo]])
  })
  it('finishes an existing legacy preview job before ensuring its own automatic recipe',async()=>{
    send.mockResolvedValue(state('generating'))
    get.mockResolvedValueOnce({...state('available'),stretch:null}).mockResolvedValue(state('available'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    await vi.advanceTimersByTimeAsync(500);await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(getBlob).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(500);await flushPromises()
    expect(getBlob).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('updated')).toEqual([[photo]])
  })
  it('closes from the focused button inside a workspace that stops keyboard bubbling',async()=>{
    const host=document.createElement('div')
    document.body.append(host)
    host.addEventListener('keydown',event=>event.stopPropagation())
    send.mockResolvedValue(state('available'))
    try{
      wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo},attachTo:host})
      await flushPromises()
      await wrapper.get('button[aria-label="关闭大图预览"]').trigger('keydown',{key:'Escape'})
      expect(wrapper.emitted('close')).toHaveLength(1)
    }finally{
      wrapper?.unmount();wrapper=undefined;host.remove()
    }
  })
  it('validates the state DTO and polls without repeating the scheduling request',async()=>{
    expect(displayPreviewSchema.parse(state('generating')).status).toBe('generating')
    send.mockResolvedValue(state('generating'));get.mockResolvedValue(state('available'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}})
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('正在读取')
    await vi.advanceTimersByTimeAsync(500);await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith(expect.stringContaining('/versions/'+versionId+'/previews/display/status'),undefined,expect.any(AbortSignal))
    expect(wrapper.get('img').attributes('src')).toBe('blob:display')
    expect(wrapper.get('img').attributes('alt')).toBe('Pinned photo')
    await wrapper.get('button[aria-label="关闭大图预览"]').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    window.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))
    expect(wrapper.emitted('close')).toHaveLength(2)
    await wrapper.setProps({photo:undefined})
    expect(revokeUrl).toHaveBeenCalledWith('blob:display')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
  it('shows an explicit error/not-ready state and lets the user retry',async()=>{
    send.mockResolvedValueOnce(state('not_ready',{code:'SOURCE_NOT_READY',message:'原件尚未完成'})).mockResolvedValue(state('available'))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}});await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('原件尚未完成')
    await wrapper.findAll('button').find(button=>button.text()==='重试')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(wrapper.find('img').exists()).toBe(true)
  })
  it('ignores a late response after closing and cancels polling on unmount',async()=>{
    let resolve!:(value:unknown)=>void
    send.mockReturnValue(new Promise(done=>{resolve=done}))
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo}})
    await wrapper.setProps({photo:undefined})
    resolve(state('available'));await flushPromises()
    expect(getBlob).not.toHaveBeenCalled()
    send.mockResolvedValue(state('generating'))
    await wrapper.setProps({photo});await flushPromises()
    wrapper.unmount();wrapper=undefined
    await vi.advanceTimersByTimeAsync(1000)
    expect(get).not.toHaveBeenCalled()
  })
  it('uses the project-reference scope for a pinned private photo',async()=>{
    send.mockResolvedValue(state('available'))
    const basePath='/astrophotoflow/api/v1/projects/project/asset-references/reference/previews'
    wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo:{...photo,basePath}}});await flushPromises()
    expect(send.mock.calls[0][0]).toBe(basePath+'/display/auto-stretch')
    expect(getBlob).toHaveBeenCalledWith(basePath+'/display')
  })
})

describe('project fixed version member browser',()=>{
  it.each(['collapse','workspace'])('cancels a pending fixed-member read on %s and ignores its late rows',async(change)=>{
    const datasetId='00000000-0000-4000-8000-000000000090'
    const firstVersion='00000000-0000-4000-8000-000000000091'
    const secondVersion='00000000-0000-4000-8000-000000000092'
    const oldMember=fixedMemberFixture({id:assetId,name:'Old scope member'},{id:versionId},firstVersion,0)
    const newMember=fixedMemberFixture({id:assetId,name:'New scope member'},{id:versionId},secondVersion,0)
    let finishOld!: (value:unknown)=>void
    get.mockImplementationOnce(()=>new Promise(resolve=>{finishOld=resolve}))
      .mockResolvedValue({items:[newMember],total:1,limit:10,offset:0})
    wrapper=mount(FixedDatasetMembers,{props:{workspaceId:'/first-workspace',datasetId,versionId:firstVersion,count:1}})
    await wrapper.get('.apf-fixed-members > button').trigger('click');await flushPromises()
    const signal=get.mock.calls[0][2] as AbortSignal
    if(change==='collapse')await wrapper.get('.apf-fixed-members > button').trigger('click')
    else await wrapper.setProps({workspaceId:'/second-workspace',versionId:secondVersion})
    await flushPromises()
    expect(signal.aborted).toBe(true)
    finishOld({items:[oldMember],total:1,limit:10,offset:0});await flushPromises()
    expect(wrapper.text()).not.toContain('Old scope member')
    if(change==='workspace')expect(wrapper.text()).toContain('New scope member')
    else expect(getBlob).not.toHaveBeenCalled()
  })

  it('pages only pinned version members and previews A even when current versions are B',async()=>{
    const fixedDataset='00000000-0000-4000-8000-000000000090'
    const fixedVersion='00000000-0000-4000-8000-000000000091'
    const currentVersion='00000000-0000-4000-8000-000000000092'
    const members=Array.from({length:11},(_,index)=>fixedMemberFixture({id:assetId,name:'A member '+index,current_version_id:currentVersion,current_version:{id:currentVersion,version_number:2}},{id:versionId},fixedVersion,index))
    send.mockResolvedValue(state('available'))
    get.mockImplementation(async (path: string) => path.includes('/members?') ? {items: members.slice(Number(new URL(path,'http://local').searchParams.get('offset')),Number(new URL(path,'http://local').searchParams.get('offset'))+Number(new URL(path,'http://local').searchParams.get('limit'))), total: members.length, limit: Number(new URL(path,'http://local').searchParams.get('limit')), offset: Number(new URL(path,'http://local').searchParams.get('offset'))} : state('available'))
    wrapper=mount(FixedDatasetMembers,{props:{workspaceId:'/test-workspace',datasetId:fixedDataset,versionId:fixedVersion,count:11}})
    expect(getBlob).not.toHaveBeenCalled()
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(wrapper.get('[aria-label="固定版本照片"]').findAll('li')).toHaveLength(10)
    expect(wrapper.text()).not.toContain('A member 10')
    await wrapper.get('button[aria-label="查看 A member 0 大图"]').trigger('click');await flushPromises()
    expect(send.mock.calls[0][0]).toContain('/versions/'+versionId+'/previews/display')
    expect(send.mock.calls[0][0]).not.toContain(currentVersion)
    const before=getBlob.mock.calls.length
    wrapper.getComponent(PhotoPreviewDialog).vm.$emit('updated',{assetId,versionId,title:'A member 0'})
    await flushPromises()
    expect(getBlob.mock.calls.length).toBe(before+1)
    await wrapper.get('button[aria-label="关闭大图预览"]').trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click');await flushPromises()
    expect(wrapper.get('[aria-label="固定版本照片"]').findAll('li')).toHaveLength(1)
    expect(wrapper.text()).toContain('A member 10')
    expect(wrapper.text()).not.toMatch(/管理成员|编辑成员/)
  })
})


it('keeps project dataset member browsing pinned to A while the current dataset is B',async()=>{
  vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}})
  const created='2026-10-22T20:00:00Z'
  const projectId='00000000-0000-4000-8000-000000000010'
  const datasetId='00000000-0000-4000-8000-000000000011'
  const datasetA='00000000-0000-4000-8000-000000000012'
  const datasetB='00000000-0000-4000-8000-000000000013'
  const asset={id:assetId,name:'Pinned A photo',scope:'shared',role:'raw',parameters:{},classification:{},revision:1,
    status:'active',created_at:created,current_version_id:'00000000-0000-4000-8000-000000000093',current_version:{id:'00000000-0000-4000-8000-000000000093'}}
  const pinned=fixedMemberFixture(asset,{id:versionId,asset_id:assetId,storage_mode:'managed',availability:'available'},datasetA,0)
  const group={id:datasetId,name:'Current B group',status:'active',notes:null,revision:2,current_version_id:datasetB,
    member_count:2,current_version_number:2,created_at:created,updated_at:created}
  const fixed={id:'00000000-0000-4000-8000-000000000094',added_at:created,project_id:projectId,dataset_id:datasetId,dataset_version_id:datasetA,base_revision:1,
    dataset:group,version:{id:datasetA,dataset_id:datasetId,version_number:1,created_at:created}}
  const summary = metadataForMembers([pinned])
  Object.assign(group, {summary, input_ready: true})
  Object.assign(fixed, {summary, input_ready: true, member_count: 1})
  const page=(items:unknown[])=>({items,total:items.length,limit:50,offset:0})
  get.mockImplementation(async(path:string)=>{
    if(path.endsWith('/capabilities'))return {stage:'ingestion',shared_library_read:true,project_assets_read:true,
      project_management:true,equipment_management:true,asset_import:true,
      asset_reference_write:true,asset_preview:true,asset_metadata_edit:true,dataset_management:true,
      asset_task_management:true,calibration_matching:false,asset_publish:false}
    if(path.includes('/projects/'+projectId+'/datasets'))return page([fixed])
    if(path.includes('/datasets/'+datasetId+'/versions/'+datasetA+'/members?'))return {...page([pinned]), limit: 10, offset: 0}
    if(path.includes('/projects?'))return page([{id:projectId,name:'Project',target_name:null,notes:null,revision:1,status:'active',created_at:created,updated_at:created}])
    if(path.includes('/datasets/'+datasetId+'/versions/'+datasetB))throw new Error('must not read the live B dataset')
    return page([])
  })
  send.mockResolvedValue(state('available'))
  wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
  await wrapper.findComponent(Workspace).vm.selectArea('settings','projects');await flushPromises()
  await wrapper.get('.apf-record').trigger('click');await flushPromises()
  await wrapper.findAll('.apf-details button').find(button=>button.text()==='查看项目图像组')!.trigger('click');await flushPromises()
  await vi.waitFor(()=>expect(wrapper!.findAll('button').some(button=>button.text()==='查看固定版本 · 1 张')).toBe(true))
  await wrapper.findAll('button').find(button=>button.text()==='查看固定版本 · 1 张')!.trigger('click');await flushPromises()
  expect(wrapper.get('[aria-label="固定版本照片"]').text()).toContain('Pinned A photo')
  await wrapper.get('[aria-label="固定版本照片"] button[aria-label="查看 Pinned A photo 大图"]').trigger('click');await flushPromises()
  expect(send.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/library/assets/'+assetId+'/versions/'+versionId+'/previews/display/auto-stretch')
  expect(get.mock.calls.every(([path])=>!String(path).includes('/versions/'+datasetB))).toBe(true)
})

it('uses the server media reference without rebuilding a route from identity fields',async()=>{
 send.mockResolvedValue(state('available'));get.mockResolvedValue(state('available'))
 wrapper=mount(PhotoPreviewDialog,{props:{workspaceId:'/test-workspace',photo:{...photo,basePath:'/checked/opaque-source'}}})
 await flushPromises()
 expect(send.mock.calls[0][0]).toBe('/checked/opaque-source/display/auto-stretch')
 expect(getBlob.mock.calls[0][0]).toBe('/checked/opaque-source/display')
})
