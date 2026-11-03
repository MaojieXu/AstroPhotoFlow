import { metadataForMembers, exposureForMembers } from '../../../fixtures/library-summary'
import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@ui/modules/data/App.vue'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import {datasetSchema,equipmentSetupSchema,type Equipment,type EquipmentSetup} from '@ui/modules/data/api/contracts'

const {get,send,upload}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),upload:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send,upload}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const camera:Equipment={id:id(1),kind:'camera',name:'Registered camera',model:null,notes:null,specs:{},status:'active',revision:1,created_at:timestamp,updated_at:timestamp}
const setup=():EquipmentSetup=>({id:id(2),name:'Night rig',components:[{id:id(101),source:'registered',equipment_id:camera.id}],notes:null,status:'active',revision:1,created_at:timestamp,updated_at:timestamp})
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
let setups:EquipmentSetup[]
let devices:Equipment[]
let wrapper:ReturnType<typeof mount>|undefined

beforeEach(()=>{
  setups=[setup()];devices=[camera]
  get.mockReset().mockImplementation(async(path:string)=>{
    const url=new URL(path,'http://test')
    if(url.pathname.endsWith('/capabilities'))return cap
    if(url.pathname.endsWith('/equipment'))return page(devices)
    if(url.pathname.endsWith('/equipment-setups'))return page(setups)
    return page([])
  })
  send.mockReset().mockImplementation(async(path:string,_schema:unknown,method:string,data:Record<string,unknown>)=>{
    if(path.includes('/equipment-setups')){
      const previous=method==='PATCH'?setups.find(row=>path.endsWith(row.id)):undefined
      const {base_revision:_,...payload}=data
      const saved=equipmentSetupSchema.parse({...previous,...payload,id:previous?.id??id(4),status:data.status??'active',revision:(previous?.revision??0)+1,created_at:timestamp,updated_at:timestamp})
      if(previous)setups=setups.map(row=>row.id===saved.id?saved:row)
      else setups.push(saved)
      return saved
    }
    throw new Error('Unexpected mutation '+path)
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
    Object.assign(group,{summary:metadataForMembers([]),exposure_summary:exposureForMembers([]),input_ready:false,current_version_number:1})
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
    send.mockResolvedValueOnce({id:id(23),project_id:project.id,dataset_id:group.id,dataset_version_id:version.id,base_revision:1,added_at:timestamp,dataset:group,version:{id:version.id,dataset_id:group.id,version_number:1,created_at:timestamp,exposure_summary:exposureForMembers([])},summary:metadataForMembers([]),input_ready:false,member_count:0})
    await click('选用此图像组版本')
    expect(send.mock.calls[1][3]).toMatchObject({dataset_version_id:version.id,base_revision:1})
  })
  it.each(['组合'])('preserves a dirty %s and disables refresh until the draft is closed',async(editor)=>{
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

})
