import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {ref} from 'vue'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@ui/modules/data/App.vue'
import CalibrationBindingSelect from '@ui/modules/data/workspace/CalibrationBindingSelect.vue'
import CalibrationBindingsEditor from '@ui/modules/data/workspace/CalibrationBindingsEditor.vue'
import LibraryTrashDialog from '@ui/modules/data/workspace/LibraryTrashDialog.vue'
import WorkspaceRecords from '@ui/modules/data/workspace/WorkspaceRecords.vue'
import {calibrationBindingsSchema} from '@ui/modules/data/api/contracts'

const {get,send}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',()=>({assetApi:{get,send}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
function photo(n:number,name:string,frame_type:string|null,master=false){
  const current_version={id:id(n+100),asset_id:id(n),version_number:1,storage_mode:'reference',storage_location:name,byte_size:10,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,filter_id:null,frame_type,calibration_level:master?'master':'individual',capture_snapshot:{},scientific_metadata:null,created_at:timestamp}
  return {id:id(n),name,scope:'shared',owner_project_id:null,role:['bias','dark','flat','dark_flat'].includes(frame_type??'')?'calibration':'raw',calibration_level:master?'master':'individual',current_version_id:current_version.id,classification:{frame_class:master?'masterframe':'subframe',frame_type},parameters:{parameter_mode:'standard'},equipment_snapshot:{},value_sources:{},notes:null,status:'active',revision:1,created_at:timestamp,current_version}
}
const light=photo(1,'Master Light image','light',true)
const dark=photo(2,'Dark master image','dark',true)
const unknown=photo(3,'Unclassified image',null)
const members=[light,dark,unknown].map((asset,index)=>({id:id(200+index),dataset_version_id:id(50),asset_version_id:asset.current_version_id,position:index,relative_path:asset.name,calibration_overrides:{},asset,version:asset.current_version}))
const group={id:id(40),name:'Mixed original group',notes:'original scene',status:'active',revision:1,current_version_id:id(50),member_count:3,created_at:timestamp,updated_at:timestamp}
const oldVersion={id:id(50),dataset_id:group.id,version_number:1,created_at:timestamp,calibration_defaults:{},members}
const mixed={entry_type:'dataset',dataset:group,version:oldVersion,import_issue:null,matching_member_count:3}
const target={target:{kind:'asset_version' as const,id:dark.current_version_id},name:dark.name,frame_type:'dark' as const,version_number:1,member_count:1}
let wrapper:ReturnType<typeof mount>|undefined
beforeEach(()=>{get.mockReset().mockImplementation(async(path:string)=>{
  const url=new URL(path,'http://test')
  if(url.pathname.endsWith('/capabilities'))return cap
  if(url.pathname.endsWith('/library/items')){
    if(url.searchParams.get('role')==='calibration')return page([{...mixed,matching_member_count:1}])
    if(url.searchParams.get('frame_type')==='light')return page([{entry_type:'asset',asset:light,import_issue:null},{...mixed,matching_member_count:1}])
    return page([{entry_type:'asset',asset:unknown,import_issue:null},{entry_type:'asset',asset:light,import_issue:null},mixed])
  }
  if(url.pathname.endsWith('/library/assets'))return page([dark])
  if(url.pathname.endsWith('/datasets/'+group.id))return {...group}
  if(url.pathname.endsWith('/versions/'+oldVersion.id))return oldVersion
  if(url.pathname.endsWith('/versions'))return page([oldVersion])
  if(url.pathname.endsWith('/calibration/targets'))return page([target])
  return page([])
});send.mockReset()})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks()})
async function click(text:string){await wrapper!.findAll('button').find(button=>button.text()===text)!.trigger('click');await flushPromises()}
async function openBindings(){
  wrapper=mount(CalibrationBindingsEditor,{props:{datasetId:group.id},global:{provide:{workspace:{calibrationDirty:ref(false)}}}})
  const details=wrapper.get('details');(details.element as HTMLDetailsElement).open=true;await details.trigger('toggle');await flushPromises()
}

