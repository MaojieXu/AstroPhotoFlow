import { libraryAsset as assetSummary, libraryDataset as datasetSummary } from '../../../fixtures/library-summary'
import {flushPromises,mount} from '@vue/test-utils'
import {createPinia} from 'pinia'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import App from '@ui/modules/data/App.vue'
import CalibrationLibrary from '@ui/modules/data/library/CalibrationLibrary.vue'
import CalibrationBindingSelect from '@ui/modules/data/library/CalibrationBindingSelect.vue'
import CalibrationBindingsEditor from '@ui/modules/data/datasets/CalibrationBindingsEditor.vue'
import LibraryTrashDialog from '@ui/modules/data/trash/LibraryTrashDialog.vue'
import {calibrationBindingsSchema} from '@ui/modules/data/api/contracts'
import { ApiClientError } from '@ui/core/api/errors'

const {get,send}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send),assetApi:{get,send}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const timestamp='2026-10-25T06:00:00Z'
const cap={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:true,asset_reference_write:true,asset_preview:false,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const page=(items:unknown[])=>({items,total:items.length,limit:200,offset:0})
function photo(n:number,name:string,frame_type:string|null,master=false){
  const current_version={view_base: `/astrophotoflow/api/v1/library/assets/${id(n)}/versions/${id(n+100)}/previews`, id:id(n+100),asset_id:id(n),version_number:1,storage_mode:'reference',storage_location:name,byte_size:10,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,filter_id:null,frame_type,calibration_level:master?'master':'individual',capture_snapshot:{},scientific_metadata:null,created_at:timestamp}
  return {id:id(n),name,scope:'shared',owner_project_id:null,role:['bias','dark','flat','dark_flat'].includes(frame_type??'')?'calibration':'raw',calibration_level:master?'master':'individual',current_version_id:current_version.id,classification:{frame_class:master?'masterframe':'subframe',frame_type},parameters:{parameter_mode:'standard'},equipment_snapshot:{},value_sources:{},notes:null,status:'active',revision:1,created_at:timestamp,current_version}
}
const light=photo(1,'Master Light image','light',true)
const dark=photo(2,'Dark master image','dark',true)
const unknown=photo(3,'Unclassified image',null)
const members=[light,dark,unknown].map((asset,index)=>({id:id(200+index),dataset_version_id:id(50),asset_version_id:asset.current_version_id,position:index,relative_path:asset.name,calibration_overrides:{},asset,version:asset.current_version}))
const group={id:id(40),name:'Mixed original group',notes:'original scene',status:'active',revision:1,current_version_id:id(50),member_count:3,created_at:timestamp,updated_at:timestamp}
const oldVersion={id:id(50),dataset_id:group.id,version_number:1,created_at:timestamp,calibration_defaults:{},members}
const mixed=datasetSummary(group,oldVersion,3)
Object.assign(group,{current_version_number:1,input_ready:false,summary:mixed.summary})
const target={target:{kind:'asset_version' as const,id:dark.current_version_id},name:dark.name,frame_type:'dark' as const,version_number:1,member_count:1}
let wrapper:ReturnType<typeof mount>|undefined
beforeEach(()=>{get.mockReset().mockImplementation(async(path:string)=>{
  const url=new URL(path,'http://test')
  if(url.pathname.endsWith('/capabilities'))return cap
  if(url.pathname.endsWith('/library/items')){
    if(url.searchParams.get('role')==='calibration')return page([{...mixed,matching_member_count:1}])
    if(url.searchParams.get('frame_type')==='light')return page([assetSummary(light),{...mixed,matching_member_count:1}])
    return page([assetSummary(unknown),assetSummary(light),mixed])
  }
  if(url.pathname.endsWith('/library/assets'))return page([dark])
  if(url.pathname.endsWith('/datasets/'+group.id))return {...group}
  if(url.pathname.endsWith('/versions/'+oldVersion.id+'/members'))return page(members)
  if(url.pathname.endsWith('/versions/'+oldVersion.id))return oldVersion
  if(url.pathname.endsWith('/versions')){const {members,...summary}=oldVersion;return page([summary])}
  if(url.pathname.endsWith('/calibration/targets'))return page([target])
  return page([])
});send.mockReset()})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.useRealTimers();vi.restoreAllMocks()})
async function click(text:string){await wrapper!.findAll('button').find(button=>button.text()===text)!.trigger('click');await flushPromises()}
async function openBindings(){
  wrapper=mount(CalibrationBindingsEditor,{props:{workspaceId:'/test-workspace',datasetId:group.id}})
  const details=wrapper.get('details');(details.element as HTMLDetailsElement).open=true;await details.trigger('toggle');await flushPromises()
}

