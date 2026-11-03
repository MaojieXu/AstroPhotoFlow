import { zCameraSnapshot } from '@ui/generated/api/zod.gen'
import { libraryAsset as assetSummary, libraryDataset as datasetSummary, metadataForMembers, exposureForMembers } from '../../../fixtures/library-summary'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { focusManager } from '@tanstack/vue-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@ui/modules/data/api/client'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import ImportTasks from '@ui/modules/data/imports/ImportTasks.vue'
import PhotoPreviewDialog from '@ui/modules/data/media/PhotoPreviewDialog.vue'
import { useWorkspaceStore } from '@ui/modules/data/workspace/store'

const { get, getBlob, send } = vi.hoisted(() => ({ get: vi.fn(), getBlob: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), displayPreviewApi: (await import('../../../fixtures/library-api')).createDisplayPreviewApiFixture(get,send,getBlob), assetApi: { get, getBlob, send } }))

const capabilities = {
  stage: 'ingestion', shared_library_read: true, project_assets_read: true,
  project_management: true, equipment_management: true, asset_import: false, asset_reference_write: false, asset_preview: false,
  asset_metadata_edit: true, dataset_management: true, asset_task_management: true, calibration_matching: false, asset_publish: false
}
const emptyPage = { items: [], total: 0, limit: 50, offset: 0 }
const createdAt = '2026-10-22T20:00:00Z'
const project = {
  id: '1f740b2c-75f3-4f76-8f85-f08ade40a33f',
  name: 'M31', target_name: null, notes: null, status: 'active', revision: 1, created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:00Z'
}
const idAt = (index: number) => '00000000-0000-4000-8000-' + String(index).padStart(12, '0')
const libraryAsset = {
  id:idAt(500),name:'M31.fit',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,current_version_id:null,
  classification:{frame_class:'subframe',frame_type:'light'},
  parameters:{camera_id:null,optical_system_id:null,filter_id:null,parameter_mode:'standard',iso:null,gain:null,offset:null,
    exposure_seconds:null,integration_seconds:null,sensor_temperature_c:null,binning_x:null,binning_y:null,cfa_pattern:null},
  equipment_snapshot:{},value_sources:{},notes:null,status:'active',revision:1,created_at:'2026-10-22T20:00:00Z',current_version:null
}

const camera = {
  id:idAt(2500),kind:'camera',name:'Camera Alpha',model:'Alpha 1',notes:null,
  specs:{sensor_width_px:2048,sensor_height_px:1536,pixel_size_um:3.76,native_bit_depth:14,cfa_pattern:'RGGB'},
  status:'active',revision:1,created_at:'2026-10-22T20:00:00Z',updated_at:'2026-10-22T20:00:00Z'
}

const page = (items: unknown[], total = items.length, offset = 0, limit = 50) => ({ items, total, limit, offset })
const url = (path: string) => new URL(path, 'http://comfy.test')
async function clickDetail(element:Element,detail:number){
  element.dispatchEvent(new MouseEvent('click',{bubbles:true,detail}))
  await nextTick()
  if(detail===2){
    element.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}))
    await nextTick()
  }
}

let wrapper: ReturnType<typeof mount>
let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  pinia = createPinia()
  setActivePinia(pinia)
  vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}})
  get.mockReset()
  send.mockReset()
  getBlob.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

async function openSettings() {
  await wrapper.findComponent(Workspace).vm.selectArea('settings','projects')
  await flushPromises()
}

