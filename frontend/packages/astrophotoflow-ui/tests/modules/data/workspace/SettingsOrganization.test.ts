import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import ImportDialog from '@ui/modules/data/workspace/ImportDialog.vue'
import {capturePresetSchema,datasetSchema,equipmentSetupSchema,type CapturePreset,type Equipment,type EquipmentSetup} from '@ui/modules/data/api/contracts'

const {get,send,upload}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),upload:vi.fn()}))
vi.mock('@ui/modules/data/api/index',()=>({assetApi:{get,send,upload}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const camera:Equipment={id:id(1),kind:'camera',name:'Registered camera',model:null,serial_number:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const setup=():EquipmentSetup=>({id:id(2),name:'Night rig',components:[{source:'registered',equipment_id:camera.id}],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
const preset=():CapturePreset=>({id:id(3),equipment_setup_id:id(2),name:'Light defaults',classification:{},parameters:{gain:42},notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
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
    const saved=capturePresetSchema.parse({...previous,...payload,id:previous?.id??id(5),equipment_setup_id:id(2),status:data.status??'active',revision:(previous?.revision??0)+1,created_at:timestamp,updated_at:timestamp})
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
    const implementation=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/projects?')?page([project]):path.includes('/datasets?')?page([group]):path.endsWith('/versions/'+version.id)?version:implementation(path))
    send.mockImplementationOnce(async(_path,_schema,_method,data)=>{
      const {base_revision:_,...patch}=data
      return datasetSchema.parse({...group,...patch,revision:4})
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
    const name=label(editor==='组合'?'组合名称':'名称前缀（可选）').get('input')
    await name.setValue('Unsaved draft');await flushPromises()
    const refresh=wrapper!.get('details button')
    expect(refresh.attributes('disabled')).toBeDefined()
    await refresh.trigger('click');await flushPromises()
    expect((name.element as HTMLInputElement).value).toBe('Unsaved draft')
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
    setups[0].components.push({source:'inline',equipment:{kind:'telescope',name:'Legacy scope',model:null,serial_number:null,notes:null,specs:{aperture_mm:80}}})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click('编辑设备组合')
    await click('编辑')
    await label('设备名称').get('input').setValue('Revised scope')
    await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls.filter(([path])=>path.includes('/equipment/'))).toHaveLength(0)
    expect(setups[0].components[1]).toMatchObject({equipment:{name:'Revised scope'}})
  })

  it('preserves untouched legacy pixel dimensions when applying only a name change',async()=>{
    setups[0].components.push({source:'inline',equipment:{kind:'camera',name:'Old inline camera',model:null,serial_number:null,notes:null,specs:{pixel_size_x_um:3.76,pixel_size_y_um:3.8}}})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('编辑设备组合');await click('编辑')
    await label('设备名称').get('input').setValue('Renamed inline camera')
    await wrapper!.get('form[aria-label="新建设备表单"]').trigger('submit');await flushPromises()
    expect(send).not.toHaveBeenCalled()
    await wrapper!.get('form[aria-label="设备组合表单"]').trigger('submit');await flushPromises()
    expect(setups[0].components[1]).toMatchObject({equipment:{name:'Renamed inline camera',specs:{pixel_size_x_um:3.76,pixel_size_y_um:3.8}}})
  })

  it('owns presets within a combination, preserves zero and sparsity, and guards dirty drafts',async()=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    expect(wrapper!.get('section[aria-label="组合拍摄预设"]').text()).toContain('新建拍摄预设')
    await click('新建拍摄预设')
    await label('名称前缀（可选）').get('input').setValue('Zero gain')
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
    expect(wrapper!.text()).toContain('Zero gain [Gain 0 · Offset 0]')
    await click('Zero gain [Gain 0 · Offset 0]')
    await label('增益（Gain）').get('input').setValue('')
    await label('Offset').get('input').setValue('')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[1][0]).toBe('/astrophotoflow/api/v1/capture-presets/'+id(5))
    expect(send.mock.calls[1][3]).toMatchObject({base_revision:1,name:'Zero gain',parameters:{gain:null,offset:null}})
  })

  it('limits preset editing to capture values and preserves hidden legacy values',async()=>{
    const original:CapturePreset={...preset(),notes:'Legacy description',classification:{frame_class:'subframe',frame_type:'light'},parameters:{
      camera_id:id(1),filter_id:id(7),parameter_mode:'gain',gain:42,offset:12,
      exposure_seconds:30,integration_seconds:300,sensor_temperature_c:-10,
      binning_x:2,binning_y:2,cfa_pattern:'RGGB'
    }}
    presets=[original]
    devices.push({...camera,id:id(7),kind:'filter',name:'Old filter'})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click(original.name)
    const form=wrapper!.get('form[aria-label="拍摄预设表单"]')
    expect(form.findAll('input[type="number"]').map(item=>item.attributes('aria-label'))).toEqual(['曝光（秒）','温度（°C）','增益（Gain）','Offset'])
    expect(form.get('select[aria-label="预设滤镜"]').element).toHaveProperty('value',id(7))
    expect(form.text()).toContain('原预设滤镜：Old filter')
    await label('曝光（秒）').get('input').setValue('60')
    await label('温度（°C）').get('input').setValue('-15')
    await label('增益（Gain）').get('input').setValue('0')
    await form.trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3]).toMatchObject({
      base_revision:1,notes:original.notes,classification:original.classification,
      parameters:{...original.parameters,exposure_seconds:60,sensor_temperature_c:-15,gain:0}
    })
  })

  it.each([['iso','ISO','400'],['gain','增益（Gain）','0']])('creates a compact %s preset and retains failed input',async(mode,field,value)=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click('新建拍摄预设')
    await label('名称前缀（可选）').get('input').setValue('Capture preset')
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

  it('selects only owned filters and updates the generated name without duplicating its suffix',async()=>{
    devices.push({...camera,id:id(7),kind:'filter',name:'Ha'}, {...camera,id:id(8),kind:'filter',name:'OIII'}, {...camera,id:id(9),kind:'filter',name:'Unrelated filter'})
    setups[0].components.push({source:'registered',equipment_id:id(7)}, {source:'registered',equipment_id:id(8)})
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises()
    await click('新建拍摄预设')
    const filters=wrapper!.get('select[aria-label="预设滤镜"]')
    expect(filters.findAll('option').map(item=>item.text())).toEqual(['使用组合默认滤镜','Ha','OIII'])
    await filters.setValue(id(8))
    await label('名称前缀（可选）').get('input').setValue('M31')
    await label('ISO／增益').get('select').setValue('gain')
    await label('增益（Gain）').get('input').setValue('100')
    await label('Offset').get('input').setValue('0')
    await label('曝光（秒）').get('input').setValue('60')
    await label('温度（°C）').get('input').setValue('-10')
    const name='M31 [OIII · 60 s · -10 °C · Gain 100 · Offset 0]'
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe(name)
    send.mockRejectedValueOnce(new Error('Preset save failed'))
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(wrapper!.get('select[aria-label="预设滤镜"]').element).toHaveProperty('value',id(8))
    expect(label('Offset').get('input').element).toHaveProperty('value','0')
    expect(label('名称前缀（可选）').get('input').element).toHaveProperty('value','M31')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[1][3]).toMatchObject({name,parameters:{filter_id:id(8),gain:100,offset:0}})
    await click(name)
    expect(label('名称前缀（可选）').get('input').element).toHaveProperty('value','M31')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe(name)
    await label('曝光（秒）').get('input').setValue('120')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[2][3]).toMatchObject({name:'M31 [OIII · 120 s · -10 °C · Gain 100 · Offset 0]',parameters:{filter_id:id(8),offset:0}})
  })

  it.each([
    {mode:'iso',field:'ISO',value:'400',suffix:'[0 s · 0 °C · ISO 400]'},
    {mode:'gain',field:'增益（Gain）',value:'0',suffix:'[0 s · 0 °C · Gain 0]'}
  ])('generates a $mode name with an optional custom prefix and zero values',async({mode,field,value,suffix})=>{
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('新建拍摄预设')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe('拍摄预设')
    await label('ISO／增益').get('select').setValue(mode)
    await label(field).get('input').setValue(value)
    await label('曝光（秒）').get('input').setValue('0')
    await label('温度（°C）').get('input').setValue('0')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe(suffix)
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3].name).toBe(suffix)
    await click(suffix)
    expect(label('名称前缀（可选）').get('input').element).toHaveProperty('value','')
    await label('名称前缀（可选）').get('input').setValue('Custom')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe('Custom '+suffix)
  })

  it('returns to the combination default filter without clearing hidden preset values',async()=>{
    devices.push({...camera,id:id(7),kind:'filter',name:'Ha'}, {...camera,id:id(8),kind:'filter',name:'OIII'})
    setups[0].components.push({source:'registered',equipment_id:id(7)}, {source:'registered',equipment_id:id(8)})
    presets=[{...preset(),parameters:{filter_id:id(8),parameter_mode:'gain',gain:0,offset:20,binning_x:2}}]
    await openSetups();await wrapper!.get('button[aria-label="查看组合 Night rig"]').trigger('click');await flushPromises();await click('Light defaults')
    await wrapper!.get('select[aria-label="预设滤镜"]').setValue('')
    expect(wrapper!.get('output[aria-label="完整预设名称"]').text()).toBe('Light defaults [Ha · Gain 0 · Offset 20]')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3].parameters).toEqual({filter_id:null,parameter_mode:'gain',gain:0,offset:20,binning_x:2})
  })

  it('offers only the current equipment categories',async()=>{
    await openSetups();await click('我的设备')
    const filter=wrapper!.get('select[aria-label="设备类别"]')
    expect(filter.findAll('option').map(item=>item.text())).toEqual(['全部设备','相机','望远镜','滤镜','赤道仪','配件'])
    await click('新建设备')
    expect(wrapper!.get('select[aria-label="设备类型"]').findAll('option').map(item=>item.element.value)).toEqual(['camera','telescope','filter','mount','accessory'])
  })

  it('passes only the selected preset identity without copying defaults into manual fields',async()=>{
    send.mockResolvedValue({task_id:id(6),status:'queued'})
    wrapper=mount(ImportDialog,{props:{open:false,files:[{root_id:'science',path:'small.fits',name:'small.fits',size:4}]}})
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
