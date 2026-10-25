import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PhotoPreviewDialog from '@frontend/workspace/PhotoPreviewDialog.vue'
import FixedDatasetMembers from '@frontend/workspace/FixedDatasetMembers.vue'
import App from '@frontend/App.vue'
import { createPinia } from 'pinia'
import { displayPreviewSchema } from '@frontend/assets/contracts'

const { get, send, getBlob } = vi.hoisted(() => ({get:vi.fn(),send:vi.fn(),getBlob:vi.fn()}))
vi.mock('@frontend/assets/host-client',()=>({assetApi:{get,send,getBlob}}))
const assetId='00000000-0000-4000-8000-000000000001'
const versionId='00000000-0000-4000-8000-000000000002'
const photo={assetId,versionId,title:'Pinned photo'}
const state=(status:string,error:unknown=null)=>({asset_version_id:versionId,size:'display',status,width:status==='available'?1080:null,height:status==='available'?720:null,error})
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
  it('closes from the focused button inside a workspace that stops keyboard bubbling',async()=>{
    const host=document.createElement('div')
    document.body.append(host)
    host.addEventListener('keydown',event=>event.stopPropagation())
    send.mockResolvedValue(state('available'))
    try{
      wrapper=mount(PhotoPreviewDialog,{props:{photo},attachTo:host})
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
    wrapper=mount(PhotoPreviewDialog,{props:{photo}})
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('正在读取')
    await vi.advanceTimersByTimeAsync(500);await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
    expect(get).toHaveBeenCalledWith(expect.stringContaining('/versions/'+versionId+'/previews/display/status'),displayPreviewSchema)
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
    wrapper=mount(PhotoPreviewDialog,{props:{photo}});await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('原件尚未完成')
    await wrapper.findAll('button').find(button=>button.text()==='重试')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(wrapper.find('img').exists()).toBe(true)
  })
  it('ignores a late response after closing and cancels polling on unmount',async()=>{
    let resolve!:(value:unknown)=>void
    send.mockReturnValue(new Promise(done=>{resolve=done}))
    wrapper=mount(PhotoPreviewDialog,{props:{photo}})
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
    wrapper=mount(PhotoPreviewDialog,{props:{photo:{...photo,basePath}}});await flushPromises()
    expect(send.mock.calls[0][0]).toBe(basePath+'/display')
    expect(getBlob).toHaveBeenCalledWith(basePath+'/display')
  })
})

describe('project fixed version member browser',()=>{
  it('pages only pinned version members and previews A even when current versions are B',async()=>{
    const members=Array.from({length:11},(_,index)=>({id:'member-'+index,asset:{id:assetId,name:'A member '+index,current_version_id:'current-B'},version:{id:versionId}}))
    send.mockResolvedValue(state('available'))
    wrapper=mount(FixedDatasetMembers,{props:{members}})
    expect(getBlob).not.toHaveBeenCalled()
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(wrapper.get('[aria-label="固定版本照片"]').findAll('li')).toHaveLength(10)
    expect(wrapper.text()).not.toContain('A member 10')
    await wrapper.get('button[aria-label="查看 A member 0 大图"]').trigger('click');await flushPromises()
    expect(send.mock.calls[0][0]).toContain('/versions/'+versionId+'/previews/display')
    expect(send.mock.calls[0][0]).not.toContain('current-B')
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
    status:'active',created_at:created,current_version_id:'current-photo-B',current_version:{id:'current-photo-B'}}
  const pinned={id:'member-A',asset,version:{id:versionId,asset_id:assetId,storage_mode:'managed',availability:'available'}}
  const group={id:datasetId,name:'Current B group',status:'active',notes:null,revision:2,current_version_id:datasetB,
    member_count:2,created_at:created,updated_at:created}
  const fixed={id:'reference-A',project_id:projectId,dataset_id:datasetId,dataset_version_id:datasetA,base_revision:1,
    dataset:group,version:{id:datasetA,dataset_id:datasetId,version_number:1,members:[pinned],created_at:created}}
  const page=(items:unknown[])=>({items,total:items.length,limit:50,offset:0})
  get.mockImplementation(async(path:string)=>{
    if(path.endsWith('/capabilities'))return {stage:'ingestion',shared_library_read:true,project_assets_read:true,
      project_management:true,equipment_management:true,asset_import:true,
      asset_reference_write:true,asset_preview:true,asset_metadata_edit:true,dataset_management:true,
      asset_task_management:true,calibration_matching:false,asset_publish:false}
    if(path.includes('/projects/'+projectId+'/datasets'))return page([fixed])
    if(path.includes('/projects?'))return page([{id:projectId,name:'Project',revision:1,status:'active',created_at:created,updated_at:created}])
    if(path.includes('/datasets/'+datasetId+'/versions/'+datasetB))throw new Error('must not read the live B dataset')
    return page([])
  })
  send.mockResolvedValue(state('available'))
  wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
  await wrapper.get('nav button[aria-label="设置"]').trigger('click');await flushPromises()
  await wrapper.get('.apf-record').trigger('click');await flushPromises()
  await wrapper.findAll('.apf-details button').find(button=>button.text()==='查看项目数据集')!.trigger('click');await flushPromises()
  await wrapper.findAll('button').find(button=>button.text()==='查看固定版本 · 1 张')!.trigger('click');await flushPromises()
  expect(wrapper.get('[aria-label="固定版本照片"]').text()).toContain('Pinned A photo')
  await wrapper.get('[aria-label="固定版本照片"] button[aria-label="查看 Pinned A photo 大图"]').trigger('click');await flushPromises()
  expect(send.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/library/assets/'+assetId+'/versions/'+versionId+'/previews/display')
  expect(get.mock.calls.every(([path])=>!String(path).includes('/versions/'+datasetB))).toBe(true)
})