describe('first-stage regression fixes', () => {
  it('shows an initial connection error without claiming that the library is empty',async()=>{
    get.mockRejectedValue(new ApiClientError('Initial service unavailable','service',503,'SERVICE_UNAVAILABLE'))
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises()
    expect(wrapper.text()).toContain('资产服务当前不可用')
    expect(wrapper.text()).not.toContain('素材库还没有内容')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(0)
    expect(send).not.toHaveBeenCalled()
  })

  it('keeps the newly selected project revision after an older reference removal completes',async()=>{
    const firstProject={...project,name:'Project A',revision:4}
    const secondProject={...project,id:idAt(1700),name:'Project B',revision:17}
    const version={view_base: `/astrophotoflow/api/v1/library/assets/${libraryAsset.id}/versions/${idAt(1701)}/previews`, id:idAt(1701),asset_id:libraryAsset.id,version_number:1,storage_mode:'reference',storage_location:'test/member.fit',byte_size:1,content_hash:null,
      availability:'available',camera_id:null,optical_system_id:null,filter_id:null,frame_type:'light',calibration_level:null,capture_snapshot:null,scientific_metadata:null,created_at:createdAt}
    const asset={...libraryAsset,current_version_id:version.id,current_version:version}
    const reference={view_base: `/astrophotoflow/api/v1/projects/${firstProject.id}/asset-references/${idAt(1702)}/previews`, id:idAt(1702),project_id:firstProject.id,asset_version_id:version.id,added_at:createdAt,asset,version}
    let finish!: (value:unknown)=>void
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      const name=url(path).pathname
      if(name.endsWith('/projects'))return page([firstProject,secondProject])
      if(name.endsWith('/projects/'+firstProject.id+'/assets'))return page([reference])
      return emptyPage
    })
    send.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises();await openSettings()
    await wrapper.findAll('.apf-record').find(item=>item.text().includes('Project A'))!.trigger('click');await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='查看项目素材')!.trigger('click');await flushPromises()
    await wrapper.get('.apf-assets-table tbody tr').trigger('click');await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='从项目移除')!.trigger('click');await flushPromises()
    const pending=wrapper.findAll('.apf-details button').find(button=>button.text()==='从项目移除')!
    expect(pending.attributes('disabled')).toBeDefined()
    await wrapper.findComponent(Workspace).vm.selectArea('settings','projects');await flushPromises()
    await wrapper.findAll('.apf-record').find(item=>item.text().includes('Project B'))!.trigger('click');await flushPromises()
    const store=useWorkspaceStore(pinia)
    expect(store.activeProjectRevision).toBe(17)
    finish({deleted_id:reference.id,revision:5});await flushPromises()
    expect(store.activeProjectId).toBe(secondProject.id)
    expect(store.activeProjectRevision).toBe(17)
    expect(send).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.apf-details').text()).toContain('Project B')
  })

  it('renders each material equipment snapshot independently from the current registry',async()=>{
    const materials=['Old camera name','Later camera name'].map((name,index)=>({
      ...libraryAsset,id:idAt(510+index),name:'Photo '+index,
      parameters:{...libraryAsset.parameters,camera_id:camera.id},
      equipment_snapshot:{camera_id:{...camera,name}},
    }))
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page(materials.map(asset=>(assetSummary(asset))))
      if(url(path).pathname.endsWith('/equipment'))return page([{...camera,name:'Current registry name'}])
      return emptyPage
    })
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr td:nth-child(4)').map(cell=>cell.text())).toEqual(['Old camera name','Later camera name'])
  })

  it('uses the pinned equipment snapshot when viewing a project asset reference',async()=>{
    const version={view_base: `/astrophotoflow/api/v1/library/assets/${libraryAsset.id}/versions/${idAt(520)}/previews`, id:idAt(520),asset_id:libraryAsset.id,version_number:1,storage_mode:'managed',storage_location:'objects/source.png',
      byte_size:1,content_hash:null,availability:'available',camera_id:camera.id,optical_system_id:null,filter_id:null,
      frame_type:'light',calibration_level:null,capture_snapshot:{equipment_snapshot:{camera_id:zCameraSnapshot.strip().parse({...camera,name:'Pinned camera name'})}},scientific_metadata:{},created_at:createdAt}
    const asset={...libraryAsset,current_version_id:version.id,current_version:version,
      parameters:{...libraryAsset.parameters,camera_id:camera.id},equipment_snapshot:{camera_id:zCameraSnapshot.strip().parse({...camera,name:'Edited material name'})}}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(url(path).pathname.endsWith('/projects'))return page([project])
      if(url(path).pathname.endsWith('/assets'))return page([{view_base: `/astrophotoflow/api/v1/projects/${project.id}/asset-references/${idAt(521)}/previews`, id:idAt(521),project_id:project.id,asset_version_id:version.id,added_at:createdAt,asset,version}])
      if(url(path).pathname.endsWith('/equipment'))return page([{...camera,name:'Current registry name'}])
      return emptyPage
    })
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises();await openSettings()
    await wrapper.get('.apf-record').trigger('click');await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='查看项目素材')!.trigger('click');await flushPromises()
    expect(wrapper.get('.apf-assets-table tbody tr td:nth-child(4)').text()).toBe('Pinned camera name')
  })

  it('loads the latest page after an inline save finishes',async()=>{
    let finishPatch!: (value: unknown) => void
    const pageOne=assetSummary(libraryAsset)
    const pageTwo={...libraryAsset,id:idAt(501),name:'Page two.fit'}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return new URL(path,'http://comfy.test').searchParams.get('offset')==='0'
        ? page([pageOne],60,0):page([assetSummary(pageTwo)],60,50)
      return emptyPage
    })
    send.mockReturnValue(new Promise(resolve=>{finishPatch=resolve}))
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    const value=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value')
    await clickDetail(value.element,2)
    const input=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await input.setValue('Renamed.fit')
    await input.trigger('keydown',{key:'Enter'})
    await nextTick()
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click')
    await nextTick()
    expect(get.mock.calls.filter(([path])=>String(path).includes('/library/items'))).toHaveLength(1)
    finishPatch({...libraryAsset,name:'Renamed.fit',revision:2})
    await flushPromises()
    const libraryCalls=get.mock.calls.filter(([path])=>String(path).includes('/library/items'))
    expect(libraryCalls).toHaveLength(2)
    expect(new URL(libraryCalls[1][0] as string,'http://comfy.test').searchParams.get('offset')).toBe('50')
    expect(wrapper.get('.apf-assets-table tbody tr').text()).toContain('Page two.fit')
    expect(wrapper.text()).not.toContain('正在搜索')
  })

  it.each(['cancel','retry'])('reloads a search after a failed inline save is resolved by %s',async recovery=>{
    const filteredAsset={...libraryAsset,name:'M31 filtered.fit',revision:2}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(url(path).searchParams.has('q')?filteredAsset:libraryAsset)])
      return emptyPage
    })
    send.mockRejectedValueOnce(new ApiClientError('保存失败','service',500,'INTERNAL_ERROR'))
      .mockResolvedValueOnce({...libraryAsset,name:'Renamed.fit',revision:2})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await clickDetail(wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value').element,2)
    const input=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await input.setValue('Renamed.fit')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.text()).toContain('保存失败')

    await wrapper.get('input[aria-label="搜索"]').setValue('M31')
    await new Promise(resolve=>setTimeout(resolve,300))
    await flushPromises()
    expect(get.mock.calls.filter(([path])=>String(path).includes('/library/items'))).toHaveLength(1)
    expect(wrapper.text()).not.toContain('正在读取服务数据')
    expect(wrapper.get<HTMLInputElement>('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]').element.value).toBe('Renamed.fit')

    await input.trigger('keydown',{key:recovery==='cancel'?'Escape':'Enter'})
    await flushPromises()
    const calls=get.mock.calls.filter(([path])=>String(path).includes('/library/items'))
    expect(calls).toHaveLength(2)
    expect(url(calls[1][0] as string).searchParams.get('q')).toBe('M31')
    expect(wrapper.get('.apf-assets-table tbody tr').text()).toContain('M31 filtered.fit')
    expect(wrapper.text()).not.toContain('保存失败')
    expect(wrapper.text()).not.toContain('正在读取服务数据')
    expect(send).toHaveBeenCalledTimes(recovery==='cancel'?1:2)
  })

  it('opens a lazy display preview when its thumbnail is clicked',async()=>{
    const version={view_base: `/astrophotoflow/api/v1/library/assets/${libraryAsset.id}/versions/${idAt(502)}/previews`, id:idAt(502),asset_id:libraryAsset.id,version_number:1,availability:'available',storage_mode:'reference',metadata_status:'ready',preview_status:'ready',created_at:createdAt}
    const asset={...libraryAsset,current_version:version,current_version_id:version.id}
    get.mockImplementation(async(path:string)=>path.endsWith('/capabilities')?capabilities:path.includes('/library/items')?page([assetSummary(asset)]):emptyPage)
    getBlob.mockResolvedValue(new Blob(['thumb'],{type:'image/jpeg'}))
    Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=>'blob:thumb')})
    Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    const thumb=wrapper.get('.apf-assets-table .apf-thumb')
    expect(thumb.element.tagName).toBe('BUTTON')
    expect(thumb.get('img').attributes('src')).toBe('blob:thumb')
    const requests=getBlob.mock.calls.length
    send.mockResolvedValue({asset_version_id:version.id,size:'display',status:'available',width:240,height:160,error:null,
      stretch:{algorithm:'auto-mtf-1',input_offset:0,white_balance:[1],shadows:0,highlights:255,midtones:.2}})
    await thumb.trigger('click')
    await flushPromises()
    expect(getBlob).toHaveBeenCalledTimes(requests+2)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(send.mock.calls[0][0]).toContain('/versions/'+version.id+'/previews/display')
    wrapper.getComponent(PhotoPreviewDialog).vm.$emit('updated',{assetId:asset.id,versionId:version.id,title:asset.name})
    await flushPromises()
    expect(getBlob).toHaveBeenCalledTimes(requests+3)
    expect(getBlob).toHaveBeenLastCalledWith('/astrophotoflow/api/v1/library/assets/'+asset.id+'/versions/'+version.id+'/previews/thumbnail', expect.any(AbortSignal))
    await wrapper.get('button[aria-label="关闭大图预览"]').trigger('click')
    await flushPromises()
  })

  it('selects a library row with one click and edits an enum value on double-click',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(libraryAsset)])
      return emptyPage
    })
    send.mockResolvedValue({...libraryAsset,classification:{frame_class:'masterframe',frame_type:'light'},revision:2})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    const fieldSelector='.apf-assets-table tbody tr td:nth-child(3) .apf-inline-value'
    const field=wrapper.get(fieldSelector).element
    await clickDetail(field,1)
    await flushPromises()
    expect(wrapper.get('.apf-assets-table tbody tr').attributes('aria-selected')).toBe('true')
    await clickDetail(wrapper.get(fieldSelector).element,2)
    await flushPromises()
    const editor=wrapper.get('.apf-assets-table tbody tr td:nth-child(3) select')
    expect((editor.element as HTMLSelectElement).value).toBe('subframe')
    await editor.setValue('masterframe')
    await editor.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/library/assets/'+libraryAsset.id,expect.anything(),'PATCH',{
      base_revision:1,classification:{frame_class:'masterframe'}
    })
  })

  it('opens the registered camera choices from the library field and saves its ID',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(libraryAsset)])
      if(path.includes('/equipment?'))return page([camera])
      return emptyPage
    })
    send.mockResolvedValue({...libraryAsset,parameters:{...libraryAsset.parameters,camera_id:camera.id},revision:2})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    const selector='.apf-assets-table tbody tr td:nth-child(4) .apf-inline-value'
    await clickDetail(wrapper.get(selector).element,1)
    await clickDetail(wrapper.get(selector).element,2)
    const select=wrapper.get('.apf-assets-table tbody tr td:nth-child(4) select')
    expect(select.find('option[value="'+camera.id+'"]').text()).toBe('Camera Alpha')
    await select.setValue(camera.id)
    await select.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/library/assets/'+libraryAsset.id,expect.anything(),'PATCH',{
      base_revision:1,parameters:{camera_id:camera.id}
    })
  })

  it('shows why a camera selector is empty when no camera has been registered',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(libraryAsset)])
      if(path.includes('/equipment?'))return emptyPage
      return emptyPage
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    const selector='.apf-assets-table tbody tr td:nth-child(4) .apf-inline-value'
    await clickDetail(wrapper.get(selector).element,1)
    await clickDetail(wrapper.get(selector).element,2)
    expect(wrapper.get('.apf-assets-table tbody tr td:nth-child(4) select').text()).toContain('尚未登记相机')
  })

  it('saves equipment numbers with their original typed value',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/equipment?'))return page([camera])
      return emptyPage
    })
    send.mockResolvedValue({...camera,specs:{...camera.specs,sensor_width_px:4096},revision:2})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await openSettings()
    await wrapper.findComponent(Workspace).vm.selectArea('settings', 'equipment')
    await flushPromises()
    await wrapper.get('.apf-record').trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='编辑')!.trigger('click')
    await flushPromises()
    const form=wrapper.get('form[aria-label="记录编辑表单"]')
    const widthField=form.findAll('label').find(label=>label.text().startsWith('图像宽度'))!
    const width=widthField.get('input[type="number"]')
    expect((width.element as HTMLInputElement).value).toBe('2048')
    await width.setValue('4096')
    expect(send).not.toHaveBeenCalled()
    await form.trigger('submit')
    await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/equipment/'+camera.id,expect.anything(),'PATCH',{
      base_revision:1,kind:'camera',specs:{sensor_width_px:4096}
    })
  })





  it('keeps an existing non-square Bin until a new Bin is selected',async()=>{
    const asset={...libraryAsset,parameters:{...libraryAsset.parameters,binning_x:1,binning_y:2}}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(asset)])
      return emptyPage
    })
    send.mockResolvedValue({...asset,parameters:{...asset.parameters,binning_x:3,binning_y:3},revision:2})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.get('select[aria-label="显示方式"]').setValue('detail')
    const binSelector='.apf-assets-table tbody tr td:nth-child(8)'
    await wrapper.get(binSelector+' .apf-inline-value').trigger('dblclick')
    let editor=wrapper.get(binSelector+' select')
    expect((editor.element as HTMLSelectElement).value).toBe('legacy:1x2')
    expect(editor.find('option[value="Bin16"]').exists()).toBe(true)
    expect(editor.find('option[value="legacy:1x2"]').text()).toContain('现有值')
    await editor.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(send).not.toHaveBeenCalled()

    await wrapper.get(binSelector+' .apf-inline-value').trigger('dblclick')
    editor=wrapper.get(binSelector+' select')
    await editor.setValue('Bin3')
    await editor.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/library/assets/'+asset.id,expect.anything(),'PATCH',{
      base_revision:1,parameters:{binning_x:3,binning_y:3}
    })
  })

  it('preserves library state and edits a mixed dataset Bin through its raw value',async()=>{
    const createdAt='2026-10-22T20:00:00Z'
    const datasetId=idAt(700),versionId=idAt(701)
    const members=[1,2].map((bin,index)=>{
      const assetId=idAt(710+index),assetVersionId=idAt(720+index)
      const version={view_base: `/astrophotoflow/api/v1/library/assets/${assetId}/versions/${assetVersionId}/previews`, id:assetVersionId,asset_id:assetId,version_number:1,storage_mode:'reference',storage_location:'roots/science/'+index+'.fits',
        byte_size:1,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,filter_id:null,frame_type:'light',calibration_level:null,capture_snapshot:null,scientific_metadata:null,created_at:createdAt}
      const asset={...libraryAsset,id:assetId,name:'Member '+index+'.fits',current_version_id:assetVersionId,
        parameters:{...libraryAsset.parameters,binning_x:bin,binning_y:bin},current_version:version}
      return {id:idAt(730+index),dataset_version_id:versionId,asset_version_id:assetVersionId,position:index,relative_path:null,asset,version}
    })
    const dataset={id:datasetId,name:'M31 set',notes:null,status:'active',revision:1,current_version_id:versionId,member_count:2,created_at:createdAt,updated_at:createdAt}
    const version={id:versionId,dataset_id:datasetId,version_number:1,created_at:createdAt,members}
    const filterOptions={frame_classes:['subframe'],frame_types:['light'],roles:['raw'],parameter_modes:['standard'],bin_values:['1x1','2x2'],
      equipment:{camera_id:[],optical_system_id:[],filter_id:[]},numeric_ranges:{}}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([datasetSummary(dataset,version,members.length)])
      if(url(path).pathname.endsWith('/members'))return page(members)
      if(path.endsWith('/library/filter-options'))return filterOptions
      return emptyPage
    })
    send.mockResolvedValue({dataset_id:datasetId,revision:1,version_id:versionId,assets:members.map(member=>member.asset)})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    expect(wrapper.get('.apf-table-scroll').classes()).toContain('simple')
    await wrapper.get('input[aria-label="搜索"]').setValue('M31')
    await new Promise(resolve=>setTimeout(resolve,300))
    await flushPromises()
    const filterButton=wrapper.findAll('button').find(button=>button.text().startsWith('筛选'))!
    await filterButton.trigger('click')
    await flushPromises()
    const frameClass=wrapper.findAll('input[type="checkbox"]').find(input=>input.element.parentElement?.textContent?.includes('单帧'))!
    await frameClass.setValue(true)
    await flushPromises()
    await wrapper.get('select[aria-label="显示方式"]').setValue('detail')
    expect(wrapper.get('.apf-table-scroll').classes()).toContain('detail')
    expect((wrapper.get('input[aria-label="搜索"]').element as HTMLInputElement).value).toBe('M31')
    expect(wrapper.findAll('button').find(button=>button.text().startsWith('筛选'))!.text()).toBe('筛选（1）')
    expect(wrapper.get('.apf-assets-table tbody tr').attributes('aria-selected')).toBe('false')
    expect(wrapper.find('.apf-filter-panel').exists()).toBe(true)

    const binSelector='.apf-assets-table tbody tr td:nth-child(8) .apf-inline-value'
    await clickDetail(wrapper.get(binSelector).element,1)
    await clickDetail(wrapper.get(binSelector).element,2)
    const binEditor=wrapper.get('.apf-assets-table tbody tr td:nth-child(8) select')
    expect((binEditor.element as HTMLSelectElement).value).toBe('mixed')
    await binEditor.setValue('Bin3')
    await binEditor.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/datasets/'+datasetId+'/member-parameters',expect.anything(),'PATCH',{
      base_revision:1,base_version_id:versionId,members:members.map(member=>({asset_id:member.asset.id,revision:1})),
      parameters:{binning_x:3,binning_y:3}
    })
  })



  it('keeps a failed inline draft when a create action is requested',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/projects?'))return page([project])
      return emptyPage
    })
    send.mockRejectedValue(new Error('revision conflict'))
    wrapper=mount(App,{attachTo:document.body,global:{plugins:[pinia]}})
    await flushPromises()
    await openSettings()
    await wrapper.get('.apf-record').trigger('click')
    await flushPromises()
    const openEditor=wrapper.findAll('button').find(button=>button.text()==='编辑项目')!
    await openEditor.trigger('click')
    await flushPromises()
    const nameButton=wrapper.findAll('.apf-editor .apf-inline-value').find(button=>button.element.parentElement?.parentElement?.textContent?.startsWith('名称'))!
    const nameButtonElement=nameButton.element as HTMLElement
    nameButtonElement.focus()
    await clickDetail(nameButton.element,2)
    const nameInput=wrapper.get('.apf-editor input[type="text"]')
    await nameInput.setValue('M42')
    const createButton=wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='新建项目')!
    const createButtonElement=createButton.element as HTMLElement
    createButtonElement.focus()
    await createButton.trigger('click')
    await flushPromises()

    expect(wrapper.get('.apf-editor h2').text()).toBe('编辑项目')
    expect((wrapper.get('.apf-editor input[type="text"]').element as HTMLInputElement).value).toBe('M42')
    expect(wrapper.text()).toContain('revision conflict')
    expect(send).toHaveBeenCalledOnce()

    await wrapper.get('.apf-editor input[type="text"]').trigger('keydown',{key:'Escape'})
    await flushPromises()
    await createButton.trigger('click')
    await flushPromises()
    expect(wrapper.get('.apf-editor h2').text()).toBe('创建项目')
  })

  it('keeps a failed field draft protected when another field is cancelled',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(libraryAsset)])
      return emptyPage
    })
    send.mockRejectedValue(new Error('revision conflict'))
    wrapper=mount(App,{attachTo:document.body,global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody tr').trigger('click')
    await flushPromises()
    const name=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value')
    await clickDetail(name.element,2)
    const nameInput=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await nameInput.setValue('M42')
    await nameInput.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.text()).toContain('revision conflict')

    const camera=wrapper.get('.apf-assets-table tbody tr td:nth-child(4) .apf-inline-value')
    await clickDetail(camera.element,2)
    await flushPromises()
    const cameraSelect=wrapper.get('.apf-assets-table tbody tr td:nth-child(4) select')
    await cameraSelect.trigger('keydown',{key:'Escape'})
    await flushPromises()
    await wrapper.get('.apf-nav button[aria-label="设备管理"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('.apf-nav button[aria-label="素材库"]').attributes('aria-current')).toBe('page')
    expect(wrapper.text()).toContain('revision conflict')
  })

  it('releases a dataset inline failure after cancelling its draft',async()=>{
    const versionId=idAt(700)
    const datasetVersion={id:versionId,dataset_id:idAt(701),version_number:1,created_at:createdAt,members:[]}
    const dataset={id:idAt(701),name:'Group',notes:null,status:'active',revision:1,current_version_id:versionId,
      member_count:0,current_version_number:1,summary:metadataForMembers([]),exposure_summary:exposureForMembers([]),input_ready:false,created_at:createdAt,updated_at:createdAt}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([datasetSummary(dataset,datasetVersion,datasetVersion.members.length)])
      if(path.endsWith('/datasets/'+dataset.id))return dataset
      if(url(path).pathname.endsWith('/versions/'+versionId+'/members'))return page(datasetVersion.members)
      return emptyPage
    })
    send.mockRejectedValue(new Error('revision conflict'))
    vi.stubGlobal('confirm',()=>true)
    wrapper=mount(App,{attachTo:document.body,global:{plugins:[pinia]}})
    await flushPromises()
    await clickDetail(wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value').element,2)
    const nameInput=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await nameInput.setValue('Changed')
    await nameInput.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.text()).toContain('revision conflict')

    expect((nameInput.element as HTMLInputElement).value).toBe('Changed')
    await nameInput.trigger('keydown',{key:'Escape'})
    await flushPromises()
    await wrapper.get('.apf-nav button[aria-label="设备管理"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('.apf-nav button[aria-label="设备管理"]').attributes('aria-current')).toBe('page')
  })

  it('refreshes the parent library row after a successful dataset field save',async()=>{
    const datasetId=idAt(720)
    const versionId=idAt(721)
    const version={id:versionId,dataset_id:datasetId,version_number:1,created_at:createdAt,members:[]}
    let dataset={id:datasetId,name:'Old name',notes:null,status:'active',revision:1,current_version_id:versionId,
      member_count:0,current_version_number:1,summary:metadataForMembers([]),exposure_summary:exposureForMembers([]),input_ready:false,created_at:createdAt,updated_at:createdAt}
    const item=()=>(datasetSummary(dataset,version,version.members.length))
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([item()])
      if(path.endsWith('/datasets/'+datasetId))return dataset
      if(url(path).pathname.endsWith('/versions/'+versionId+'/members'))return page(version.members)
      return emptyPage
    })
    send.mockImplementation(async()=>{
      dataset={...dataset,name:'New name',revision:2}
      return dataset
    })
    wrapper=mount(App,{attachTo:document.body,global:{plugins:[pinia]}})
    await flushPromises()
    await clickDetail(wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value').element,2)
    const nameInput=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await nameInput.setValue('New name')
    await nameInput.trigger('keydown',{key:'Enter'})
    await flushPromises()

    expect(wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value').text()).toBe('New name')
  })

  it('uses the saved dataset revision for batch removal after automatic summary refresh',async()=>{
    const datasetId=idAt(722)
    const versionId=idAt(723)
    const version={id:versionId,dataset_id:datasetId,version_number:1,created_at:createdAt,members:[]}
    let dataset={id:datasetId,name:'Old name',notes:null,status:'active',revision:1,current_version_id:versionId,
      member_count:0,current_version_number:1,summary:metadataForMembers([]),exposure_summary:exposureForMembers([]),input_ready:false,created_at:createdAt,updated_at:createdAt}
    let removed=false
    const item=()=>(datasetSummary(dataset,version,version.members.length))
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return removed?page([],0):page([item()])
      return emptyPage
    })
    send.mockImplementation(async(path:string,_schema:unknown,method:string,body:Record<string,any>)=>{
      if(method==='PATCH'){
        expect(path).toBe('/astrophotoflow/api/v1/datasets/'+datasetId)
        expect(body.base_revision).toBe(1)
        dataset={...dataset,name:'New name',revision:2}
        return dataset
      }
      expect(path).toBe('/astrophotoflow/api/v1/library/items')
      expect(method).toBe('DELETE')
      expect(body.items).toEqual([{entry_type:'dataset',id:datasetId,revision:2,current_version_id:versionId}])
      removed=true
      return {removed_count:1}
    })
    wrapper=mount(App,{attachTo:document.body,global:{plugins:[pinia]}})
    await flushPromises()
    const name=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value')
    await clickDetail(name.element,2)
    const input=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await input.setValue('New name')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value').text()).toBe('New name')
    expect(get.mock.calls.filter(([path])=>path.includes('/library/items'))).toHaveLength(2)

    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 New name"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='删除')!.trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='移入回收站')!.trigger('click')
    await flushPromises()
    expect(send.mock.calls.map(([, , method])=>method)).toEqual(['PATCH','DELETE'])
    expect(wrapper.text()).toContain('已移除1条素材库记录')
  })

  it('keeps a renamed dataset selected when a later external revision makes removal stale',async()=>{
    const datasetId=idAt(724)
    const versionId=idAt(725)
    const version={id:versionId,dataset_id:datasetId,version_number:1,created_at:createdAt,members:[]}
    let dataset={id:datasetId,name:'Old name',notes:null,status:'active',revision:1,current_version_id:versionId,
      member_count:0,current_version_number:1,summary:metadataForMembers([]),exposure_summary:exposureForMembers([]),input_ready:false,created_at:createdAt,updated_at:createdAt}
    const item=()=>(datasetSummary(dataset,version,version.members.length))
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([item()])
      return emptyPage
    })
    send.mockImplementation(async(path:string,_schema:unknown,method:string,body:Record<string,any>)=>{
      if(method==='PATCH'){
        dataset={...dataset,name:'New name',revision:2}
        return dataset
      }
      expect(body.items).toEqual([{entry_type:'dataset',id:datasetId,revision:2,current_version_id:versionId}])
      dataset={...dataset,revision:3}
      throw new ApiClientError('记录已变化，请重新读取。','service',409,'REVISION_CONFLICT')
    })
    wrapper=mount(App,{attachTo:document.body,global:{plugins:[pinia]}})
    await flushPromises()
    await clickDetail(wrapper.get('.apf-assets-table tbody tr td:nth-child(2) .apf-inline-value').element,2)
    const input=wrapper.get('.apf-assets-table tbody tr td:nth-child(2) input[type="text"]')
    await input.setValue('New name')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 New name"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='删除')!.trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='移入回收站')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('记录已被其他窗口修改。')
    expect((wrapper.get('input[aria-label="选择 New name"]').element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.get('.apf-assets-table tbody tr').text()).toContain('New name')
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

    await wrapper.findComponent(Workspace).vm.selectArea('settings', 'equipment')
    await flushPromises()

    expect(wrapper.text()).toContain('资产服务未连接，请检查服务是否运行')
    expect(wrapper.findAll('.apf-record')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('M31')
    expect(wrapper.text()).not.toContain('此处目前没有记录')
  })

  it('resets search pages to offset zero', async () => {
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

  it('sorts library columns on the server and resets the current page', async () => {
    const row = assetSummary(libraryAsset)
    const filterOptions={frame_classes:['subframe'],frame_types:['light'],roles:['raw'],parameter_modes:['standard'],bin_values:[],
      equipment:{camera_id:[],optical_system_id:[],filter_id:[]},numeric_ranges:{}}
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.endsWith('/library/filter-options')) return filterOptions
      if (path.includes('/library/items')) {
        const request = url(path)
        return page([row], 60, Number(request.searchParams.get('offset')))
      }
      return emptyPage
    })
    const store = useWorkspaceStore(pinia)
    store.offset = 50
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    expect(wrapper.text()).toContain('已选 1 项')
    expect((wrapper.get('input[aria-label="选择 M31.fit"]').element as HTMLInputElement).checked).toBe(true)

    await wrapper.get('.apf-sort-button').trigger('click')
    await flushPromises()
    expect((wrapper.get('input[aria-label="选择 M31.fit"]').element as HTMLInputElement).checked).toBe(false)
    let request = get.mock.calls.map(([path]) => url(path)).filter(value => value.pathname.endsWith('/library/items')).at(-1)!
    expect(request.searchParams.get('sort_by')).toBe('name')
    expect(request.searchParams.get('order')).toBe('asc')
    expect(request.searchParams.get('offset')).toBe('0')
    expect(wrapper.get('th[aria-sort="ascending"] .apf-sort-button').text()).toContain('▲')

    store.offset=50
    await flushPromises()
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    await wrapper.get('input[aria-label="搜索"]').setValue('M31')
    await new Promise(resolve=>setTimeout(resolve,300))
    await flushPromises()
    expect((wrapper.get('input[aria-label="选择 M31.fit"]').element as HTMLInputElement).checked).toBe(false)
    await wrapper.findAll('button').find(button=>button.text().startsWith('筛选'))!.trigger('click')
    await flushPromises()
    const classChoice=wrapper.findAll('input[type="checkbox"]').find(input=>input.element.parentElement?.textContent?.includes('单帧'))!
    await classChoice.setValue(true)
    await flushPromises()

    await wrapper.get('.apf-sort-button').trigger('click')
    await flushPromises()
    request = get.mock.calls.map(([path]) => url(path)).filter(value => value.pathname.endsWith('/library/items')).at(-1)!
    expect(request.searchParams.get('order')).toBe('desc')
    expect(wrapper.get('th[aria-sort="descending"] .apf-sort-button').text()).toContain('▼')
  })

  it('uses the updated active project revision when adding a reference after an inline project edit', async () => {
    const versionId = idAt(501)
    const datasetId = idAt(503)
    const datasetVersionId = idAt(504)
    const version = {view_base: `/astrophotoflow/api/v1/library/assets/${libraryAsset.id}/versions/${versionId}/previews`,
      id:versionId,asset_id:libraryAsset.id,version_number:1,storage_mode:'reference',storage_location:'raw/M31.fit',
      byte_size:100,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,filter_id:null,
      frame_type:'light',calibration_level:null,capture_snapshot:null,scientific_metadata:null,created_at:createdAt
    }
    const addableAsset = {...libraryAsset,current_version_id:versionId,current_version:version}
    const datasetVersion = {id:datasetVersionId,dataset_id:datasetId,version_number:1,created_at:createdAt,members:[]}
    const dataset = {id:datasetId,name:'Project dataset',notes:null,status:'active',revision:1,current_version_id:datasetVersionId,
      member_count:0,current_version_number:1,summary:metadataForMembers([]),exposure_summary:exposureForMembers([]),input_ready:false,created_at:createdAt,updated_at:createdAt}
    Object.assign(dataset, {summary: metadataForMembers([]), input_ready: false})
    const assetReference = {view_base: `/astrophotoflow/api/v1/projects/${project.id}/asset-references/${idAt(502)}/previews`, id:idAt(502),project_id:project.id,asset_version_id:versionId,added_at:createdAt,asset:addableAsset,version}
    const datasetReference = {id:idAt(505),project_id:project.id,dataset_id:datasetId,dataset_version_id:datasetVersionId,
      base_revision:4,added_at:createdAt,dataset,version:{id:datasetVersionId,dataset_id:datasetId,version_number:1,created_at:createdAt,exposure_summary:exposureForMembers([])}}
    let currentProject=project
    let assetReferenced=false
    let datasetReferenced=false
    Object.assign(datasetReference, {summary: metadataForMembers([]), input_ready: false, member_count: 0})
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      const request = url(path)
      if (request.pathname === '/astrophotoflow/api/v1/projects') return page([currentProject])
      if (request.pathname === '/astrophotoflow/api/v1/library/assets') return page([addableAsset])
      if (request.pathname === '/astrophotoflow/api/v1/datasets') return page([dataset])
      if (request.pathname === '/astrophotoflow/api/v1/projects/'+project.id+'/assets') return assetReferenced?page([assetReference]):emptyPage
      if (request.pathname === '/astrophotoflow/api/v1/projects/'+project.id+'/datasets') return datasetReferenced?page([datasetReference]):emptyPage
      return emptyPage
    })
    send.mockImplementation(async (path: string, _schema: unknown, method: string, body: Record<string, any>) => {
      if (path === '/astrophotoflow/api/v1/projects/'+project.id&&method==='PATCH') {
        currentProject={...currentProject,name:body.name??currentProject.name,revision:currentProject.revision+1}
        return currentProject
      }
      if (path === '/astrophotoflow/api/v1/projects/'+project.id+'/asset-references'&&method==='POST') {
        assetReferenced=true
        currentProject={...currentProject,revision:body.base_revision+1}
        return assetReference
      }
      if (path === '/astrophotoflow/api/v1/projects/'+project.id+'/asset-references/'+assetReference.id&&method==='DELETE') {
        assetReferenced=false
        currentProject={...currentProject,revision:body.base_revision+1}
        return {deleted_id:assetReference.id,revision:body.base_revision+1}
      }
      if (path === '/astrophotoflow/api/v1/projects/'+project.id+'/dataset-references'&&method==='POST') {
        datasetReferenced=true
        currentProject={...currentProject,revision:body.base_revision+1}
        return datasetReference
      }
      if (path === '/astrophotoflow/api/v1/projects/'+project.id+'/dataset-references/'+datasetReference.id&&method==='DELETE') {
        datasetReferenced=false
        currentProject={...currentProject,revision:body.base_revision+1}
        return {deleted_id:datasetReference.id,revision:body.base_revision+1}
      }
      throw new Error('Unexpected write '+method+' '+path+' '+JSON.stringify(body))
    })
    wrapper = mount(App, { attachTo: document.body, global: { plugins: [pinia] } })
    await flushPromises()
    await openSettings()
    await wrapper.get('.apf-record').trigger('click')
    await flushPromises()
    const name = wrapper.get('.apf-details .apf-inline-value')
    await clickDetail(name.element, 2)
    await wrapper.get('.apf-details input[type="text"]').setValue('M42')
    await wrapper.get('.apf-details input[type="text"]').trigger('keydown', {key:'Enter'})
    await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='查看项目素材')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='添加素材')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody tr').trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='选用此素材版本')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody tr').trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='从项目移除')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-toolbar button').trigger('click')
    await flushPromises()
    await wrapper.get('.apf-record').trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='查看项目图像组')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='添加图像组')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody tr').trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='选用此图像组版本')!.trigger('click')
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody tr').trigger('click')
    await flushPromises()
    await wrapper.findAll('.apf-details button').find(button=>button.text()==='从项目移除图像组')!.trigger('click')
    await flushPromises()

    expect(send.mock.calls[0][3]).toMatchObject({base_revision:1,name:'M42'})
    expect(send.mock.calls[1][3]).toMatchObject({base_revision:2,asset_version_id:versionId})
    expect(send.mock.calls[2][3]).toMatchObject({base_revision:3})
    expect(send.mock.calls[3][3]).toMatchObject({base_revision:4,dataset_id:datasetId,dataset_version_id:datasetVersionId})
    expect(send.mock.calls[4][3]).toMatchObject({base_revision:5})
  })

  it('removes selected library rows while retaining a clear non-destructive explanation', async () => {
    const row = assetSummary(libraryAsset)
    const otherAsset={...libraryAsset,id:idAt(501),name:'M42.fit'}
    const otherRow=assetSummary(otherAsset)
    const task={id:idAt(502),status:'running',sources:[],storage_mode:'managed',classification:{},parameters:{},notes:null,
      dataset_name:'导入中',target_dataset_id:null,dataset_base_revision:null,dataset_id:null,enumeration_completed:true,
      retry_of_task_id:null,report:{},error:null,created_at:createdAt,updated_at:createdAt,items:[],items_total:1,
      items_completed:0,items_limit:20,items_offset:0}
    let removed = false
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/asset-tasks')) return page([task])
      if (path.includes('/library/items')) return removed ? page([otherRow],1) : page([row,otherRow])
      return emptyPage
    })
    send.mockImplementation(async (path: string, _schema: unknown, method: string, body: Record<string, any>) => {
      expect(path).toBe('/astrophotoflow/api/v1/library/items')
      expect(method).toBe('DELETE')
      expect(body.items).toEqual([{entry_type:'asset',id:libraryAsset.id,revision:1,current_version_id:null}])
      removed = true
      return {removed_count:1}
    })
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()

    await wrapper.findAll('button').find(button => button.text() === '批量管理')!.trigger('click')
    expect(wrapper.text()).toContain('只删除素材库引用，不删除原本数据。')
    expect(wrapper.find('.apf-import-progress').exists()).toBe(true)
    expect(wrapper.find('.apf-import-progress input[type="checkbox"]').exists()).toBe(false)
    const selectPage=wrapper.get('input[aria-label="全选当前页"]')
    await selectPage.setValue(true)
    expect((selectPage.element as HTMLInputElement).checked).toBe(true)
    await selectPage.setValue(false)
    expect((selectPage.element as HTMLInputElement).checked).toBe(false)
    expect((wrapper.findAll('button').find(button => button.text() === '删除')!.element as HTMLButtonElement).disabled).toBe(true)
    const rowCheckbox = wrapper.get('input[aria-label="选择 M31.fit"]')
    await rowCheckbox.setValue(true)
    expect((rowCheckbox.element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.text()).toContain('已选 1 项')
    expect(wrapper.get('input[aria-label="全选当前页"]').attributes('aria-checked')).toBe('mixed')
    await wrapper.findAll('button').find(button => button.text() === '删除')!.trigger('click')
    expect(send).not.toHaveBeenCalled()
    await wrapper.findAll('button').find(button => button.text() === '移入回收站')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已移除1条素材库记录，原始数据未删除。')
    expect(wrapper.text()).toContain('1 条记录')
    expect(wrapper.find('input[aria-label="选择 M31.fit"]').exists()).toBe(false)
    expect(wrapper.get('.apf-assets-table tbody tr:not(.apf-import-row)').text()).toContain('M42.fit')
  })

  it('does not carry a completed library deletion failure into another resource page',async()=>{
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([assetSummary(libraryAsset)])
      if(url(path).pathname.endsWith('/projects'))return page([project])
      return emptyPage
    })
    send.mockRejectedValue(new ApiClientError('Old delete failure','service',400,'DELETE_REJECTED'))
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='删除')!.trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='移入回收站')!.trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('Old delete failure')
    await openSettings()
    expect(wrapper.text()).not.toContain('Old delete failure')
    expect(wrapper.text()).toContain('M31')
  })

  it('keeps rows and the selection when a batch library removal fails', async()=>{
    const row=assetSummary(libraryAsset)
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([row])
      return emptyPage
    })
    send.mockRejectedValue(new ApiClientError('记录已变化，请重新读取。','service',409,'REVISION_CONFLICT'))
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='删除')!.trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='移入回收站')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('记录已被其他窗口修改。')
    expect((wrapper.get('input[aria-label="选择 M31.fit"]').element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.get('.apf-assets-table tbody tr').text()).toContain('M31.fit')
  })

  it('cancelling the bulk confirmation sends no removal request', async()=>{
    get.mockImplementation(async(path:string)=>path.endsWith('/capabilities')?capabilities:
      path.includes('/library/items')?page([assetSummary(libraryAsset)]):emptyPage)
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='删除')!.trigger('click')
    expect(wrapper.text()).toContain('原文件保留，可恢复')
    await wrapper.get('.apf-trash-confirm').findAll('button').find(button=>button.text()==='取消')!.trigger('click')
    expect(send).not.toHaveBeenCalled()
    expect((wrapper.get('input[aria-label="选择 M31.fit"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('does not apply a delayed library removal receipt to the project page opened meanwhile',async()=>{
    get.mockImplementation(async(path:string)=>path.endsWith('/capabilities')?capabilities:
      path.includes('/library/items')?page([assetSummary(libraryAsset)]):url(path).pathname.endsWith('/projects')?page([project]):emptyPage)
    let finish!:(value:{removed_count:number})=>void
    send.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='删除')!.trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='移入回收站')!.trigger('click')
    await flushPromises();expect(send).toHaveBeenCalledTimes(1)
    await openSettings()
    finish({removed_count:1});await flushPromises()
    expect(useWorkspaceStore(pinia).section).toBe('projects')
    expect(wrapper.text()).toContain('M31')
    expect(wrapper.text()).not.toContain('已移除1条素材库记录')
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('does not clear the new page selection when an earlier archive finishes',async()=>{
    get.mockImplementation(async(path:string)=>path.endsWith('/capabilities')?capabilities:
      url(path).pathname.endsWith('/projects')?page([project]):path.includes('/library/items')?page([assetSummary(libraryAsset)]):emptyPage)
    let finish!:(value:{archived_count:number})=>void
    send.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises();await openSettings()
    await wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='批量删除')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31"]').setValue(true)
    await wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='移入回收站')!.trigger('click')
    await wrapper.get('.apf-trash-confirm').findAll('button').find(button=>button.text()==='确认移入回收站')!.trigger('click')
    await flushPromises();expect(send).toHaveBeenCalledTimes(1)
    await wrapper.findComponent(Workspace).vm.selectArea('library');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='批量管理')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31.fit"]').setValue(true)
    finish({archived_count:1});await flushPromises()
    expect((wrapper.get('input[aria-label="选择 M31.fit"]').element as HTMLInputElement).checked).toBe(true)
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('archives only the project identities reviewed when confirmation opened', async()=>{
    const secondProject={...project,id:idAt(1601),name:'M42'}
    let archived=false
    get.mockImplementation(async(path:string)=>path.endsWith('/capabilities')?capabilities:
      url(path).pathname.endsWith('/projects')?page(archived?[secondProject]:[project,secondProject]):emptyPage)
    send.mockResolvedValue({archived_count:1})
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises();await openSettings()
    await wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='批量删除')!.trigger('click')
    await wrapper.get('input[aria-label="选择 M31"]').setValue(true)
    await wrapper.findAll('.apf-toolbar button').find(button=>button.text()==='移入回收站')!.trigger('click')
    const reviewedMessage=wrapper.get('.apf-trash-confirm p').text()
    // A late background checkbox event must not expand an already reviewed request.
    await wrapper.get('input[aria-label="选择 M42"]').setValue(true)
    expect(wrapper.get('.apf-trash-confirm p').text()).toBe(reviewedMessage)
    archived=true
    await wrapper.get('.apf-trash-confirm').findAll('button').find(button=>button.text()==='确认移入回收站')!.trigger('click')
    await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/settings/trash/archive',expect.anything(),'POST',{
      items:[{entry_type:'project',id:project.id,revision:project.revision}]
    })
    expect(wrapper.find('.apf-trash-confirm').exists()).toBe(false)
    expect(wrapper.text()).toContain('M42')
  })

  it('reads current-page trash records and restores their original identity', async()=>{
    const item={entry_type:'asset',id:idAt(550),name:'Trash A.fit',removed_at:createdAt,revision:2,current_version_id:idAt(551),cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:null}
    let restored=false
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/trash'))return page(restored?[]:[item],restored?0:1,Number(url(path).searchParams.get('offset')))
      return emptyPage
    })
    send.mockImplementation(async(path:string,_schema:unknown,method:string,body:Record<string,any>)=>{
      expect(method).toBe('POST')
      if(path.endsWith('/restore')){expect(body.items).toEqual([{entry_type:'asset',id:item.id,removed_at:createdAt,revision:2,current_version_id:item.current_version_id,source_dataset_id:null}]);restored=true;return {restored_count:1}}
      throw new Error('unexpected request')
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='回收站')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Trash A.fit')
    expect(wrapper.find('nav[aria-label="回收站分页"]').exists()).toBe(true)
    await wrapper.get('input[aria-label="选择 Trash A.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='恢复')!.trigger('click')
    await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('回收站为空。')
  })

  it('clears trash selection across pages and prevents restoring partial cleanups',async()=>{
    const items=Array.from({length:21},(_,index)=>({entry_type:'asset',id:idAt(570+index),name:`Trash ${index}.fit`,removed_at:createdAt,
      revision:1,current_version_id:null,cleanup_status:index===20?'partial':'trash',cleanup_error:index===20?'locked':null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:null}))
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/trash')){
        const offset=Number(url(path).searchParams.get('offset'))
        return page(items.slice(offset,offset+20),items.length,offset,20)
      }
      return emptyPage
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='回收站')!.trigger('click')
    await flushPromises()
    await wrapper.get('input[aria-label="选择 Trash 0.fit"]').setValue(true)
    await wrapper.get('nav[aria-label="回收站分页"]').findAll('button').find(button=>button.text()==='下一页')!.trigger('click')
    await flushPromises()
    expect((wrapper.get('input[aria-label="选择 Trash 20.fit"]').element as HTMLInputElement).checked).toBe(false)
    expect((wrapper.findAll('button').find(button=>button.text()==='恢复')!.element as HTMLButtonElement).disabled).toBe(true)
    await wrapper.get('nav[aria-label="回收站分页"]').findAll('button').find(button=>button.text()==='上一页')!.trigger('click')
    await flushPromises()
    expect((wrapper.get('input[aria-label="选择 Trash 0.fit"]').element as HTMLInputElement).checked).toBe(false)
    expect(send).not.toHaveBeenCalled()
  })

  it('refreshes the parent library after restoring an asset',async()=>{
    const item={entry_type:'asset',id:idAt(560),name:'Trash B.fit',removed_at:createdAt,revision:1,current_version_id:null,cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:null}
    let restored=false
    let libraryReads=0
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/trash'))return page(restored?[]:[item],restored?0:1)
      if(path.includes('/library/items')){libraryReads++;return page([])}
      return emptyPage
    })
    send.mockImplementation(async(path:string)=>{
      if(path.endsWith('/restore')){restored=true;return {restored_count:1}}
      throw new Error('unexpected request')
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    const initialLibraryReads=libraryReads
    await wrapper.findAll('button').find(button=>button.text()==='回收站')!.trigger('click')
    await flushPromises()
    await wrapper.get('input[aria-label="选择 Trash B.fit"]').setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='恢复')!.trigger('click')
    await flushPromises()
    expect(restored).toBe(true)
    expect(libraryReads).toBeGreaterThan(initialLibraryReads)
  })

  it('shows group trash as a parent with individually removed members',async()=>{
    const group={entry_type:'dataset',id:idAt(570),name:'Light frames',removed_at:createdAt,revision:2,current_version_id:idAt(572),cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[idAt(571)],groups:[],source_dataset_id:null}
    const member={entry_type:'asset',id:idAt(571),name:'A.fit',removed_at:createdAt,revision:2,current_version_id:idAt(573),cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[{id:group.id,name:group.name,in_trash:true}],source_dataset_id:null}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/trash'))return page([member,group])
      return emptyPage
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='回收站')!.trigger('click')
    await flushPromises()
    const rows=wrapper.findAll('.trash-table-wrap tbody tr')
    expect(rows[0].text()).toContain('Light frames')
    expect(rows[0].classes()).not.toContain('trash-child-row')
    expect(rows[1].text()).toContain('A.fit')
    expect(rows[1].classes()).toContain('trash-child-row')
    expect(wrapper.findAll('.trash-child-row')).toHaveLength(1)
  })

  it('loads and restores an implicit trash group member with its parent identity',async()=>{
    const group={entry_type:'dataset',id:idAt(590),name:'All lights',removed_at:createdAt,revision:1,current_version_id:idAt(591),cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[idAt(592)],groups:[],source_dataset_id:null}
    const child={entry_type:'asset',id:idAt(592),name:'Implicit.fit',removed_at:createdAt,revision:2,current_version_id:idAt(593),cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:group.id}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/trash'))return url(path).searchParams.has('group_id')?page([child]):page([group])
      return emptyPage
    })
    send.mockImplementation(async(path:string,_schema:unknown,method:string,body:Record<string,any>)=>{
      expect(path).toContain('/restore');expect(method).toBe('POST')
      expect(body.items).toEqual([{entry_type:'asset',id:child.id,removed_at:createdAt,revision:2,current_version_id:child.current_version_id,source_dataset_id:group.id}])
      return {restored_count:1}
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='回收站')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('.trash-table-wrap tbody button').find(button=>button.text()==='展开')!.trigger('click')
    await flushPromises()
    expect(get.mock.calls.some(([path])=>String(path).includes('group_id='+group.id))).toBe(true)
    await wrapper.get('input[aria-label="选择 Implicit.fit"]').setValue(true)
    await wrapper.findAll('.trash-dialog footer button').find(button=>button.text()==='恢复')!.trigger('click')
    await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('does not delete when the final permanent-delete confirmation is cancelled',async()=>{
    const item={entry_type:'asset',id:idAt(580),name:'Cancel.fit',removed_at:createdAt,revision:1,current_version_id:null,cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:null}
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/trash'))return page([item])
      return emptyPage
    })
    send.mockImplementation(async(path:string)=>{
      if(path.endsWith('/delete-preview'))return {items:[item],references:[],tasks:[],photo_count:1,managed_file_count:0,managed_bytes:0,preview_fingerprint:'confirmed-range'}
      throw new Error('delete must not run after cancellation')
    })
    wrapper=mount(App,{global:{plugins:[pinia]}})
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='回收站')!.trigger('click')
    await flushPromises()
    await wrapper.get('input[aria-label="选择 Cancel.fit"]').setValue(true)
    await wrapper.findAll('.trash-dialog footer button').find(button=>button.text()==='永久删除')!.trigger('click')
    await flushPromises()
    const confirm=wrapper.get('[role="alertdialog"]')
    await confirm.findAll('button').find(button=>button.text()==='取消')!.trigger('click')
    expect(send.mock.calls.some(([path])=>String(path).endsWith('/delete'))).toBe(false)
  })

  it('truncates displayed temperatures toward zero without changing saved precision', async () => {
    const assets=[0.29,1.15,-10.12].map((sensor_temperature_c,index)=>({
      ...libraryAsset,id:idAt(800+index),parameters:{...libraryAsset.parameters,sensor_temperature_c}
    }))
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/library/items')) return page(assets.map(asset=>(assetSummary(asset))))
      return emptyPage
    })
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()

    expect(wrapper.findAll('.apf-assets-table tbody tr').map(row=>row.find('td:nth-child(7) .apf-inline-value').text()))
      .toEqual(['0.29 °C','1.15 °C','-10.12 °C'])
    expect(send).not.toHaveBeenCalled()
  })
  it('refreshes a visible library after a change made outside the page', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    let current = assetSummary(libraryAsset)
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/library/items')) return page([current])
      return emptyPage
    })
    try {
      wrapper = mount(App, { global: { plugins: [pinia] } })
      await flushPromises()
      expect(wrapper.text()).toContain('M31.fit')
      current = { ...current, name: 'Changed outside UI.fit', revision: 2 }
      await vi.advanceTimersByTimeAsync(10_000)
      await flushPromises()
      expect(wrapper.text()).toContain('Changed outside UI.fit')
      expect(get.mock.calls.filter(([path]) => String(path).includes('/library/items'))).toHaveLength(2)
    } finally {
      wrapper?.unmount()
      focusManager.setFocused(undefined)
      vi.useRealTimers()
    }
  })

  it('retains a row draft and its original revision while the visible library refreshes', async () => {
    vi.useFakeTimers()
    focusManager.setFocused(true)
    let current = assetSummary(libraryAsset)
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/library/items')) return page([current])
      return emptyPage
    })
    send.mockRejectedValue(new ApiClientError('Background revision conflict', 'service', 409, 'REVISION_CONFLICT'))
    try {
      wrapper = mount(App, { global: { plugins: [pinia] } })
      await flushPromises()
      await wrapper.get('.apf-assets-table tbody .apf-material-name .apf-inline-value').trigger('dblclick')
      await flushPromises()
      await wrapper.get('.apf-assets-table tbody input').setValue('Unsent row draft')
      current = { ...current, name: 'Remote name.fit', revision: 2 }
      await vi.advanceTimersByTimeAsync(10_000)
      await flushPromises()
      expect((wrapper.get('.apf-assets-table tbody input').element as HTMLInputElement).value).toBe('Unsent row draft')
      await wrapper.get('.apf-assets-table tbody input').trigger('keydown', { key: 'Enter' })
      await flushPromises()
      expect(send.mock.calls[0][3]).toMatchObject({ name: 'Unsent row draft', base_revision: 1 })
      expect(wrapper.text()).toContain('Background revision conflict')
    } finally {
      wrapper?.unmount()
      focusManager.setFocused(undefined)
      vi.useRealTimers()
    }
  })

  it('defers import-driven library invalidation while an inline write is pending', async () => {
    let current = assetSummary(libraryAsset)
    get.mockImplementation(async (path: string) => {
      if (path.endsWith('/capabilities')) return capabilities
      if (path.includes('/library/items')) return page([current])
      return emptyPage
    })
    let finish!: (value: typeof libraryAsset) => void
    send.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody .apf-material-name .apf-inline-value').trigger('dblclick')
    await flushPromises()
    await wrapper.get('.apf-assets-table tbody input').setValue('Saved name.fit')
    await wrapper.get('.apf-assets-table tbody input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    const reads = () => get.mock.calls.filter(([path]) => String(path).includes('/library/items')).length
    expect(reads()).toBe(1)
    wrapper.getComponent(ImportTasks).vm.$emit('registered', 'external-task')
    await flushPromises()
    expect(reads()).toBe(1)
    const saved = { ...libraryAsset, name: 'Saved name.fit', revision: 2 }
    current = assetSummary(saved)
    finish(saved)
    await flushPromises()
    expect(reads()).toBeGreaterThan(1)
    expect(wrapper.text()).toContain('Saved name.fit')
    expect(send).toHaveBeenCalledTimes(1)
  })

})