describe('calibration library and fixed bindings',()=>{
  it('pauses background reads while a draft retains its original revision',async()=>{
    vi.useFakeTimers()
    await openBindings()
    await wrapper!.get('#calibration-group-name').setValue('Unsaved local name')
    const reads=get.mock.calls.length
    const implementation=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.endsWith('/datasets/'+group.id)?{...group,name:'Changed externally',revision:7}:implementation(path))
    await vi.advanceTimersByTimeAsync(20_000)
    await flushPromises()
    expect(get.mock.calls).toHaveLength(reads)
    expect((wrapper!.get('#calibration-group-name').element as HTMLInputElement).value).toBe('Unsaved local name')
    send.mockRejectedValue(new Error('REVISION_CONFLICT'))
    await click('保存组说明')
    expect(send.mock.calls[0][3]).toMatchObject({base_revision:1,name:'Unsaved local name'})
    expect(send).toHaveBeenCalledTimes(1)
    expect(wrapper!.text()).toContain('REVISION_CONFLICT')
    expect((wrapper!.get('#calibration-group-name').element as HTMLInputElement).value).toBe('Unsaved local name')
  })

  it('reports a published version separately from failed verification and only retries the read',async()=>{
    const newer={...oldVersion,id:id(52),version_number:2}
    const implementation=get.getMockImplementation()!
    let published=false,canRead=false
    get.mockImplementation(async(path:string)=>{
      if(published&&path.endsWith('/datasets/'+group.id)){
        if(!canRead)throw new ApiClientError('Metadata verification unavailable','service',503,'SERVICE_UNAVAILABLE')
        return {...group,revision:2,current_version_id:newer.id}
      }
      if(path.endsWith('/versions/'+newer.id))return newer
      return implementation(path)
    })
    send.mockImplementation(async()=>{published=true;return newer})
    await openBindings()
    await wrapper!.get('#calibration-group-name').setValue('Description still unsaved')
    await click('保存校准关联为新版本')
    expect(wrapper!.text()).toContain('已保存固定版本 v2')
    expect(wrapper!.text()).toContain('Metadata verification unavailable')
    expect(wrapper!.emitted('updated')).toBeUndefined()
    expect(wrapper!.findAll('button').find(button=>button.text()==='保存校准关联为新版本')!.attributes('disabled')).toBeDefined()
    canRead=true;await click('重新读取')
    expect(send).toHaveBeenCalledTimes(1)
    expect(wrapper!.emitted('updated')?.at(-1)?.[0]).toMatchObject({revision:2,current_version_id:newer.id})
    expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    expect((wrapper!.get('#calibration-group-name').element as HTMLInputElement).value).toBe('Description still unsaved')
    expect(wrapper!.emitted('dirty')?.at(-1)).toEqual([true])
  })

  it('cancels an outstanding full-version read when the editor closes',async()=>{
    const implementation=get.getMockImplementation()!
    let finish!:(value:typeof oldVersion)=>void
    let signal:AbortSignal|undefined
    get.mockImplementation((path:string,_schema:unknown,currentSignal:AbortSignal)=>{
      if(path.endsWith('/versions/'+oldVersion.id)){
        signal=currentSignal
        return new Promise(resolve=>{finish=resolve})
      }
      return implementation(path)
    })
    await openBindings()
    expect(signal?.aborted).toBe(false)
    const details=wrapper!.get('details')
    ;(details.element as HTMLDetailsElement).open=false
    await details.trigger('toggle');await flushPromises()
    expect(signal?.aborted).toBe(true)
    finish(oldVersion);await flushPromises()
    expect(wrapper!.emitted('updated')).toBeUndefined()
    expect(wrapper!.find('#calibration-group-name').exists()).toBe(false)
  })

  it('refreshes an untouched editor and uses the newly observed revision',async()=>{
    vi.useFakeTimers()
    await openBindings()
    const implementation=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.endsWith('/datasets/'+group.id)?{...group,name:'Observed new name',revision:7}:implementation(path))
    await vi.advanceTimersByTimeAsync(10_000);await flushPromises()
    expect((wrapper!.get('#calibration-group-name').element as HTMLInputElement).value).toBe('Observed new name')
    send.mockRejectedValue(new Error('Keep draft'))
    await wrapper!.get('#calibration-group-name').setValue('Next edit')
    await click('保存组说明')
    expect(send.mock.calls[0][3]).toMatchObject({base_revision:7,name:'Next edit'})
  })

  it('keeps All default, separates Master Light from calibration, and opens mixed groups with complete members',async()=>{
    wrapper=mount(App,{global:{plugins:[createPinia()]}});await flushPromises()
    expect(wrapper.get('[role="tablist"][aria-label="素材用途"] button[aria-current="page"]').text()).toBe('全部素材')
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
    await wrapper.get('.apf-column-exposure .apf-inline-value').trigger('dblclick')
    const exposure=wrapper.get('.apf-column-exposure input')
    await exposure.setValue('60')
    await exposure.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.get('.apf-inline-error').text()).toContain('完整成员范围')
    expect(send).not.toHaveBeenCalled()
    await exposure.trigger('keydown',{key:'Escape'})
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
      if(saved&&path.includes('/library/items'))return page([{...mixed,matching_member_count:1},datasetSummary(created,createdVersion,createdVersion.members.length)])
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
    expect(get.mock.calls.some(([path]) => new URL(path, 'http://test').pathname.endsWith('/versions/' + createdVersion.id + '/members'))).toBe(true)
  })

  it('saves default/inherit/null/member maps with all canonical members and keeps old versions read-only',async()=>{
    const newer={...oldVersion,id:id(52),version_number:2,calibration_defaults:{dark:target.target},members:members.map((member,index)=>({...member,dataset_version_id:id(52),calibration_overrides:index===0?{dark:null}:{}}))}
    const implementation=get.getMockImplementation()!
    let saved=false
    get.mockImplementation(async(path:string)=>path.endsWith('/versions/'+newer.id)?newer:path.endsWith('/datasets/'+group.id)&&saved?{...group,revision:2,current_version_id:newer.id}:implementation(path))
    send.mockImplementation(async()=>{saved=true;return newer})
    await openBindings()
    expect(wrapper!.text()).toContain('完整成员 3 张')
    expect(get.mock.calls.some(([path])=>path.endsWith('/versions/'+oldVersion.id))).toBe(true)
    await wrapper!.get('select[aria-label="组默认 暗场"]').setValue('asset_version:'+dark.current_version_id)
    await wrapper!.get('select[aria-label="'+light.name+' 暗场"]').setValue('none')
    await click('保存校准关联为新版本')
    const body=send.mock.calls[0][3]
    expect(body.asset_version_ids).toEqual(members.map(member=>member.asset_version_id))
    expect(body.calibration_defaults).toEqual({dark:target.target})
    expect(body.member_calibration_overrides[light.current_version_id]).toEqual({dark:null})
    expect(body.member_calibration_overrides[unknown.current_version_id]).toEqual({})
    expect(oldVersion.calibration_defaults).toEqual({})
    await wrapper!.findAll('label').find(label=>label.text().startsWith('固定组版本'))!.get('select').setValue(oldVersion.id)
    await flushPromises()
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
    send.mockResolvedValue({items:[item],references:[{id:id(900),kind:'calibration',name:'Old light group · 组默认 暗场',version:1}],tasks:[],photo_count:1,managed_file_count:1,managed_bytes:10,preview_fingerprint:'protected'})
    wrapper=mount(LibraryTrashDialog,{props:{open:true,workspaceId:'trash-test-workspace'}});await flushPromises()
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
    wrapper=mount(LibraryTrashDialog,{props:{open:true,workspaceId:'trash-test-workspace'}});await flushPromises()
    await wrapper.get('input[aria-label="选择 '+dark.name+'"]').setValue(true);await click('永久删除');await click('确认永久删除')
    expect(wrapper.text()).toContain(reason)
    expect(wrapper.text()).toContain('1 项保留在回收站中')
  })
  it('reports dirty state explicitly without a Workspace provider and clears it on disposal', async () => {
    await openBindings()
    await wrapper!.get('#calibration-group-name').setValue('Edited group')
    expect(wrapper!.emitted('dirty')?.at(-1)).toEqual([true])
    const editor = wrapper!
    editor.unmount()
    wrapper = undefined
    expect(editor.emitted('dirty')?.at(-1)).toEqual([false])
  })

  it('keeps the calibration draft and selected fixed version when creation fails without replay', async () => {
    send.mockRejectedValue(new Error('Request outcome unknown'))
    wrapper = mount(CalibrationLibrary, { props: { workspace: '/one', recordsLoading: false }, global: { stubs: { WorkspaceRecords: true } } })
    await click('从已有校准照片创建组')
    const form = wrapper.get('form')
    await form.get('input[required]').setValue('Retained draft')
    await form.get('input[type="checkbox"]').setValue(true)
    await form.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Request outcome unknown')
    expect((wrapper.get('input[required]').element as HTMLInputElement).value).toBe('Retained draft')
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
    expect(send).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('created')).toBeUndefined()
  })

  it('preserves selection order and hidden fixed versions when the frame-use filter changes', async () => {
    const bias = photo(7, 'Bias.fit', 'bias')
    get.mockResolvedValue(page([dark, bias]))
    send.mockResolvedValue(group)
    wrapper = mount(CalibrationLibrary, { props: { workspace: '/one', recordsLoading: false }, global: { stubs: { WorkspaceRecords: true } } })
    await click('从已有校准照片创建组')
    const form = wrapper.get('form')
    await form.get('input[required]').setValue('Ordered group')
    const choices = form.findAll('input[type="checkbox"]')
    await choices[1].setValue(true)
    await choices[0].setValue(true)
    await form.get('select').setValue('dark')
    expect(form.findAll('input[type="checkbox"]')).toHaveLength(1)
    await form.trigger('submit')
    await flushPromises()
    expect(send.mock.calls[0][3]).toMatchObject({ asset_version_ids: [bias.current_version_id, dark.current_version_id] })
    expect(wrapper.emitted('created')).toHaveLength(1)
  })

})