describe('calibration library and fixed bindings',()=>{
  it('keeps All default, separates Master Light from calibration, and opens mixed groups with complete members',async()=>{
    wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
    expect(wrapper.get('nav[aria-label="素材用途"] button[aria-current="page"]').text()).toBe('全部素材')
    expect(wrapper.text()).toContain(unknown.name)
    await click('亮场')
    expect(wrapper.text()).toContain(light.name)
    expect(wrapper.text()).not.toContain(unknown.name)
    expect(new URL(get.mock.calls.filter(([path])=>path.includes('/library/items')).at(-1)![0],'http://test').searchParams.get('frame_type')).toBe('light')
    await click('校准库')
    expect(wrapper.find('section[aria-label="独立校准素材库"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('从已有校准照片创建组')
    expect(wrapper.text()).not.toContain(light.name)
    expect(wrapper.text()).toContain('混合用途组；打开后显示全部成员')
    const records=wrapper.findComponent(WorkspaceRecords).vm as unknown as {updateDatasetMembers:(row:unknown,changes:unknown)=>Promise<void>}
    await expect(records.updateDatasetMembers({...group,...mixed,matching_member_count:1},{parameters:{exposure_seconds:60}})).rejects.toThrow('完整成员范围')
    expect(send).not.toHaveBeenCalled()
    await click('图像组 · 3 张')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(3)
    expect(wrapper.text()).toContain(light.name)
    expect(wrapper.text()).toContain(dark.name)
    expect(wrapper.text()).toContain(unknown.name)
    await click('← 返回素材库');await click('全部素材')
    expect(wrapper.text()).toContain(unknown.name)
  })

  it('explicitly creates a logical calibration group from already-imported versions',async()=>{
    const created={...group,id:id(41),name:'Dark scene',notes:'gain 0 / -10 C',current_version_id:id(51),member_count:1}
    const createdVersion={...oldVersion,id:id(51),dataset_id:created.id,members:[{...members[1],dataset_version_id:id(51)}]}
    const implementation=get.getMockImplementation()!
    let saved=false
    get.mockImplementation(async(path:string)=>{
      if(saved&&path.includes('/library/items'))return page([{...mixed,matching_member_count:1},{entry_type:'dataset',dataset:created,version:createdVersion,import_issue:null,matching_member_count:createdVersion.members.length}])
      if(path.endsWith('/datasets/'+created.id+'/versions/'+createdVersion.id))return createdVersion
      return implementation(path)
    })
    send.mockImplementation(async()=>{saved=true;return created})
    wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises();await click('校准库');await click('从已有校准照片创建组')
    const form=wrapper.get('form[aria-label="创建校准组"]')
    await form.get('input[required]').setValue(created.name);await form.get('textarea').setValue(created.notes)
    await form.get('input[type="checkbox"]').setValue(true)
    await form.trigger('submit');await flushPromises()
    expect(send.mock.calls[0]).toEqual(['/astrophotoflow/api/v1/datasets',expect.anything(),'POST',{name:created.name,notes:created.notes,asset_version_ids:[dark.current_version_id]}])
    expect(oldVersion.members.map(member=>member.asset_version_id)).toEqual([light.current_version_id,dark.current_version_id,unknown.current_version_id])
    expect(send.mock.calls.every(([path])=>!path.includes('/library/assets/'))).toBe(true)
  })

  it('saves default/inherit/null/member maps with all canonical members and keeps old versions read-only',async()=>{
    const newer={...oldVersion,id:id(52),version_number:2,calibration_defaults:{dark:target.target},members:members.map((member,index)=>({...member,dataset_version_id:id(52),calibration_overrides:index===0?{dark:null}:{}}))}
    const implementation=get.getMockImplementation()!
    let saved=false
    get.mockImplementation(async(path:string)=>path.endsWith('/datasets/'+group.id)&&saved?{...group,revision:2,current_version_id:newer.id}:implementation(path))
    send.mockImplementation(async()=>{saved=true;return newer})
    await openBindings()
    expect(wrapper!.text()).toContain('全部 3 个成员')
    await wrapper!.get('select[aria-label="组默认 dark"]').setValue('asset_version:'+dark.current_version_id)
    await wrapper!.get('select[aria-label="'+light.name+' dark"]').setValue('none')
    await click('保存校准关联为新版本')
    const body=send.mock.calls[0][3]
    expect(body.asset_version_ids).toEqual(members.map(member=>member.asset_version_id))
    expect(body.calibration_defaults).toEqual({dark:target.target})
    expect(body.member_calibration_overrides[light.current_version_id]).toEqual({dark:null})
    expect(body.member_calibration_overrides[unknown.current_version_id]).toEqual({})
    expect(oldVersion.calibration_defaults).toEqual({})
    await wrapper!.findAll('label').find(label=>label.text().startsWith('固定组版本'))!.get('select').setValue(oldVersion.id)
    expect(wrapper!.text()).toContain('历史版本只读')
    expect(wrapper!.findAll('button').find(button=>button.text()==='保存校准关联为新版本')!.attributes('disabled')).toBeDefined()
  })

  it('distinguishes missing inheritance, explicit none, and preserved historical targets without guessing',async()=>{
    expect(calibrationBindingsSchema.parse({dark:null})).toEqual({dark:null})
    wrapper=mount(CalibrationBindingSelect,{props:{modelValue:{kind:'asset_version',id:id(999)},frameType:'dark',targets:[],inherit:true,label:'member dark'}})
    expect(wrapper.text()).toContain('已固定的历史版本')
    await wrapper.get('select').setValue('inherit')
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual([undefined])
    await wrapper.get('select').setValue('none')
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual([null])
  })

  it('shows surviving calibration references and blocks the permanent-delete confirmation',async()=>{
    const item={entry_type:'asset',id:dark.id,name:dark.name,removed_at:timestamp,revision:1,current_version_id:dark.current_version_id,cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:null}
    get.mockResolvedValue(page([item]))
    send.mockResolvedValue({items:[item],references:[{id:id(900),kind:'calibration',name:'Old light group · 组默认 dark',version:1}],tasks:[],photo_count:1,managed_file_count:1,managed_bytes:10,preview_fingerprint:'protected'})
    wrapper=mount(LibraryTrashDialog,{props:{open:true}});await flushPromises()
    await wrapper.get('input[aria-label="选择 '+dark.name+'"]').setValue(true);await click('永久删除')
    expect(wrapper.text()).toContain('保留中的校准引用')
    expect(wrapper.text()).toContain('已阻止清理')
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
  })

  it('keeps the retained-target retry instruction visible after refreshing trash',async()=>{
    const item={entry_type:'asset',id:dark.id,name:dark.name,removed_at:timestamp,revision:1,current_version_id:dark.current_version_id,cleanup_status:'trash',cleanup_error:null,photo_count:1,member_asset_ids:[],groups:[],source_dataset_id:null}
    get.mockResolvedValue(page([item]))
    const reason='校准目标保留原件和版本；待所选引用组清理后可重试此照片。'
    send.mockImplementation(async(path:string)=>path.endsWith('/delete-preview')
      ?{items:[item],references:[],tasks:[],photo_count:1,managed_file_count:1,managed_bytes:10,preview_fingerprint:'retained'}
      :{deleted_count:0,deleted_entry_count:1,deleted_file_count:0,deleted_bytes:0,missing_file_count:0,failed:[{id:dark.id,error:reason}]})
    wrapper=mount(LibraryTrashDialog,{props:{open:true}});await flushPromises()
    await wrapper.get('input[aria-label="选择 '+dark.name+'"]').setValue(true);await click('永久删除');await click('确认永久删除')
    expect(wrapper.text()).toContain(reason)
    expect(wrapper.text()).toContain('1 项保留在垃圾桶中')
  })
})
