import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@frontend/App.vue'
import ImportDialog from '@frontend/workspace/ImportDialog.vue'
import {capturePresetSchema,equipmentSetupSchema,type CapturePreset,type EquipmentSetup} from '@frontend/assets/contracts'

const {get,send,upload}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),upload:vi.fn()}))
vi.mock('@frontend/assets/host-client',()=>({assetApi:{get,send,upload}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const camera={id:id(1),kind:'camera',name:'Registered camera',model:null,serial_number:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const setup=():EquipmentSetup=>({id:id(2),name:'Night rig',components:[{source:'registered',equipment_id:camera.id}],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
const preset=():CapturePreset=>({id:id(3),equipment_setup_id:id(2),name:'Light defaults',classification:{},parameters:{gain:42},notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
let setups:EquipmentSetup[]
let presets:CapturePreset[]
let wrapper:ReturnType<typeof mount>|undefined

beforeEach(()=>{
  setups=[setup()];presets=[preset()]
  get.mockReset().mockImplementation(async(path:string)=>{
    const url=new URL(path,'http://test')
    if(url.pathname.endsWith('/capabilities'))return cap
    if(url.pathname.endsWith('/equipment'))return page([camera])
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
function label(text:string){return wrapper!.findAll('label').find(item=>item.text().startsWith(text))!}
async function openSetups(){
  wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
  await wrapper.get('button[aria-label="设置"]').trigger('click');await flushPromises()
  await click('使用组合')
}

describe('settings organization',()=>{
  it.each(['组合','预设'])('preserves a dirty %s when a previously opened filter excludes its setup',async(editor)=>{
    await openSetups();await wrapper!.get('.apf-record').trigger('click');await flushPromises()
    await click('筛选')
    await wrapper!.get('.apf-management-filter-panel select').setValue('filter')
    await click(editor==='组合'?'编辑使用组合':'Light defaults')
    const name=label(editor==='组合'?'组合名称':'预设名称').get('input')
    await name.setValue('Unsaved draft');await flushPromises()
    const apply=wrapper!.findAll('.apf-management-filter-panel button').find(button=>button.text()==='应用')!
    expect(apply.attributes('disabled')).toBeDefined()
    await apply.trigger('click');await flushPromises()
    expect((name.element as HTMLInputElement).value).toBe('Unsaved draft')
    expect(wrapper!.text()).toContain('Night rig')
    expect(get.mock.calls.some(([path])=>path.includes('component_kind=filter'))).toBe(false)
    vi.spyOn(window,'confirm').mockReturnValue(true)
    await click('取消')
    expect(apply.attributes('disabled')).toBeUndefined()
    await apply.trigger('click');await flushPromises()
    expect(get.mock.calls.some(([path])=>path.includes('component_kind=filter'))).toBe(true)
  })

  it('blocks management filtering during an unchanged setup save',async()=>{
    await openSetups();await wrapper!.get('.apf-record').trigger('click');await flushPromises()
    await click('编辑使用组合')
    let complete!:(value:EquipmentSetup)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{complete=resolve}))
    await wrapper!.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
    expect(wrapper!.get('.apf-management-filter-control>button').attributes('disabled')).toBeDefined()
    complete({...setup(),revision:2});await flushPromises()
    expect(wrapper!.get('.apf-management-filter-control>button').attributes('disabled')).toBeUndefined()
  })

  it('creates registered/inline combinations and edits only their snapshot',async()=>{
    await openSetups()
    expect(wrapper!.get('.apf-management-tabs').text()).toBe('项目设备使用组合')
    await click('新建使用组合')
    await label('组合名称').get('input').setValue('Travel rig')
    await label('注册设备').get('select').setValue(camera.id)
    await click('加入注册设备');await click('添加组合内设备')
    await label('设备类别').get('select').setValue('telescope')
    await label('设备名称').get('input').setValue('Travel scope')
    await label('口径').get('input').setValue('80')
    await wrapper!.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
    const create=send.mock.calls.find(([path,_,method])=>path.endsWith('/equipment-setups')&&method==='POST')!
    expect(create[3].components).toEqual([
      {source:'registered',equipment_id:camera.id},
      {source:'inline',equipment:{kind:'telescope',name:'Travel scope',model:null,serial_number:null,notes:null,specs:{aperture_mm:80}}}
    ])
    expect(wrapper!.text()).toContain('Travel rig')
    await click('编辑使用组合')
    await label('设备名称').get('input').setValue('Revised scope')
    await wrapper!.get('form[aria-label="使用组合表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls.filter(([path])=>path.includes('/equipment/'))).toHaveLength(0)
    expect(setups.find(row=>row.name==='Travel rig')!.components[1]).toMatchObject({equipment:{name:'Revised scope'}})
  })

  it('owns presets within a combination, preserves zero and sparsity, and guards dirty drafts',async()=>{
    await openSetups();await wrapper!.get('.apf-record').trigger('click');await flushPromises()
    expect(wrapper!.text()).toContain('组合内拍摄预设')
    await click('新建拍摄预设')
    await label('预设名称').get('input').setValue('Zero gain')
    await label('Gain').get('input').setValue('0')
    expect(wrapper!.get('input[aria-label="搜索"]').attributes('disabled')).toBeDefined()
    expect(wrapper!.find('select[aria-label="状态筛选"]').exists()).toBe(false)
    expect(wrapper!.find('.apf-layout').exists()).toBe(false)
    expect(wrapper!.get('select[aria-label="每页显示数量"]').attributes('disabled')).toBeDefined()
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false)
    await click('设备')
    expect(confirm).toHaveBeenCalledOnce()
    expect(wrapper!.find('form[aria-label="拍摄预设表单"]').exists()).toBe(true)
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/equipment-setups/'+id(2)+'/presets')
    expect(send.mock.calls[0][3].parameters).toEqual({gain:0})
    expect(wrapper!.text()).toContain('Zero gain')
    await click('Zero gain')
    await label('Gain').get('input').setValue('')
    await wrapper!.get('form[aria-label="拍摄预设表单"]').trigger('submit');await flushPromises()
    expect(send.mock.calls[1][0]).toBe('/astrophotoflow/api/v1/capture-presets/'+id(5))
    expect(send.mock.calls[1][3]).toMatchObject({base_revision:1,parameters:{gain:null}})
  })

  it('offers only the current equipment categories',async()=>{
    await openSetups();await click('设备')
    await click('筛选')
    const filter=wrapper!.get('.apf-management-filter-panel select')
    expect(filter.findAll('option').map(item=>item.text())).toEqual(['全部设备','相机','望远镜','滤镜','赤道仪','配件'])
    await filter.setValue('mount');await click('应用')
    expect(get.mock.calls.at(-1)![0]).toContain('kind=mount')
    await click('添加设备')
    await wrapper!.get('.apf-editor select').setValue('mount')
    expect(wrapper!.text()).toContain('承重（kg）')
    await wrapper!.get('.apf-editor select').setValue('accessory')
    expect(wrapper!.text()).toContain('配件类型')
  })

  it('passes only the selected preset identity without copying defaults into manual fields',async()=>{
    send.mockResolvedValue({task_id:id(6),status:'queued'})
    wrapper=mount(ImportDialog,{props:{open:false,files:[new File(['fits'],'small.fits')]}})
    await wrapper.setProps({open:true});await flushPromises()
    await wrapper.get('select[aria-label="导入使用组合"]').setValue(id(2))
    await wrapper.get('select[aria-label="导入拍摄预设"]').setValue(id(3))
    await label('增益模式').get('select').setValue('gain')
    expect(label('Gain').get('input').element).toHaveProperty('value','')
    await wrapper.get('form').trigger('submit');await flushPromises()
    expect(send.mock.calls[0][3].capture_preset_id).toBe(id(3))
    expect(send.mock.calls[0][3].parameters.gain).not.toBe(42)
    await wrapper.setProps({open:false});await wrapper.setProps({open:true});await flushPromises()
    expect(wrapper.get('select[aria-label="导入使用组合"]').element).toHaveProperty('value','')
    await wrapper.get('form').trigger('submit');await flushPromises()
    expect(send.mock.calls.filter(([path])=>path.endsWith('/uploads')).at(-1)![3]).not.toHaveProperty('capture_preset_id')
  })

  it('makes adding either fixed-version reference discoverable from a selected project',async()=>{
    const project={id:id(20),name:'M31 processing',target_name:'M31',notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
    const implementation=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/projects?')?page([project]):implementation(path))
    wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
    await wrapper.get('button[aria-label="设置"]').trigger('click');await flushPromises()
    await wrapper.get('.apf-record').trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('跨夜、跨滤镜的单图和数据集')
    await click('添加单图')
    expect(wrapper.text()).toContain('单图 · 从素材库选择要固定的版本')
    expect(get.mock.calls.some(([path])=>path.includes('/library/assets?'))).toBe(true)
    await click('← 返回项目');await wrapper.get('.apf-record').trigger('click');await flushPromises()
    await click('添加数据集')
    expect(wrapper.text()).toContain('数据集 · 从素材库选择要固定的版本')
    expect(get.mock.calls.some(([path])=>new URL(path,'http://test').pathname.endsWith('/datasets'))).toBe(true)
  })
})
