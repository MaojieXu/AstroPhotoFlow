import { zEquipmentSetupCreate } from '@ui/generated/api/zod.gen'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@ui/modules/data/App.vue'
import EquipmentDeleteDialog from '@ui/modules/data/equipment/EquipmentDeleteDialog.vue'
import { equipmentSchema, equipmentSetupSchema, type Equipment, type EquipmentSetup } from '@ui/modules/data/api/contracts'

const {get,send} = vi.hoisted(()=>({get:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-28T12:00:00Z'
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
let devices:Equipment[]
let setups:EquipmentSetup[]
let wrapper:ReturnType<typeof mount>|undefined
const preview={items:[{entry_type:'equipment',id:id(1),name:'Camera',revision:1,updated_at:timestamp,details:{}}],
  dependencies:[{entry_type:'equipment',id:id(1),kind:'equipment_setups',name:'设备组合中的关联（移除）',count:1,blocks_delete:false,references:['Wide rig']}],blocked:false,preview_fingerprint:'current'}

beforeEach(()=>{
  devices=[];setups=[]
  get.mockReset().mockImplementation(async(path:string)=>{
    if(path.endsWith('/capabilities'))return {stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
    const url=new URL(path,'http://test')
    if(url.pathname.endsWith('/equipment'))return page(devices)
    if(url.pathname.endsWith('/equipment-setups'))return page(setups)
    return page([])
  })
  send.mockReset().mockImplementation(async(path:string,_schema:unknown,_method:string,data:Record<string,unknown>)=>{
    if(path.endsWith('/equipment')){
      const saved=equipmentSchema.parse({...data,id:id(devices.length+1),status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
      devices.push(saved);return saved
    }
    if(path.endsWith('/equipment-setups')){
      const saved=equipmentSetupSchema.parse({...data,components:(zEquipmentSetupCreate.shape.components.parse(data.components)??[]).map((component,index)=>({...component,id:component.id??id(500+setups.length*100+index)})),id:id(100+setups.length),status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
      setups.push(saved);return saved
    }
    if(path.endsWith('/delete-preview'))return preview
    return {deleted_count:1,detached_material_count:0}
  })
})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks()})
async function click(text:string){await wrapper!.findAll('button').find(button=>button.text()===text||button.attributes('aria-label')===text)!.trigger('click');await flushPromises()}
async function open(){wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises();await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()}
function field(text:string){return wrapper!.findAll('label').find(label=>label.text()===text)!.get('input')}

describe('equipment management',()=>{
  it.each([
    {name:'ASI2600MC',model:'asi2600mc',subtitle:'相机'},
    {name:'Main camera',model:'ASI2600MC',subtitle:'相机 · ASI2600MC'},
    {name:'Main camera',model:null,subtitle:'相机'},
    {name:'Main camera',model:'  ',subtitle:'相机'}
  ])('shows only useful category and model information for $name / $model',async({name,model,subtitle})=>{
    devices=[equipmentSchema.parse({id:id(1),kind:'camera',name,model,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp})]
    await open();await click('我的设备')
    const row=wrapper!.get('button[aria-label="选择设备 '+name+'"]')
    expect(row.get('strong').text()).toBe(name)
    expect(row.get('small').text()).toBe(subtitle)
    expect(row.attributes('aria-pressed')).toBe('false')
    await row.trigger('click');await flushPromises()
    expect(row.attributes('aria-pressed')).toBe('true')
    expect(wrapper!.get('button[aria-label="编辑设备 '+name+'"]').text()).toBe('编辑')
  })

  it('starts on combinations with only equipment navigation and no management trash',async()=>{
    await open()
    expect(wrapper!.get('.apf-management-tabs').text()).toBe('设备组合我的设备')
    expect(wrapper!.get('.apf-management-tabs button[aria-current="page"]').text()).toBe('设备组合')
    expect(wrapper!.text()).not.toContain('回收站')
    expect(wrapper!.text()).not.toContain('新建项目')
    expect(get.mock.calls.some(([path])=>String(path).includes('/projects'))).toBe(false)
  })

  it.each([['camera','相机'],['telescope','望远镜'],['filter','滤镜']])('registers %s inside a combination and keeps it after abandoning the combination',async(kind,label)=>{
    await open();await click('新建设备组合');await click('新建'+label)
    await field('设备名称').setValue('Saved '+kind)
    if(kind==='camera')await field('像元尺寸（μm）').setValue('3.76')
    await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    expect(devices).toHaveLength(1)
    expect(devices[0]).toMatchObject({kind,name:'Saved '+kind})
    if(kind==='camera')expect(devices[0].specs).toMatchObject({pixel_size_um:3.76})
    expect(wrapper!.text()).toContain('取消组合仍会保留此设备')
    vi.spyOn(window,'confirm').mockReturnValue(true)
    await click('取消');await click('我的设备')
    expect(wrapper!.text()).toContain('Saved '+kind)
    expect(setups).toHaveLength(0)
    if(kind==='camera'){
      await wrapper!.get('.apf-record').trigger('click');await flushPromises();await click('编辑')
      const pixel=wrapper!.get('form[aria-label="记录编辑表单"]').findAll('label').find(label=>label.text().startsWith('像元尺寸'))!
      expect(pixel.get('input').element).toHaveProperty('value','3.76')
    }
  })

  it('shows edit only in the selected device row and opens the shared form for that device',async()=>{
    devices=[equipmentSchema.parse({id:id(1),kind:'filter',name:'Ha filter',model:'7 nm',notes:null,specs:{bandwidth_nm:7},status:'active',revision:3,created_at:timestamp,updated_at:timestamp})]
    devices.push({...devices[0],id:id(2),name:'OIII filter'})
    await open();await click('我的设备')
    expect(wrapper!.find('button[aria-label^="编辑设备 "]').exists()).toBe(false)
    const row=wrapper!.get('button[aria-label="选择设备 Ha filter"]')
    await row.trigger('click');await flushPromises()
    expect(wrapper!.find('aside[aria-label="记录详情"]').exists()).toBe(false)
    expect(wrapper!.find('form[aria-label="记录编辑表单"]').exists()).toBe(false)
    expect(row.attributes('aria-pressed')).toBe('true')
    expect(wrapper!.get('[role="group"][aria-label="设备 Ha filter"]').get('button[aria-label="编辑设备 Ha filter"]').text()).toBe('编辑')
    expect(wrapper!.get('[role="group"][aria-label="设备 OIII filter"]').find('button[aria-label^="编辑设备 "]').exists()).toBe(false)
    expect(wrapper!.find('[role="group"][aria-label="设备操作"]').exists()).toBe(false)
    await row.trigger('dblclick')
    await flushPromises()
    expect(wrapper!.find('form[aria-label="记录编辑表单"]').exists()).toBe(false)
    await click('编辑')
    await flushPromises()
    expect(wrapper!.findAll('[role="dialog"]')).toHaveLength(1)
    expect(wrapper!.get('#device-name').element).toHaveProperty('value','Ha filter')
    expect(field('型号').element).toHaveProperty('value','7 nm')
    expect(wrapper!.get('select[aria-label="设备类型"]').attributes('disabled')).toBeDefined()
    await click('取消')
    expect(wrapper!.find('form[aria-label="记录编辑表单"]').exists()).toBe(false)
    expect(send).not.toHaveBeenCalled()
    await wrapper!.get('button[aria-label="选择设备 OIII filter"]').trigger('click');await flushPromises()
    expect(wrapper!.get('[role="group"][aria-label="设备 Ha filter"]').find('button[aria-label^="编辑设备 "]').exists()).toBe(false)
    expect(wrapper!.get('[role="group"][aria-label="设备 OIII filter"]').get('button[aria-label="编辑设备 OIII filter"]').text()).toBe('编辑')
    await click('编辑')
    expect(wrapper!.get('#device-name').element).toHaveProperty('value','OIII filter')
  })

  it('keeps checkbox deletion separate from opening an editor',async()=>{
    devices=[equipmentSchema.parse({id:id(1),kind:'filter',name:'Ha filter',model:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp})]
    await open();await click('我的设备')
    expect(wrapper!.find('input[type="checkbox"]').exists()).toBe(false)
    await click('批量管理')
    await wrapper!.get('input[aria-label="选择 Ha filter"]').setValue(true);await flushPromises()
    expect(wrapper!.find('form[aria-label="记录编辑表单"]').exists()).toBe(false)
    expect(wrapper!.find('button[aria-label^="编辑设备 "]').exists()).toBe(false)
    expect(wrapper!.text()).toContain('删除所选（1）')
  })

  it('saves the shared device form explicitly with its revision and preserves failed input',async()=>{
    devices=[equipmentSchema.parse({id:id(1),kind:'filter',name:'Ha filter',model:null,notes:null,specs:{},status:'active',revision:3,created_at:timestamp,updated_at:timestamp})]
    await open();await click('我的设备');await wrapper!.get('button[aria-label="选择设备 Ha filter"]').trigger('click');await flushPromises();await click('编辑')
    const form=wrapper!.get('form[aria-label="记录编辑表单"]')
    await form.get('#device-name').setValue('Revised Ha')
    expect(send).not.toHaveBeenCalled()
    send.mockRejectedValueOnce(new Error('Device save failed'))
    await form.trigger('submit');await flushPromises()
    expect(form.text()).toContain('Device save failed')
    expect(form.get('#device-name').element).toHaveProperty('value','Revised Ha')
    send.mockImplementationOnce(async()=>{devices=[{...devices[0],name:'Revised Ha',revision:4}];return devices[0]})
    await form.trigger('submit');await flushPromises()
    expect(send.mock.calls.at(-1)).toEqual(['/astrophotoflow/api/v1/equipment/'+id(1),expect.anything(),'PATCH',{kind:'filter',base_revision:3,name:'Revised Ha'}])
    expect(wrapper!.find('form[aria-label="记录编辑表单"]').exists()).toBe(false)
    expect(wrapper!.get('button[aria-label="选择设备 Revised Ha"]').text()).toContain('Revised Ha')
    expect(wrapper!.get('button[aria-label="选择设备 Revised Ha"]').attributes('aria-pressed')).toBe('true')
    expect(wrapper!.get('[role="group"][aria-label="设备 Revised Ha"]').get('button[aria-label="编辑设备 Revised Ha"]').text()).toBe('编辑')
  })

  it('preserves untouched camera specs and saves only the changed name and cleared model',async()=>{
    devices=[equipmentSchema.parse({id:id(1),kind:'camera',name:'Camera',model:'Old',notes:null,specs:{pixel_size_um:3.76,native_bit_depth:16},status:'active',revision:5,created_at:timestamp,updated_at:timestamp})]
    await open();await click('我的设备');await wrapper!.get('button[aria-label="选择设备 Camera"]').trigger('click');await flushPromises();await click('编辑')
    await field('名称').setValue('Renamed')
    await field('型号').setValue('')
    send.mockResolvedValueOnce({...devices[0],name:'Renamed',model:null,revision:6})
    await wrapper!.get('form[aria-label="记录编辑表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3]).toEqual({kind:'camera',base_revision:5,name:'Renamed',model:null})
  })

  it('keeps unsaved changes when cancelling is declined and discards them without a write when confirmed',async()=>{
    devices=[equipmentSchema.parse({id:id(1),kind:'mount',name:'Mount',model:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp})]
    await open();await click('我的设备');await wrapper!.get('button[aria-label="选择设备 Mount"]').trigger('click');await flushPromises();await click('编辑')
    await field('名称').setValue('Unsaved telescope')
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
    await click('取消')
    expect(field('名称').element).toHaveProperty('value','Unsaved telescope')
    confirm.mockReturnValue(true)
    await click('取消')
    expect(wrapper!.find('form[aria-label="记录编辑表单"]').exists()).toBe(false)
    expect(send).not.toHaveBeenCalled()
  })

  it('reuses a saved device in two combinations without registering another copy',async()=>{
    await open();await click('新建设备组合');await click('新建相机')
    await field('设备名称').setValue('Shared camera');await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    await field('组合名称').setValue('Wide rig')
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(wrapper!.text()).not.toContain('加入组合草稿')
    await click('新建设备组合');await field('组合名称').setValue('Long rig')
    await wrapper!.get('select[aria-label="选择相机"]').setValue([id(1)]);await flushPromises()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(setups.map(row=>row.components)).toEqual([[{id:id(500),source:'registered',equipment_id:id(1)}],[{id:id(600),source:'registered',equipment_id:id(1)}]])
    expect(send.mock.calls.filter(([path])=>String(path).endsWith('/equipment'))).toHaveLength(1)
  })

  it('keeps the combination draft in one dialog while returning from a device view',async()=>{
    await open();await click('新建设备组合');await field('组合名称').setValue('Draft rig')
    const dialog=wrapper!.get('[role="dialog"]').element
    expect(wrapper!.findAll('select[multiple]')).toHaveLength(5)
    await click('新建相机')
    expect(wrapper!.findAll('[role="dialog"]')).toHaveLength(1)
    expect(wrapper!.get('[role="dialog"]').element).toBe(dialog)
    expect(wrapper!.find('form[aria-label="设备组合表单"]').exists()).toBe(false)
    await field('设备名称').setValue('Unsaved camera')
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
    await wrapper!.get('[role="dialog"]').trigger('keydown',{key:'Escape'})
    expect(confirm).toHaveBeenCalledOnce()
    expect(field('设备名称').element).toHaveProperty('value','Unsaved camera')
    confirm.mockReturnValue(true);await click('返回组合')
    expect(field('组合名称').element).toHaveProperty('value','Draft rig')
    expect(send).not.toHaveBeenCalled()
  })

  it.each([['camera','相机'],['filter','滤镜']])('updates multiple %s selections directly and preserves the order of retained components',async(kind,label)=>{
    devices=[1,2,3].map(index=>equipmentSchema.parse({id:id(index),kind,name:label+' '+index,model:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}))
    setups=[{id:id(100),name:'Ordered rig',components:[{id:id(201),source:'registered',equipment_id:id(2)},{id:id(202),source:'registered',equipment_id:id(1)}],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}]
    await open();await wrapper!.get('button[aria-label="查看组合 Ordered rig"]').trigger('click');await flushPromises();await click('编辑设备组合')
    await wrapper!.get('select[aria-label="选择'+label+'"]').setValue([id(1),id(2),id(3)])
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls.at(-1)![3].components).toEqual([
      {id:id(201),source:'registered',equipment_id:id(2)},
      {id:id(202),source:'registered',equipment_id:id(1)},
      {source:'registered',equipment_id:id(3)}
    ])
    expect(wrapper!.findAll('button').some(button=>button.text()==='加入'+label)).toBe(false)
  })

  it('keeps failed device input and guards switching away from it',async()=>{
    await open();await click('新建设备组合');await click('新建望远镜')
    await field('设备名称').setValue('Unsaved telescope')
    send.mockRejectedValueOnce(new Error('Device save failed'))
    await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    expect(wrapper!.text()).toContain('Device save failed')
    expect(field('设备名称').element).toHaveProperty('value','Unsaved telescope')
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
    await click('返回组合')
    expect(confirm).toHaveBeenCalledOnce()
    expect(field('设备名称').element).toHaveProperty('value','Unsaved telescope')
    expect(devices).toHaveLength(0)
  })

  it('previews the impact once and cancels without deleting or archiving',async()=>{
    wrapper=mount(EquipmentDeleteDialog,{props:{workspaceId:'/fixture',viewKey:'one',items:[{entry_type:'equipment',id:id(1),revision:1}]}})
    await flushPromises()
    expect(wrapper.text()).toContain('Wide rig')
    await click('取消')
    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(send.mock.calls.map(([path])=>path)).toEqual(['/astrophotoflow/api/v1/equipment-management/delete-preview'])
  })

  it('does not apply a deletion acknowledgement to a different management view',async()=>{
    const items=[{entry_type:'equipment' as const,id:id(1),revision:1}]
    wrapper=mount(EquipmentDeleteDialog,{props:{workspaceId:'/fixture',viewKey:'one',items}})
    await flushPromises()
    let finish!:(value:unknown)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
    await wrapper.findAll('button').find(button=>button.text()==='确认删除')!.trigger('click')
    await flushPromises()
    await wrapper.setProps({viewKey:'two'})
    finish({deleted_count:1,detached_material_count:0})
    await flushPromises()
    expect(wrapper.emitted('deleted')).toBeUndefined()
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(send.mock.calls.filter(([path])=>String(path).endsWith('/delete'))).toHaveLength(1)
  })

  it('does not enable deletion from a late preview after the confirmation closes',async()=>{
    let finish!:(value:unknown)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
    wrapper=mount(EquipmentDeleteDialog,{props:{workspaceId:'/fixture',viewKey:'one',items:[{entry_type:'equipment',id:id(1),revision:1}]}})
    await flushPromises()
    await wrapper.setProps({items:undefined})
    finish(preview)
    await flushPromises()
    expect(wrapper.emitted('deleted')).toBeUndefined()
    expect(wrapper.text()).not.toContain('Wide rig')
    expect(send.mock.calls).toHaveLength(1)
  })

  it('selects multiple owned presets for one direct deletion confirmation',async()=>{
    setups=[{id:id(100),name:'Wide rig',components:[],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}]
    const presets=[1,2].map(index=>({id:id(200+index),equipment_setup_id:id(100),name:'Preset '+index,equipment_selection:{},parameters:{},status:'active',revision:index,created_at:timestamp,updated_at:timestamp}))
    const original=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/presets?')?page(presets):original(path))
    await open();await wrapper!.get('button[aria-label="查看组合 Wide rig"]').trigger('click');await flushPromises()
    for(const preset of presets)await wrapper!.get('input[aria-label="选择预设 '+preset.name+'"]').setValue(true)
    await click('删除所选预设（2）')
    expect(send.mock.calls.at(-1)![0]).toBe('/astrophotoflow/api/v1/equipment-management/delete-preview')
    expect(send.mock.calls.at(-1)![3]).toEqual({items:presets.map(row=>({entry_type:'capture_preset',id:row.id,revision:row.revision}))})
    await click('取消')
    expect(send.mock.calls.some(([path])=>String(path).endsWith('/delete'))).toBe(false)
  })

  it('requires a fresh preview after a deletion conflict and never resends automatically',async()=>{
    const items=[{entry_type:'equipment' as const,id:id(1),revision:1}]
    wrapper=mount(EquipmentDeleteDialog,{props:{workspaceId:'/fixture',viewKey:'one',items}});await flushPromises()
    send.mockRejectedValueOnce(new Error('PREVIEW_STALE'))
    await click('确认删除')
    expect(wrapper.text()).toContain('PREVIEW_STALE')
    expect(wrapper.findAll('button').find(button=>button.text()==='确认删除')!.attributes('disabled')).toBeDefined()
    expect(send.mock.calls.filter(([path])=>String(path).endsWith('/delete'))).toHaveLength(1)
    await click('重新读取影响');await click('确认删除')
    expect(wrapper.emitted('deleted')).toHaveLength(1)
    expect(send.mock.calls.at(-1)![3]).toEqual({items,preview_fingerprint:'current'})
  })
})
