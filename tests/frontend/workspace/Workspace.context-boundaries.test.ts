import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@frontend/App.vue'
import Workspace from '@frontend/workspace/Workspace.vue'
const {get,send,getBlob}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),getBlob:vi.fn()}))
vi.mock('@frontend/assets/host-client',()=>({assetApi:{get,send,getBlob}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const camera={id:id(1),kind:'camera',name:'Camera',model:null,serial_number:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const setup={id:id(2),name:'Saved rig',components:[],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const assetVersion={id:id(10),asset_id:id(9),version_number:1,storage_mode:'reference',storage_location:'root/photo.png',byte_size:10,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,filter_id:null,frame_type:'light',calibration_level:'individual',capture_snapshot:{},scientific_metadata:{},created_at:timestamp}
const asset={id:id(9),name:'Photo.png',scope:'shared',owner_project_id:null,role:'raw',calibration_level:'individual',current_version_id:assetVersion.id,classification:{frame_class:'subframe',frame_type:'light'},parameters:{parameter_mode:'standard'},equipment_snapshot:{},value_sources:{},notes:null,status:'active',revision:1,created_at:timestamp,current_version:assetVersion}
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
  await wrapper.get('button[aria-label="设置"]').trigger('click');await flushPromises()
  await click('使用组合');await click('新建使用组合')
  await wrapper.get('form[aria-label="使用组合表单"] input[required]').setValue('Saved rig')
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
  await wrapper.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
  await click('设备')
  expect(wrapper.find('section[aria-label="使用组合和拍摄预设"]').exists()).toBe(false)
  resolveSave(setup);await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {selected:unknown}
  expect(vm.selected).toBeUndefined()
 })
 it('does not open an old library preview after navigation waited on an inline save',async()=>{
  get.mockImplementation(async(path:string)=>{
   const url=new URL(path,'http://test')
   if(url.pathname.endsWith('/capabilities'))return cap
   if(url.pathname.endsWith('/library/items'))return page([{entry_type:'asset',asset,import_issue:null}])
   return page([])
  })
  await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {loadRecords:()=>Promise<void>;activeArea:string}
  await vm.loadRecords();await flushPromises()
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve})).mockResolvedValue({asset_version_id:assetVersion.id,size:'display',status:'not_ready',error:{code:'NOT_READY',message:'not ready'},width:null,height:null})
  const row=wrapper.get('.apf-assets-table tbody tr')
  await row.get('.apf-inline-value').trigger('dblclick')
  await row.get('input').setValue('Renamed.png');await row.get('input').trigger('keydown',{key:'Enter'});await flushPromises()
  await row.get('.apf-thumb').trigger('click')
  await wrapper.get('button[aria-label="设置"]').trigger('click');await flushPromises()
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
  await wrapper.get('button[aria-label="设置"]').trigger('click');await flushPromises()
  await click('使用组合')
  await wrapper.findAll('.apf-record').find(button=>button.text().includes('First rig'))!.trigger('click');await flushPromises()
  await click('编辑使用组合')
  await wrapper.get('form[aria-label="使用组合表单"] input[required]').setValue('Changed first')
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
  await wrapper.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
  await wrapper.findAll('.apf-record').find(button=>button.text().includes('Second rig'))!.trigger('click');await flushPromises()
  resolveSave({...first,name:'Changed first',revision:2});await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {selected:{id:string}}
  expect(vm.selected.id).toBe(second.id)
  expect(wrapper.get('section[aria-label="使用组合详情"]').text()).toContain('Second rig')
 })
 it('finishes the same setup save after retrying its failed preset list',async()=>{
  let presetReads=0
  get.mockImplementation(async(path:string)=>{
   if(path.endsWith('/capabilities'))return cap
   const pathname=new URL(path,'http://test').pathname
   if(pathname.endsWith('/equipment-setups'))return page([setup])
   if(pathname.endsWith('/presets')&&presetReads++===0)throw new Error('preset list unavailable')
   return page([])
  })
  await flushPromises()
  await wrapper.get('button[aria-label="设置"]').trigger('click');await flushPromises()
  await click('使用组合')
  await wrapper.findAll('.apf-record').find(button=>button.text().includes(setup.name))!.trigger('click');await flushPromises()
  await click('编辑使用组合')
  await wrapper.get('form[aria-label="使用组合表单"] input[required]').setValue('Updated rig')
  let resolveSave!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
  await wrapper.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
  await click('重试')
  resolveSave({...setup,name:'Updated rig',revision:2});await flushPromises()
  const vm=wrapper.getComponent(Workspace).vm as unknown as {selected:{name:string;revision:number}}
  expect(vm.selected.name).toBe('Updated rig')
  expect(vm.selected.revision).toBe(2)
  expect(wrapper.find('form[aria-label="使用组合表单"]').exists()).toBe(false)
  await click('编辑使用组合')
  await wrapper.get('form[aria-label="使用组合表单"] input[required]').setValue('Updated again')
  send.mockResolvedValueOnce({...setup,name:'Updated again',revision:3})
  await wrapper.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
  expect(send.mock.calls.at(-1)![3].base_revision).toBe(2)
  expect(vm.selected.revision).toBe(3)
 })
 it('does not silently replace an explicit frame filter with the category filter',async()=>{
  get.mockImplementation(async(path:string)=>{
   if(path.endsWith('/capabilities'))return cap
   if(path.includes('/library/items'))return page([{entry_type:'asset',asset,import_issue:null}])
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
   if(path.includes('/library/items'))return page([{entry_type:'asset',asset:{...asset,role:'calibration',classification:{frame_class:'masterframe',frame_type:'flat'}},import_issue:null}])
   return page([])
  })
  await flushPromises();await click('校准库')
  expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
  const vm=wrapper.getComponent(Workspace).vm as unknown as {applyFilters:(filters:unknown)=>void;activeFilters:unknown}
  vm.applyFilters({roles:['raw']});await flushPromises()
  expect(vm.activeFilters).toEqual({roles:['raw']})
  expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(0)
 })
 it('does not navigate back to a calibration group created after leaving its view',async()=>{
  const dark={...asset,name:'Master dark',role:'calibration',classification:{frame_class:'masterframe',frame_type:'dark'}}
  const group={id:id(20),name:'New calibration',notes:null,status:'active',revision:1,current_version_id:id(21),member_count:1,created_at:timestamp,updated_at:timestamp}
  const version={id:id(21),dataset_id:group.id,version_number:1,created_at:timestamp,calibration_defaults:{},members:[{
   id:id(22),dataset_version_id:id(21),asset_version_id:assetVersion.id,position:0,relative_path:null,calibration_overrides:{},asset:dark,version:assetVersion
  }]}
  let persisted=false
  get.mockImplementation(async(path:string)=>{
   if(path.endsWith('/capabilities'))return cap
   if(path.includes('/library/assets'))return page([dark])
   if(path.includes('/library/items'))return page(persisted?[{entry_type:'dataset',dataset:group,version,matching_member_count:1,import_issue:null}]:[])
   if(path.endsWith('/versions/'+version.id))return version
   return page([])
  })
  await flushPromises();await click('校准库');await click('从已有校准照片创建组')
  const form=wrapper.get('form[aria-label="创建校准组"]')
  await form.get('input[required]').setValue(group.name)
  await form.get('input[type="checkbox"]').setValue(true)
  let resolveCreate!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{resolveCreate=resolve}))
  await form.trigger('submit');await flushPromises()
  await click('全部素材')
  persisted=true;resolveCreate(group);await flushPromises()
  expect(wrapper.get('h1').text()).toBe('素材库')
  const vm=wrapper.getComponent(Workspace).vm as unknown as {activeDataset:unknown}
  expect(vm.activeDataset).toBeUndefined()
 })
})
