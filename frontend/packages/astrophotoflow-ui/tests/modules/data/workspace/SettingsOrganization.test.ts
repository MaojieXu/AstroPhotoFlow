import { focusManager } from '@tanstack/vue-query'
import { metadataForMembers } from '../../../fixtures/library-summary'
import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import ImportDialog from '@ui/modules/data/imports/ImportDialog.vue'
import {capturePresetSchema,datasetSchema,equipmentSetupSchema,type CapturePreset,type Equipment,type EquipmentSetup} from '@ui/modules/data/api/contracts'

const {get,send,upload}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),upload:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send,upload}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const camera:Equipment={id:id(1),kind:'camera',name:'Registered camera',model:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const setup=():EquipmentSetup=>({id:id(2),name:'Night rig',components:[{id:id(101),source:'registered',equipment_id:camera.id}],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
const preset=():CapturePreset=>({id:id(3),equipment_setup_id:id(2),name:'Light defaults',equipment_selection:{},parameters:{gain:42},status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
let setups:EquipmentSetup[]
let presets:CapturePreset[]
let devices:Equipment[]
let wrapper:ReturnType<typeof mount>|undefined

beforeEach(()=>{
  setups=[setup()];presets=[preset()];devices=[camera]
  get.mockReset().mockImplementation(async(path:string)=>{
    const url=new URL(path,'http://test')
    if(url.pathname.endsWith('/capabilities'))return cap
    if(url.pathname.endsWith('/equipment'))return page(devices)
    if(url.pathname.endsWith('/equipment-setups'))return page(setups)
    if(url.pathname.endsWith('/presets')||url.pathname.endsWith('/capture-presets'))return page(presets)
    return page([])
  })
  send.mockReset().mockImplementation(async(path:string,_schema:unknown,method:string,data:Record<string,unknown>)=>{
    if(path.includes('/equipment-setups')&&!path.endsWith('/presets')){
      const previous=method==='PATCH'?setups.find(row=>path.endsWith(row.id)):undefined
      const {base_revision:_,...payload}=data
      const saved=equipmentSetupSchema.parse({...previous,...payload,id:previous?.id??id(4),status:data.status??'active',revision:(previous?.revision??0)+1,created_at:timestamp,updated_at:timestamp})
      if(previous)setups=setups.map(row=>row.id===saved.id?saved:row)
      else setups.push(saved)
      return saved
    }
    const previous=method==='PATCH'?presets.find(row=>path.endsWith(row.id)):undefined
    const {base_revision:_,...payload}=data
    const saved=capturePresetSchema.parse({...previous,...payload,name:previous?.name??'Server-generated preset',id:previous?.id??id(5),equipment_setup_id:id(2),status:data.status??'active',revision:(previous?.revision??0)+1,created_at:timestamp,updated_at:timestamp})
    if(previous)presets=presets.map(row=>row.id===saved.id?saved:row)
    else presets.push(saved)
    return saved
  })
  upload.mockReset().mockResolvedValue(undefined)
})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks()})
async function click(text:string){await wrapper!.findAll('button').find(button=>button.text()===text)!.trigger('click');await flushPromises()}
function label(text:string){const labels=wrapper!.findAll('label');return (labels.find(item=>item.text()===text)??labels.find(item=>item.text().startsWith(text)))!}
async function openSetups(){
  wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
  await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()
  await click('设备组合')
}

describe('settings organization',()=>{
  it('edits an available project group through its dataset resource and keeps the chosen version fixed',async()=>{
    const project={id:id(20),name:'Project',target_name:'M31',notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
    const group={id:id(21),name:'Science group',notes:null,status:'active',revision:3,current_version_id:id(22),member_count:0,created_at:timestamp,updated_at:timestamp}
    const version={id:id(22),dataset_id:group.id,version_number:1,created_at:timestamp,members:[],calibration_defaults:{}}
    Object.assign(group,{summary:metadataForMembers([]),input_ready:false,current_version_number:1})
    const implementation=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/projects?')?page([project]):path.includes('/datasets?')?page([group]):path.endsWith('/versions/'+version.id)?version:implementation(path))
    send.mockImplementationOnce(async(_path,_schema,_method,data)=>{
      const {base_revision:_,...patch}=data
      Object.assign(group,patch,{revision:4});return datasetSchema.parse(group)
    })
    wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
    await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()
    await wrapper.findComponent(Workspace).vm.selectArea('settings','projects');await flushPromises()
    await wrapper.get('.apf-record').trigger('click');await click('添加图像组')
    await wrapper.get('.apf-dataset-table tbody tr').trigger('click');await flushPromises()
    const details=wrapper.get('aside[aria-label="记录详情"]')
    expect(details.text()).not.toContain('拍摄目标')
    expect(details.text()).toContain('图像组名称')
    await details.findAll('button').find(button=>button.text()==='Science group')!.trigger('keydown',{key:'Enter'})
    await details.get('input').setValue('Revised group')
    await details.get('input').trigger('keydown',{key:'Enter'});await flushPromises()
    expect(send.mock.calls[0]).toEqual(['/astrophotoflow/api/v1/datasets/'+group.id,expect.anything(),'PATCH',{base_revision:3,name:'Revised group'}])
    expect(details.text()).toContain('Revised group')
    send.mockResolvedValueOnce({...project,revision:2})
    await click('选用此图像组版本')
    expect(send.mock.calls[1][3]).toMatchObject({dataset_version_id:version.id,base_revision:1})
  })
  it.each(['组合','预设'])('preserves a dirty %s and disables refresh until the draft is closed',async(editor)=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click(editor==='组合'?'编辑设备组合':'Light defaults')
    const name=label(editor==='组合'?'组合名称':'曝光（秒）').get('input')
    const draftValue=editor==='组合'?'Unsaved draft':'60'
    await name.setValue(draftValue);await flushPromises()
    const refresh=wrapper!.get('details button')
    expect(refresh.attributes('disabled')).toBeDefined()
    await refresh.trigger('click');await flushPromises()
    expect((name.element as HTMLInputElement).value).toBe(draftValue)
    expect(wrapper!.text()).toContain('Night rig')
    vi.spyOn(window,'confirm').mockReturnValue(true)
    await click('取消')
    expect(refresh.attributes('disabled')).toBeUndefined()
  })

  it('blocks refresh during an unchanged setup save',async()=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click('编辑设备组合')
    let complete!:(value:EquipmentSetup)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{complete=resolve}))
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(wrapper!.get('details button').attributes('disabled')).toBeDefined()
    complete({...setup(),revision:2});await flushPromises()
    expect(wrapper!.get('details button').attributes('disabled')).toBeUndefined()
  })

  it('keeps legacy inline equipment editable without changing registered devices',async()=>{
    setups[0].components.push({id:id(900),source:'inline',equipment:{kind:'telescope',name:'Legacy scope',model:null,notes:null,specs:{native_focal_length_mm:480}}})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click('编辑设备组合')
    await click('编辑')
    await label('设备名称').get('input').setValue('Revised scope')
    await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls.filter(([path])=>path.includes('/equipment/'))).toHaveLength(0)
    expect(setups[0].components[1]).toMatchObject({equipment:{name:'Revised scope'}})
  })

  it('preserves inline member identity and untouched pixel size when applying a name change',async()=>{
    setups[0].components=[{id:id(12),source:'inline',equipment:{kind:'camera',name:'Old inline camera',model:null,notes:null,specs:{pixel_size_um:3.76}}}]
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('编辑设备组合');await click('编辑')
    await label('设备名称').get('input').setValue('Renamed inline camera')
    await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    expect(send).not.toHaveBeenCalled()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(setups[0].components[0]).toMatchObject({id:id(12),equipment:{name:'Renamed inline camera',specs:{pixel_size_um:3.76}}})
  })

  it('owns presets within a combination, preserves zero and sparsity, and guards dirty drafts',async()=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    expect(wrapper!.get('section[aria-label="组合拍摄预设"]').text()).toContain('新建拍摄预设')
    await click('新建拍摄预设')
    expect(wrapper!.find('select[aria-label="默认帧用途"]').exists()).toBe(false)
    expect(wrapper!.findAll('label').some(item=>item.text()==='增益（Gain）')).toBe(false)
    await label('ISO／增益').get('select').setValue('gain')
    await label('增益（Gain）').get('input').setValue('0')
    await label('Offset').get('input').setValue('0')
    await label('ISO／增益').get('select').setValue('iso')
    expect(wrapper!.findAll('label').some(item=>item.text()==='增益（Gain）')).toBe(false)
    expect(wrapper!.find('input[aria-label="Offset"]').exists()).toBe(false)
    await label('ISO／增益').get('select').setValue('gain')
    expect(label('增益（Gain）').get('input').element).toHaveProperty('value','0')
    expect(label('Offset').get('input').element).toHaveProperty('value','0')
    expect(wrapper!.get('input[aria-label="搜索"]').attributes('disabled')).toBeDefined()
    expect(wrapper!.find('select[aria-label="状态筛选"]').exists()).toBe(false)
    expect(wrapper!.find('.apf-layout').exists()).toBe(false)
    expect(wrapper!.find('select[aria-label="每页显示数量"]').exists()).toBe(false)
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
    await click('我的设备')
    expect(confirm).toHaveBeenCalledOnce()
    expect(wrapper!.find('form[aria-label="拍摄预设表单"]').exists()).toBe(true)
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/equipment-setups/'+id(2)+'/presets')
    expect(send.mock.calls[0][3].parameters).toEqual({parameter_mode:'gain',gain:0,offset:0})
    expect(wrapper!.text()).toContain('Server-generated preset')
    await click('Server-generated preset')
    await label('增益（Gain）').get('input').setValue('')
    await label('Offset').get('input').setValue('')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[1][0]).toBe('/astrophotoflow/api/v1/capture-presets/'+id(5))
    expect(send.mock.calls[1][3]).toMatchObject({base_revision:1,parameters:{gain:null,offset:null}})
  })

  it('edits capture values while preserving owned filter and allowed sparse parameters',async()=>{
    const original:CapturePreset={...preset(),equipment_selection:{filter:id(107)},parameters:{
      parameter_mode:'gain',gain:42,offset:12,
      exposure_seconds:30,sensor_temperature_c:-10
    }}
    presets=[original]
    devices.push({...camera,id:id(7),kind:'filter',specs:{},name:'Old filter'})
    setups[0].components.push({id:id(107),source:'registered',equipment_id:id(7)})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click(original.name)
    const form=wrapper!.get('form[aria-label="拍摄预设表单"]')
    expect(form.findAll('input[type="number"]').map(item=>item.attributes('aria-label'))).toEqual(['曝光（秒）','温度（°C）','增益（Gain）','Offset'])
    expect(form.get('select[aria-label="预设滤镜"]').element).toHaveProperty('value',id(107))
    expect(form.text()).toContain('Old filter')
    await label('曝光（秒）').get('input').setValue('60')
    await label('温度（°C）').get('input').setValue('-15')
    await label('增益（Gain）').get('input').setValue('0')
    await form.trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3]).toMatchObject({
      base_revision:1,equipment_selection:original.equipment_selection,
      parameters:{...original.parameters,exposure_seconds:60,sensor_temperature_c:-15,gain:0}
    })
  })

  it.each([['iso','ISO','400'],['gain','增益（Gain）','0']])('creates a compact %s preset and retains failed input',async(mode,field,value)=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click('新建拍摄预设')
    await label('ISO／增益').get('select').setValue(mode)
    await label(field).get('input').setValue(value)
    await label('曝光（秒）').get('input').setValue('30')
    await label('温度（°C）').get('input').setValue('-10')
    send.mockRejectedValueOnce(new Error('Preset save failed'))
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(wrapper!.get('form[aria-label="拍摄预设表单"]').text()).toContain('Preset save failed')
    expect(label(field).get('input').element).toHaveProperty('value',value)
    expect(send.mock.calls[0][3].parameters).toEqual({parameter_mode:mode,[mode]:Number(value),exposure_seconds:30,sensor_temperature_c:-10})
  })

  it('selects only owned filters and displays the authoritative server name after saving',async()=>{
    devices.push({...camera,id:id(7),kind:'filter',specs:{},name:'Ha'}, {...camera,id:id(8),kind:'filter',specs:{},name:'OIII'}, {...camera,id:id(9),kind:'filter',specs:{},name:'Unrelated filter'})
    setups[0].components.push({id:id(107),source:'registered',equipment_id:id(7)}, {id:id(108),source:'registered',equipment_id:id(8)})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('新建拍摄预设')
    const filters=wrapper!.get('select[aria-label="预设滤镜"]')
    expect(filters.findAll('option').map(item=>item.text())).toEqual(['使用组合默认（未指定通道 · Ha）','不使用','未指定通道 · Ha','未指定通道 · OIII'])
    expect(wrapper!.find('#preset-name').exists()).toBe(false)
    expect(wrapper!.find('select[aria-label="相机"]').exists()).toBe(false)
    expect(wrapper!.find('select[aria-label="望远镜"]').exists()).toBe(false)
    expect(wrapper!.find('select[aria-label="光学附件"]').exists()).toBe(false)
    await filters.setValue(id(108))
    await label('ISO／增益').get('select').setValue('gain')
    await label('增益（Gain）').get('input').setValue('100')
    await label('Offset').get('input').setValue('0')
    send.mockRejectedValueOnce(new Error('Preset save failed'))
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(filters.element).toHaveProperty('value',id(108))
    expect(label('Offset').get('input').element).toHaveProperty('value','0')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[1][3]).toEqual({equipment_selection:{filter:id(108)},parameters:{parameter_mode:'gain',gain:100,offset:0}})
    await click('Server-generated preset')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe('Server-generated preset')
    await label('曝光（秒）').get('input').setValue('120')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[2][3]).toMatchObject({base_revision:1,equipment_selection:{filter:id(108)},parameters:{offset:0,exposure_seconds:120}})
    expect(send.mock.calls[2][3]).not.toHaveProperty('name')
  })

  it.each([['iso','ISO','400'],['gain','增益（Gain）','0']])('submits %s zero capture values without maintaining a second name generator',async(mode,field,value)=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('新建拍摄预设')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe('保存时自动生成')
    await label('ISO／增益').get('select').setValue(mode)
    await label(field).get('input').setValue(value)
    await label('曝光（秒）').get('input').setValue('0')
    await label('温度（°C）').get('input').setValue('0')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3].parameters).toEqual({parameter_mode:mode,[mode]:Number(value),exposure_seconds:0,sensor_temperature_c:0})
    expect(send.mock.calls[0][3]).not.toHaveProperty('name')
  })

  it('selects an inline filter member while hardware stays with the combination',async()=>{
    setups[0].components.push({id:id(107),source:'inline',equipment:{kind:'filter',name:'Ha',model:null,notes:null,specs:{}}}, {id:id(108),source:'inline',equipment:{kind:'filter',name:'OIII',model:null,notes:null,specs:{}}})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('新建拍摄预设')
    await wrapper!.get('select[aria-label="预设滤镜"]').setValue(id(108))
    expect(wrapper!.find('select[aria-label="相机"]').exists()).toBe(false)
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3]).toEqual({equipment_selection:{filter:id(108)},parameters:{}})
  })

  it('restores the default filter while retaining inactive Gain and Offset draft values in standard mode',async()=>{
    devices.push({...camera,id:id(7),kind:'filter',specs:{},name:'Ha'}, {...camera,id:id(8),kind:'filter',specs:{},name:'OIII'})
    setups[0].components.push({id:id(107),source:'registered',equipment_id:id(7)}, {id:id(108),source:'registered',equipment_id:id(8)})
    presets=[{...preset(),equipment_selection:{filter:id(108)},parameters:{parameter_mode:'gain',gain:0,offset:20}}]
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('Light defaults')
    await wrapper!.get('select[aria-label="预设滤镜"]').setValue('')
    await label('ISO／增益').get('select').setValue('standard')
    expect(wrapper!.find('input[aria-label="Offset"]').exists()).toBe(false)
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3].parameters).toEqual({parameter_mode:'standard',gain:0,offset:20})
    expect(send.mock.calls[0][3].equipment_selection).toEqual({})
  })

  it('offers only the current equipment categories',async()=>{
    await openSetups();await click('我的设备')
    const filter=wrapper!.get('select[aria-label="设备类别"]')
    expect(filter.findAll('option').map(item=>item.text())).toEqual(['全部设备','相机','望远镜','滤镜'])
    await click('新建设备')
    expect(wrapper!.get('select[aria-label="设备类型"]').findAll('option').map(item=>item.element.value)).toEqual(['camera','telescope','filter'])
  })

  it.each(['updated','removed'])('keeps import selection and Gain zero when preset catalogs are %s in the background',async(change)=>{
    vi.useFakeTimers();focusManager.setFocused(true)
    wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:false,files:[{root_id:'science',path:'small.fits',name:'small.fits',size:4}]}})
    try {
      await wrapper.setProps({open:true});await flushPromises()
      await wrapper.get('select[aria-label="导入设备组合"]').setValue(id(2))
      await wrapper.get('select[aria-label="导入拍摄预设"]').setValue(id(3))
      await label('增益模式').get('select').setValue('gain')
      await label('Gain').get('input').setValue('0')
      if(change==='removed'){setups=[];presets=[]}
      else presets=presets.map(item=>({...item,name:'Updated outside this form'}))
      await vi.advanceTimersByTimeAsync(10_000);await flushPromises()
      expect(wrapper.get('select[aria-label="导入设备组合"]').element).toHaveProperty('value',id(2))
      expect(wrapper.get('select[aria-label="导入拍摄预设"]').element).toHaveProperty('value',id(3))
      expect(label('Gain').get('input').element).toHaveProperty('value','0')
      expect(wrapper.text()).toContain(change==='removed'?'不可用':'Updated outside this form')
      expect(send).not.toHaveBeenCalled()
    } finally {wrapper.unmount();wrapper=undefined;focusManager.setFocused(undefined);vi.useRealTimers()}
  })

  it('passes only the selected preset identity without copying defaults into manual fields',async()=>{
    send.mockResolvedValue({task_id:id(6),status:'queued'})
    wrapper=mount(ImportDialog,{props:{workspaceId:'/test-workspace',open:false,files:[{root_id:'science',path:'small.fits',name:'small.fits',size:4}]}})
    await wrapper.setProps({open:true});await flushPromises()
    await wrapper.get('select[aria-label="导入设备组合"]').setValue(id(2))
    await wrapper.get('select[aria-label="导入拍摄预设"]').setValue(id(3))
    await label('增益模式').get('select').setValue('gain')
    expect(label('Gain').get('input').element).toHaveProperty('value','')
    await wrapper.get('form').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3].capture_preset_id).toBe(id(3))
    expect(send.mock.calls[0][3].parameters.gain).not.toBe(42)
    await wrapper.setProps({open:false});await wrapper.setProps({open:true});await flushPromises()
    expect(wrapper.get('select[aria-label="导入设备组合"]').element).toHaveProperty('value','')
    await wrapper.get('form').trigger('submit');await flushPromises()
    expect(send.mock.calls.filter(([path])=>path.endsWith('/imports')).at(-1)![3]).not.toHaveProperty('capture_preset_id')
  })

  it('makes adding either fixed-version reference discoverable from a selected project',async()=>{
    const project={id:id(20),name:'M31 processing',target_name:'M31',notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
    const implementation=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/projects?')?page([project]):implementation(path))
    wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
    await wrapper.get('button[aria-label="设备管理"]').trigger('click');await flushPromises()
    await wrapper.findComponent(Workspace).vm.selectArea('settings','projects');await flushPromises()
    await wrapper.get('.apf-record').trigger('click');await flushPromises()
    expect(wrapper.get('button[aria-label="项目说明"]').attributes('title')).toContain('跨夜、跨滤镜的单图和图像组')
    await click('添加单图')
    expect(wrapper.text()).toContain('单图 · 从素材库选择要固定的版本')
    expect(get.mock.calls.some(([path])=>path.includes('/library/assets?'))).toBe(true)
    await click('← 返回项目');await wrapper.get('.apf-record').trigger('click');await flushPromises()
    await click('添加图像组')
    expect(wrapper.text()).toContain('图像组 · 从素材库选择要固定的版本')
    expect(get.mock.calls.some(([path])=>new URL(path,'http://test').pathname.endsWith('/datasets'))).toBe(true)
  })
})
