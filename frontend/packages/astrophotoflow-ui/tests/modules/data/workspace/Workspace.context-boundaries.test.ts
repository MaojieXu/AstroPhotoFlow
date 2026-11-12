import { assetFixture } from '../../../fixtures/library-members'
import { libraryAsset } from '../../../fixtures/library-summary'
import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/WorkspacePage.vue'
const {get,send,getBlob}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),getBlob:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send,getBlob}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const camera={id:id(1),kind:'camera',name:'Camera',model:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const setup={id:id(2),name:'Saved rig',components:[],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const original={view_base: `/astrophotoflow/api/v1/library/assets/${id(9)}/previews`, id: id(9), storage_mode:'reference', storage_location:'root/photo.png', byte_size:10, content_hash:null, availability:'available', calibration_level:'individual', capture_snapshot:{}, scientific_metadata:{}, created_at:timestamp}
const asset=assetFixture({...original, id:id(9), name:'Photo.png', scope:'shared', owner_project_id:null, role:'raw', calibration_level:'individual', classification:{frame_class:'subframe',frame_type:'light'}, parameters:{parameter_mode:'standard'}, equipment_snapshot:{}, value_sources:{}, notes:null, status:'active', revision:1, created_at:timestamp})
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
let wrapper:ReturnType<typeof mount>
async function click(text:string){await wrapper.findAll('button').find(button=>button.text()===text)!.trigger('click');await flushPromises()}
beforeEach(()=>{
 get.mockReset().mockImplementation(async(path:string)=>{
  const url=new URL(path,'http://test')
  if(url.pathname.endsWith('/capabilities'))return cap
  if(url.pathname.endsWith('/equipment'))return page([camera])
  return page([])
 })
 send.mockReset();getBlob.mockReset().mockRejectedValue(new Error('unavailable'))
 vi.spyOn(window,'confirm').mockReturnValue(true)
 wrapper=mount(App,{global:{plugins:[createPinia()]}})
})
afterEach(()=>{wrapper.unmount();vi.restoreAllMocks()})
describe('workspace async view boundaries',()=>{
 it('does not install a setup selection into equipment after saving in previous view',async()=>{
  await flushPromises()
  await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()
  await click('设备组合');await click('新建设备组合')
  await wrapper.get('form[aria-label="设备组合表单"] input[required]').setValue('Saved rig')
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
  await wrapper.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
  await click('我的设备')
  expect(wrapper.find('section[aria-label="设备组合"]').exists()).toBe(false)
  resolveSave(setup);await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {selected:unknown}
  expect(vm.selected).toBeUndefined()
 })
 it('does not open an old library preview after navigation waited on an inline save',async()=>{
  get.mockImplementation(async(path:string)=>{
   const url=new URL(path,'http://test')
   if(url.pathname.endsWith('/capabilities'))return cap
   if(url.pathname.endsWith('/library/items'))return page([libraryAsset(asset)])
   return page([])
  })
  await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {refreshRecords:()=>Promise<void>;activeArea:string}
  await vm.refreshRecords();await flushPromises()
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve})).mockResolvedValue({asset_id:original.id, size:'display', status:'not_ready', error:{code:'NOT_READY',message:'not ready'}, width:null, height:null})
  const row=wrapper.get('.apf-assets-table tbody tr')
  await row.get('.apf-inline-value').trigger('dblclick')
  await row.get('input').setValue('Renamed.png');await row.get('input').trigger('keydown',{key:'Enter'});await flushPromises()
  await row.get('.apf-thumb').trigger('click')
  await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()
  resolveSave({...asset,name:'Renamed.png',revision:2})
  await new Promise(resolve=>setTimeout(resolve,60));await flushPromises()
  expect(vm.activeArea).toBe('settings')
  expect(wrapper.find('.apf-photo-dialog').exists()).toBe(false)
 })
 it('does not replace a newer setup selection after an older save completes',async()=>{
  const first={...setup,name:'First rig'}
  const second={...setup,id:id(3),name:'Second rig'}
  get.mockImplementation(async(path:string)=>{
   if(path.endsWith('/capabilities'))return cap
   if(new URL(path,'http://test').pathname.endsWith('/equipment-setups'))return page([first,second])
   return page([])
  })
  await flushPromises()
  await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()
  await click('设备组合')
  await wrapper.get('button[aria-label="查看组合 First rig"]').trigger('click');await flushPromises()
  await click('编辑设备组合')
  await wrapper.get('form[aria-label="设备组合表单"] input[required]').setValue('Changed first')
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
  await wrapper.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
  await wrapper.get('button[aria-label="查看组合 Second rig"]').trigger('click');await flushPromises()
  resolveSave({...first,name:'Changed first',revision:2});await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {selected:{id:string}}
  expect(vm.selected.id).toBe(second.id)
  expect(wrapper.get('table[aria-label="设备组合列表"] tr[aria-selected="true"]').text()).toContain('Second rig')
  expect(wrapper.text()).toContain('编辑设备组合')
 })
 it('does not silently replace an explicit frame filter with the category filter',async()=>{
  get.mockImplementation(async(path:string)=>{
   if(path.endsWith('/capabilities'))return cap
   if(path.includes('/library/items'))return page([libraryAsset(asset)])
   return page([])
  })
  await flushPromises();await click('亮场')
  expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
  const vm=wrapper.getComponent(Workspace).vm as unknown as {applyFilters:(filters:unknown)=>void;activeFilters:unknown}
  vm.applyFilters({frame_types:['dark']});await flushPromises()
  expect(vm.activeFilters).toEqual({frame_types:['dark']})
  expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(0)
 })
 it('keeps a matching frame alternative in the Light intersection',async()=>{
  await flushPromises();await click('亮场')
  const vm=wrapper.getComponent(Workspace).vm as unknown as {applyFilters:(filters:unknown)=>void;activeFilters:unknown}
  vm.applyFilters({frame_types:['light','dark']});await flushPromises()
  expect(vm.activeFilters).toEqual({frame_types:['light','dark']})
  const path=get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0]
  expect(new URL(path,'http://test').searchParams.getAll('frame_type')).toEqual(['light'])
 })
 it('returns an empty intersection instead of ignoring Raw inside calibration',async()=>{
  get.mockImplementation(async(path:string)=>{
   if(path.endsWith('/capabilities'))return cap
   if(path.includes('/library/items'))return page([libraryAsset({...asset,role:'calibration',classification:{frame_class:'masterframe',frame_type:'flat'}})])
   return page([])
  })
  await flushPromises();await click('校准库')
  expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
  const vm=wrapper.getComponent(Workspace).vm as unknown as {applyFilters:(filters:unknown)=>void;activeFilters:unknown}
  vm.applyFilters({roles:['raw']});await flushPromises()
  expect(vm.activeFilters).toEqual({roles:['raw']})
  expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(0)
 })
})
