import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '../assets/client'
import App from '../App.vue'
import type { Asset } from '../assets/contracts'
import realApiFixtureJson from './fixtures/dataset-groups-real-api.json?raw'
import { useWorkspaceStore } from './store'

const { get, getBlob, send } = vi.hoisted(() => ({get:vi.fn(),getBlob:vi.fn(),send:vi.fn()}))
vi.mock('../assets/host-client',()=>({assetApi:{get,getBlob,send}}))

const createdAt='2026-10-22T20:00:00Z'
const idAt=(index:number)=>'00000000-0000-4000-8000-'+String(index).padStart(12,'0')
const capabilities={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,
  capture_profile_management:true,asset_import:false,asset_reference_write:false,asset_preview:true,asset_metadata_edit:true,
  dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const page=(items:unknown[])=>({items,total:items.length,limit:50,offset:0})
const versionFor=(assetId:string,index:number):NonNullable<Asset['current_version']>=>({id:idAt(index),asset_id:assetId,version_number:1,storage_mode:'reference',
  storage_location:'test/'+index+'.fits',byte_size:100,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,
  filter_id:null,capture_profile_id:null,frame_type:'light',calibration_level:null,capture_snapshot:null,scientific_metadata:null,created_at:createdAt})
const assetFor=(index:number,name:string,revision=1):Asset=>{
  const version=versionFor(idAt(index),index+1000)
  return {id:idAt(index),name,scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,current_version_id:version.id,
    classification:{frame_class:'subframe',frame_type:'light'},parameters:{camera_id:null,optical_system_id:null,filter_id:null,
      parameter_mode:'standard',iso:null,gain:null,offset:null,exposure_seconds:30,integration_seconds:null,sensor_temperature_c:null,
      binning_x:1,binning_y:1,cfa_pattern:null},value_sources:{},notes:'Initial note',status:'active',revision,created_at:createdAt,current_version:version}
}
const member=(asset:ReturnType<typeof assetFor>,datasetVersionId:number,position:number,fixedVersionNumber?:number)=>{
  const fixedVersion=fixedVersionNumber===undefined?asset.current_version!:versionFor(asset.id,fixedVersionNumber)
  return {id:idAt(datasetVersionId+100+position),dataset_version_id:idAt(datasetVersionId),asset_version_id:fixedVersion.id,
    position,relative_path:null,asset,version:fixedVersion}
}
const dataset=(index:number,name:string,versionId:number,count:number)=>({id:idAt(index),name,notes:null,status:'active',revision:1,
  current_version_id:idAt(versionId),member_count:count,created_at:createdAt,updated_at:createdAt})
const version=(datasetId:string,index:number,members:ReturnType<typeof member>[])=>({id:idAt(index),dataset_id:datasetId,version_number:1,created_at:createdAt,members})
const realApiFixture=JSON.parse(realApiFixtureJson) as {dataset:ReturnType<typeof dataset>;version:ReturnType<typeof version>}

let wrapper:ReturnType<typeof mount>
let pinia:ReturnType<typeof createPinia>
let urlNumber=0
beforeEach(()=>{
  pinia=createPinia();setActivePinia(pinia)
  get.mockReset();getBlob.mockReset();send.mockReset();urlNumber=0
  vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}})
  class BrowserURL extends URL {}
  Object.assign(BrowserURL,{createObjectURL:vi.fn(()=>`blob:${++urlNumber}`),revokeObjectURL:vi.fn()})
  vi.stubGlobal('URL',BrowserURL)
  getBlob.mockResolvedValue(new Blob(['preview']))
  send.mockImplementation(async(path:string,_schema:unknown,_method:string,body:Record<string,any>)=>{
    const assetId=path.split('/').at(-1)!
    const asset=assets.get(assetId)!
    const updated={...asset,...(body.name!==undefined?{name:body.name}:{}),...(body.parameters?{parameters:{...asset.parameters,...body.parameters}}:{}),
      ...(body.notes!==undefined?{notes:body.notes}:{}),revision:body.base_revision+1}
    assets.set(assetId,updated)
    return updated
  })
})
afterEach(()=>{wrapper?.unmount();vi.unstubAllGlobals()})

const assets=new Map<string,ReturnType<typeof assetFor>>()
function configureLibrary(groups:Array<{dataset:ReturnType<typeof dataset>;version:ReturnType<typeof version>}>,single=assetFor(900,'unrelated.fit')){
  assets.clear()
  groups.flatMap(group=>group.version.members).forEach(item=>assets.set(item.asset.id,item.asset))
  assets.set(single.id,single)
  get.mockImplementation(async(path:string)=>{
    if(path.endsWith('/capabilities'))return capabilities
    if(path.endsWith('/library/filter-options'))return {frame_classes:[],frame_types:[],roles:['raw'],parameter_modes:[],bin_values:[],equipment:{camera_id:[],optical_system_id:[],filter_id:[]},numeric_ranges:{}}
    if(path.includes('/library/items'))return page([
      ...groups.map(group=>({entry_type:'dataset',dataset:group.dataset,version:group.version,import_issue:null})),
      {entry_type:'asset',asset:single,import_issue:null}
    ])
    const match=path.match(/\/datasets\/([^/]+)\/versions\/([^/?]+)/)
    if(match){const group=groups.find(item=>item.dataset.id===match[1]);if(group)return group.version}
    return page([])
  })
}
async function mountLibrary(){wrapper=mount(App,{global:{plugins:[pinia]}});await flushPromises()}
async function enterGroup(name:string){
  const button=wrapper.findAll('.apf-member-open').find(item=>item.text().includes('图像组'))!
  expect(button).toBeTruthy();await button.trigger('click')
  await new Promise(resolve=>setTimeout(resolve,300))
  await flushPromises()
}
describe('dataset group member table',()=>{
  it('opens a group when its row is selected but preserves inline field clicks',async()=>{
    const group=dataset(9,'Selectable group',19,1)
    const groupVersion=version(group.id,19,[member(assetFor(90,'Selectable.fit'),19,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary()
    const row=wrapper.findAll('.apf-assets-table tbody tr').find(item=>item.text().includes('Selectable group'))!

    await row.find('.apf-inline-value').trigger('click')
    expect(wrapper.get('h1').text()).toBe('素材库')
    await row.trigger('click')
    await new Promise(resolve=>setTimeout(resolve,300))
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('素材库 / Selectable group')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('Selectable.fit')
  })

  it('loads only the selected version members and restores outer library state on return',async()=>{
    const first=dataset(10,'Group A',20,2),second=dataset(11,'Group B',21,1)
    const firstVersion=version(first.id,20,[member(assetFor(100,'A-1.fit'),20,0),member(assetFor(101,'A-2.fit'),20,1)])
    const secondVersion=version(second.id,21,[member(assetFor(200,'B-only.fit'),21,0)])
    configureLibrary([{dataset:first,version:firstVersion},{dataset:second,version:secondVersion}])
    const store=useWorkspaceStore(pinia);store.query='outer-query';store.offset=10;store.pageSize=10
    await mountLibrary()
    await wrapper.findAll('.apf-sort-button').find(button=>button.text().startsWith('名称'))!.trigger('click')
    await flushPromises()
    store.offset=10
    await flushPromises()
    await enterGroup('Group A')

    expect(wrapper.get('h1').text()).toBe('素材库 / Group A')
    expect(wrapper.text()).toContain('图像组 · 2 张')
    expect(wrapper.text()).toContain('A-1.fit')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('A-2.fit')
    expect(wrapper.text()).not.toContain('B-only.fit')
    expect(wrapper.text()).not.toContain('unrelated.fit')
    expect(wrapper.get('.apf-table-scroll').classes()).toContain('detail')
    expect(get).toHaveBeenCalledWith('/astrophotoflow/api/v1/datasets/'+first.id+'/versions/'+firstVersion.id,expect.anything())

    await wrapper.get('.apf-library-view button').trigger('click')
    expect(wrapper.get('.apf-table-scroll').classes()).toContain('simple')
    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(store.query).toBe('outer-query')
    expect(store.offset).toBe(10)
    expect(store.pageSize).toBe(10)
    const outerRequest=get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0] as string
    const outerQuery=new URL(outerRequest,'http://comfy.test').searchParams
    expect(outerQuery.get('q')).toBe('outer-query')
    expect(outerQuery.get('offset')).toBe('10')
    expect(outerQuery.get('limit')).toBe('10')
    expect(outerQuery.get('sort_by')).toBe('name')
    expect(outerQuery.get('order')).toBe('asc')
  })

  it('leaves group context before loading each management module and returns to the outer library',async()=>{
    const group=dataset(12,'Navigation group',22,1)
    const groupVersion=version(group.id,22,[member(assetFor(120,'Member.fit'),22,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary();await enterGroup('Navigation group')

    await wrapper.get('nav button[aria-label="设置"]').trigger('click');await flushPromises()
    expect(get.mock.calls.some(([path])=>String(path).startsWith('/astrophotoflow/api/v1/projects?')&&String(path).includes('status=active'))).toBe(true)
    expect(wrapper.get('h1').text()).toBe('设置')
    for(const [label,path] of [['设备','/astrophotoflow/api/v1/equipment?status=active'],['拍摄设置','/astrophotoflow/api/v1/capture-profiles?status=active']] as const){
      await wrapper.findAll('.apf-management-tabs button').find(button=>button.text()===label)!.trigger('click');await flushPromises()
      expect(get.mock.calls.some(([request])=>String(request).startsWith(path.split('?')[0]+'?')&&String(request).includes('status=active'))).toBe(true)
    }
    await wrapper.get('nav button[aria-label="素材库"]').trigger('click');await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.findAll('.apf-assets-table tbody tr').some(row=>row.text().includes('Member.fit'))).toBe(false)
    expect(get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0]).toContain('sort_by=created_at')
  })

  it('closes outer filters on entry and keeps them unchanged inside the group',async()=>{
    const group=dataset(13,'Filter group',23,1)
    const groupVersion=version(group.id,23,[member(assetFor(130,'Filter member.fit'),23,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary()
    const filterButton=wrapper.findAll('button').find(button=>button.text().startsWith('筛选'))!
    await filterButton.trigger('click');await flushPromises()
    expect(wrapper.find('.apf-filter-panel').exists()).toBe(true)
    await wrapper.get('.apf-filter-panel input[type="checkbox"]').setValue(true)
    await flushPromises()
    const countBefore=filterButton.text()
    const listRequestsBefore=get.mock.calls.filter(([path])=>String(path).includes('/library/items')).length
    await enterGroup('Filter group')
    expect(wrapper.find('.apf-filter-panel').exists()).toBe(false)
    expect(wrapper.findAll('button').some(button=>button.text().startsWith('筛选'))).toBe(false)
    expect(wrapper.text()).not.toContain('筛选（')
    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click');await flushPromises()
    const restoredButton=wrapper.findAll('button').find(button=>button.text().startsWith('筛选'))!
    expect(restoredButton.text()).toBe(countBefore)
    expect(get.mock.calls.filter(([path])=>String(path).includes('/library/items')).length).toBeGreaterThan(listRequestsBefore)
    const outerRequest=get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0] as string
    expect(new URL(outerRequest,'http://comfy.test').searchParams.getAll('role')).toEqual(['raw'])
  })

  it('ignores a delayed member response after leaving the group',async()=>{
    const group=dataset(14,'Late group',24,1)
    const groupVersion=version(group.id,24,[member(assetFor(140,'Late member.fit'),24,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    let resolveVersion!:(value:ReturnType<typeof version>)=>void
    get.mockImplementation((path:string)=>{
      if(path.endsWith('/capabilities'))return Promise.resolve(capabilities)
      if(path.includes('/library/items'))return Promise.resolve(page([{entry_type:'dataset',dataset:group,version:groupVersion,import_issue:null}]))
      if(path.includes('/datasets/'+group.id+'/versions/'))return new Promise(resolve=>{resolveVersion=resolve})
      if(path.includes('/projects'))return Promise.resolve(page([]))
      return Promise.resolve(page([]))
    })
    await mountLibrary()
    await wrapper.findAll('.apf-member-open').find(button=>button.text().includes('图像组'))!.trigger('click')
    await wrapper.get('nav button[aria-label="设置"]').trigger('click');await flushPromises()
    resolveVersion(groupVersion);await flushPromises()
    expect(wrapper.get('h1').text()).toBe('设置')
    expect(wrapper.text()).not.toContain('Late group')
    expect(wrapper.text()).not.toContain('Late member.fit')
  })

  it('ignores a delayed member response after returning to the outer library',async()=>{
    const group=dataset(16,'Return late group',26,1)
    const groupVersion=version(group.id,26,[member(assetFor(160,'Return late member.fit'),26,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    let resolveVersion!:(value:ReturnType<typeof version>)=>void
    get.mockImplementation((path:string)=>{
      if(path.endsWith('/capabilities'))return Promise.resolve(capabilities)
      if(path.includes('/library/items'))return Promise.resolve(page([{entry_type:'dataset',dataset:group,version:groupVersion,import_issue:null}]))
      if(path.includes('/datasets/'+group.id+'/versions/'))return new Promise(resolve=>{resolveVersion=resolve})
      return Promise.resolve(page([]))
    })
    await mountLibrary()
    await wrapper.findAll('.apf-member-open').find(button=>button.text().includes('图像组'))!.trigger('click')
    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click');await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    resolveVersion(groupVersion);await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.text()).not.toContain('Return late member.fit')
  })

  it('ignores a delayed dataset update after leaving the group',async()=>{
    const group=dataset(15,'Late update group',25,1)
    const groupVersion=version(group.id,25,[member(assetFor(150,'Current member.fit'),25,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    let resolveDataset!:(value:ReturnType<typeof dataset>)=>void
    get.mockImplementation((path:string)=>{
      if(path.endsWith('/capabilities'))return Promise.resolve(capabilities)
      if(path.includes('/library/items'))return Promise.resolve(page([{entry_type:'dataset',dataset:group,version:groupVersion,import_issue:null}]))
      if(path==='/astrophotoflow/api/v1/datasets/'+group.id)return new Promise(resolve=>{resolveDataset=resolve})
      if(path.includes('/datasets/'+group.id+'/versions/'))return Promise.resolve(groupVersion)
      if(path.includes('/projects'))return Promise.resolve(page([]))
      return Promise.resolve(page([]))
    })
    await mountLibrary();await enterGroup('Late update group')
    await wrapper.findAll('button').find(button=>button.text()==='管理成员')!.trigger('click');await flushPromises()
    const editor=wrapper.findComponent({name:'DatasetEditor'})
    expect(editor.exists()).toBe(true)
    editor.vm.$emit('updated')
    await flushPromises()
    await wrapper.get('nav button[aria-label="设置"]').trigger('click');await flushPromises()
    resolveDataset({...group,name:'Stale renamed group'});await flushPromises()
    expect(wrapper.get('h1').text()).toBe('设置')
    expect(wrapper.text()).not.toContain('Stale renamed group')
  })

  it('searches, sorts, and paginates within the selected group',async()=>{
    const group=dataset(25,'Paged group',35,12)
    const members=Array.from({length:12},(_,position)=>member(assetFor(250+position,`Member ${String(12-position).padStart(2,'0')}.fit`),35,position))
    const groupVersion=version(group.id,35,members)
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary();await enterGroup('Paged group')

    const pageSize=wrapper.get('select[aria-label="每页显示数量"]')
    await pageSize.setValue('10')
    await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(10)
    expect(wrapper.find('.apf-assets-table tbody tr').text()).toContain('Member 12.fit')
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(2)

    const search=wrapper.get('input[aria-label="搜索"]')
    await search.setValue('Member 11.fit')
    await new Promise(resolve=>setTimeout(resolve,300))
    await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('Member 11.fit')

    await search.setValue('')
    await new Promise(resolve=>setTimeout(resolve,300))
    await flushPromises()
    await wrapper.findAll('.apf-sort-button').find(button=>button.text().startsWith('名称'))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.apf-assets-table tbody tr').text()).toContain('Member 01.fit')
  })

  it('renders real API members across pages and restores the outer query state',async()=>{
    configureLibrary([{dataset:realApiFixture.dataset,version:realApiFixture.version}])
    const store=useWorkspaceStore(pinia)
    store.query='outer search';store.offset=20;store.pageSize=20
    await mountLibrary();await enterGroup(realApiFixture.dataset.name)

    expect(realApiFixture.version.members).toHaveLength(31)
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(31)
    await wrapper.get('select[aria-label="每页显示数量"]').setValue('10');await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(10)
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click');await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(10)
    const searchedName=realApiFixture.version.members[20].asset.name
    const search=wrapper.get('input[aria-label="搜索"]')
    await search.setValue(searchedName)
    await new Promise(resolve=>setTimeout(resolve,300));await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain(searchedName)

    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click');await flushPromises()
    expect(store.query).toBe('outer search')
    expect(store.offset).toBe(20)
    expect(store.pageSize).toBe(20)
    const request=String(get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0])
    const params=new URL(request,'http://comfy.test').searchParams
    expect(params.get('q')).toBe('outer search')
    expect(params.get('offset')).toBe('20')
    expect(params.get('limit')).toBe('20')
    expect(params.get('sort_by')).toBe('created_at')
    expect(params.get('order')).toBe('desc')
  })

  it('keeps the members’ Master and video classifications intact',async()=>{
    const group=dataset(27,'Mixed classification group',37,2)
    const master={...assetFor(270,'Master.fit'),classification:{frame_class:'masterframe' as const,frame_type:'light' as const}}
    const video={...assetFor(271,'Capture video'),classification:{frame_class:'video' as const,frame_type:null}}
    const groupVersion=version(group.id,37,[member(master,37,0),member(video,37,1)])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary();await enterGroup('Mixed classification group')

    const rows=wrapper.findAll('.apf-assets-table tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].find('td:nth-child(3)').text()).toContain('masterframe')
    expect(rows[1].find('td:nth-child(3)').text()).toContain('video')
    expect(rows[1].find('td:nth-child(3)').text()).not.toContain('subframe')
  })

  it('shows the fixed member thumbnail and uses the latest asset revision for consecutive edits',async()=>{
    const group=dataset(30,'Editing group',40,2)
    const asset=assetFor(300,'Editable.fit')
    const fixed=member(asset,40,0,40)
    const untouched=member(assetFor(301,'Untouched.fit'),40,1,41)
    const groupVersion=version(group.id,40,[fixed,untouched])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary();await enterGroup('Editing group')

    const previewRequests=getBlob.mock.calls.length
    await wrapper.get('.apf-assets-table tbody tr .apf-thumb').trigger('click')
    await flushPromises()
    expect(getBlob).toHaveBeenCalledTimes(previewRequests)
    expect(wrapper.find('.apf-preview-overlay').exists()).toBe(false)
    expect(getBlob).toHaveBeenCalledWith('/astrophotoflow/api/v1/library/assets/'+asset.id+'/versions/'+fixed.version.id+'/previews/thumbnail')
    expect(get.mock.calls.some(([path])=>String(path).includes('/datasets/'+group.id+'/versions/'))).toBe(true)
    const row=wrapper.findAll('.apf-assets-table tbody tr').find(item=>item.text().includes('Editable.fit'))!
    const nameButton=row.find('.apf-inline-value')
    await nameButton.trigger('dblclick')
    let input=row.find('input')
    await input.setValue('Renamed.fit')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()
    const notesButton=row.find('td:nth-child(15) .apf-inline-value')
    await notesButton.trigger('dblclick')
    let notes=row.find('textarea')
    await notes.setValue('New saved note')
    await notes.trigger('focusin')
    notes.element.parentElement!.dispatchEvent(new FocusEvent('focusout',{bubbles:true,relatedTarget:null}))
    await flushPromises()
    expect(row.find('td:nth-child(15) .apf-inline-value').text()).toBe('New saved note')
    await row.find('td:nth-child(15) .apf-inline-value').trigger('dblclick')
    notes=row.find('textarea')
    expect((notes.element as HTMLTextAreaElement).value).toBe('New saved note')
    await notes.setValue('')
    await notes.trigger('focusin')
    notes.element.parentElement!.dispatchEvent(new FocusEvent('focusout',{bubbles:true,relatedTarget:null}))
    await flushPromises()
    expect(row.find('td:nth-child(15) .apf-inline-value').text()).toBe('未设置')
    const exposureButton=row.find('td:nth-child(6) .apf-inline-value')
    await exposureButton.trigger('dblclick')
    input=row.find('input[type="number"]')
    await input.setValue('0')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()

    expect(send).toHaveBeenCalledTimes(4)
    expect(send.mock.calls[0]).toMatchObject(['/astrophotoflow/api/v1/library/assets/'+asset.id,expect.anything(),'PATCH',{base_revision:1,name:'Renamed.fit'}])
    expect(send.mock.calls[1][3]).toEqual({base_revision:2,notes:'New saved note'})
    expect(send.mock.calls[2][3]).toEqual({base_revision:3,notes:null})
    expect(send.mock.calls[3][3]).toEqual({base_revision:4,parameters:{exposure_seconds:0}})
    expect(send.mock.calls.map(([path])=>path)).toEqual(Array(4).fill('/astrophotoflow/api/v1/library/assets/'+asset.id))
    const untouchedRow=wrapper.findAll('.apf-assets-table tbody tr').find(item=>item.text().includes('Untouched.fit'))!
    expect(untouchedRow.text()).toContain('30 s')
    expect(get.mock.calls.filter(([path])=>String(path).includes('/datasets/')&&String(path).includes('/versions/')).every(([path])=>path==='/astrophotoflow/api/v1/datasets/'+group.id+'/versions/'+fixed.dataset_version_id)).toBe(true)
  })

  it('sorts exposure and temperature numerically and keeps missing values last in either direction',async()=>{
    const group=dataset(31,'Numeric group',41,4)
    const numericMember=(index:number,name:string,exposure:number|null,temperature:number|null,position:number)=>{
      const asset=assetFor(index,name)
      asset.parameters.exposure_seconds=exposure
      asset.parameters.sensor_temperature_c=temperature
      return member(asset,41,position)
    }
    const groupVersion=version(group.id,41,[
      numericMember(310,'Half.fit',0.5,-5,0),
      numericMember(311,'Quarter.fit',0.25,-10,1),
      numericMember(312,'Zero.fit',0,0,2),
      numericMember(313,'Missing.fit',null,null,3)
    ])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary();await enterGroup('Numeric group')
    const names=()=>wrapper.findAll('.apf-assets-table tbody tr').map(row=>row.find('td:nth-child(2)').text().replace('固定版本 · light',''))
    const exposure=wrapper.findAll('.apf-sort-button').find(button=>button.text().startsWith('曝光'))!
    await exposure.trigger('click');await flushPromises()
    expect(names()).toEqual(['Zero.fit','Quarter.fit','Half.fit','Missing.fit'])
    await exposure.trigger('click');await flushPromises()
    expect(names()).toEqual(['Half.fit','Quarter.fit','Zero.fit','Missing.fit'])
    const temperature=wrapper.findAll('.apf-sort-button').find(button=>button.text().startsWith('温度'))!
    await temperature.trigger('click');await flushPromises()
    expect(names()).toEqual(['Quarter.fit','Half.fit','Zero.fit','Missing.fit'])
    await temperature.trigger('click');await flushPromises()
    expect(names()).toEqual(['Zero.fit','Half.fit','Quarter.fit','Missing.fit'])
  })

  it('sorts fractional gain numerically and keeps zero before missing in either direction',async()=>{
    const group=dataset(32,'Gain group',42,4)
    const gainMember=(index:number,name:string,gain:number|null,position:number)=>{
      const asset=assetFor(index,name)
      asset.parameters.parameter_mode='gain';asset.parameters.iso=null;asset.parameters.gain=gain
      return member(asset,42,position)
    }
    const groupVersion=version(group.id,42,[
      gainMember(320,'Half gain.fit',0.5,0),
      gainMember(321,'Quarter gain.fit',0.25,1),
      gainMember(322,'Zero gain.fit',0,2),
      gainMember(323,'Missing gain.fit',null,3)
    ])
    configureLibrary([{dataset:group,version:groupVersion}])
    await mountLibrary();await enterGroup('Gain group')
    const names=()=>wrapper.findAll('.apf-assets-table tbody tr').map(row=>row.find('td:nth-child(2)').text().replace('固定版本 · light',''))
    const parameterMode=wrapper.findAll('.apf-sort-button').find(button=>button.text().startsWith('ISO／Gain'))!
    await parameterMode.trigger('click');await flushPromises()
    expect(names()).toEqual(['Zero gain.fit','Quarter gain.fit','Half gain.fit','Missing gain.fit'])
    await parameterMode.trigger('click');await flushPromises()
    expect(names()).toEqual(['Half gain.fit','Quarter gain.fit','Zero gain.fit','Missing gain.fit'])
  })

  it('keeps a failed member edit draft and reports a revision conflict',async()=>{
    const group=dataset(45,'Conflict group',55,1)
    const asset=assetFor(450,'Conflict.fit')
    const groupVersion=version(group.id,55,[member(asset,55,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    send.mockRejectedValueOnce(new ApiClientError('记录已被其他窗口修改','service',409,'REVISION_CONFLICT'))
    await mountLibrary();await enterGroup('Conflict group')

    const row=wrapper.findAll('.apf-assets-table tbody tr').find(item=>item.text().includes('Conflict.fit'))!
    await row.find('.apf-inline-value').trigger('dblclick')
    const input=row.find('input')
    await input.setValue('Uncommitted name.fit')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()

    expect((row.find('input').element as HTMLInputElement).value).toBe('Uncommitted name.fit')
    expect(wrapper.text()).toContain('记录已被其他窗口修改')
  })

  it('waits for an outer inline save before opening a group',async()=>{
    const group=dataset(48,'Saving group',58,1)
    const groupVersion=version(group.id,58,[member(assetFor(480,'Saving member.fit'),58,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    let resolveSave!:(value:ReturnType<typeof dataset>)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
    await mountLibrary()
    const row=wrapper.findAll('.apf-assets-table tbody tr').find(item=>item.text().includes('Saving group'))!
    await row.find('.apf-inline-value').trigger('dblclick')
    const input=row.find('input')
    await input.setValue('Saved group')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)

    await row.findAll('.apf-member-open').find(button=>button.text().includes('张'))!.trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(2)

    resolveSave({...group,name:'Saved group',revision:2})
    await new Promise(resolve=>setTimeout(resolve,40))
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库 / Saved group')
    expect(wrapper.text()).toContain('Saving member.fit')
  })

  it('keeps the outer list and failed draft when any group entry is attempted',async()=>{
    const group=dataset(49,'Protected group',59,1)
    const groupVersion=version(group.id,59,[member(assetFor(490,'Protected member.fit'),59,0)])
    configureLibrary([{dataset:group,version:groupVersion}])
    send.mockRejectedValueOnce(new ApiClientError('记录已被其他窗口修改','service',409,'REVISION_CONFLICT'))
    const store=useWorkspaceStore(pinia)
    store.query='outer query';store.offset=0
    await mountLibrary()
    const row=wrapper.findAll('.apf-assets-table tbody tr').find(item=>item.text().includes('Protected group'))!
    await row.find('.apf-inline-value').trigger('dblclick')
    const input=row.find('input')
    await input.setValue('Uncommitted group')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect((row.find('input').element as HTMLInputElement).value).toBe('Uncommitted group')
    expect(row.text()).toContain('记录已被其他窗口修改')

    await row.find('.apf-thumb').trigger('click')
    await row.findAll('.apf-member-open').find(button=>button.text().includes('张'))!.trigger('click')
    await row.trigger('click')
    await flushPromises()

    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('Protected member.fit')
    expect(store.query).toBe('outer query')
    expect((row.find('input').element as HTMLInputElement).value).toBe('Uncommitted group')
    expect(row.text()).toContain('记录已被其他窗口修改')
    expect(send).toHaveBeenCalledTimes(1)
  })

  it('refreshes the group members after the manager saves a new member version',async()=>{
    const group=dataset(46,'Managed group',56,1)
    const existingAsset=assetFor(460,'Existing.fit')
    const addedAsset=assetFor(461,'Added from manager.fit')
    const single=assetFor(900,'unrelated.fit')
    const initialVersion=version(group.id,56,[member(existingAsset,56,0)])
    const updatedVersion=version(group.id,57,[member(existingAsset,57,0),member(addedAsset,57,1)])
    let currentDataset={...group}
    let currentVersion=initialVersion
    configureLibrary([{dataset:group,version:initialVersion}],single)
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([{entry_type:'dataset',dataset:currentDataset,version:currentVersion,import_issue:null},
        {entry_type:'asset',asset:single,import_issue:null}])
      if(path==='/astrophotoflow/api/v1/datasets/'+group.id)return currentDataset
      if(path.includes('/datasets/'+group.id+'/versions/'))return currentVersion
      if(path.startsWith('/astrophotoflow/api/v1/library/assets?'))return page([existingAsset,addedAsset,single])
      return page([])
    })
    send.mockImplementation(async(path:string,_schema:unknown,method:string)=>{
      expect(method).toBe('POST')
      expect(path).toBe('/astrophotoflow/api/v1/datasets/'+group.id+'/versions')
      currentVersion=updatedVersion
      currentDataset={...currentDataset,current_version_id:updatedVersion.id,member_count:2,revision:2}
      return updatedVersion
    })
    await mountLibrary();await enterGroup('Managed group')
    await wrapper.findAll('button').find(button=>button.text()==='管理成员')!.trigger('click')
    await flushPromises()

    const choices=wrapper.findAll('.apf-dataset-choice input[type="checkbox"]')
    expect(choices).toHaveLength(3)
    await choices[1].setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='保存成员版本')!.trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('图像组 · 2 张')
    expect(wrapper.text()).toContain('Added from manager.fit')
    expect(get).toHaveBeenCalledWith('/astrophotoflow/api/v1/datasets/'+group.id+'/versions/'+updatedVersion.id,expect.anything())
  })

  it('keeps a delayed member update through a search in the same group',async()=>{
    const group=dataset(47,'Search refresh group',57,1)
    const existingAsset=assetFor(470,'Existing.fit')
    const addedAsset=assetFor(471,'Added from manager.fit')
    const single=assetFor(900,'unrelated.fit')
    const initialVersion=version(group.id,57,[member(existingAsset,57,0)])
    const updatedVersion=version(group.id,58,[member(existingAsset,58,0),member(addedAsset,58,1)])
    let currentDataset={...group}
    let currentVersion=initialVersion
    let resolveDataset!:(value:ReturnType<typeof dataset>)=>void
    let datasetRequests=0
    configureLibrary([{dataset:group,version:initialVersion}],single)
    assets.set(addedAsset.id,addedAsset)
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([{entry_type:'dataset',dataset:currentDataset,version:currentVersion,import_issue:null}])
      if(path==='/astrophotoflow/api/v1/datasets/'+group.id){datasetRequests++;return datasetRequests===3?new Promise(resolve=>{resolveDataset=resolve}):currentDataset}
      if(path.includes('/datasets/'+group.id+'/versions/'))return path.endsWith('/'+initialVersion.id)?initialVersion:currentVersion
      if(path.startsWith('/astrophotoflow/api/v1/library/assets?'))return page([existingAsset,addedAsset,single])
      return page([])
    })
    send.mockImplementation(async(path:string,_schema:unknown,method:string)=>{
      expect(method).toBe('POST')
      expect(path).toBe('/astrophotoflow/api/v1/datasets/'+group.id+'/versions')
      currentVersion=updatedVersion
      currentDataset={...currentDataset,current_version_id:updatedVersion.id,member_count:2,revision:2}
      return updatedVersion
    })
    await mountLibrary();await enterGroup('Search refresh group')
    await wrapper.findAll('button').find(button=>button.text()==='管理成员')!.trigger('click');await flushPromises()
    const choices=wrapper.findAll('.apf-dataset-choice input[type="checkbox"]')
    await choices[1].setValue(true)
    await wrapper.findAll('button').find(button=>button.text()==='保存成员版本')!.trigger('click')
    await flushPromises()

    const search=wrapper.get('input[aria-label="搜索"]')
    await search.setValue('Added from manager')
    await new Promise(resolve=>setTimeout(resolve,300));await flushPromises()
    resolveDataset(currentDataset);await flushPromises()

    expect((search.element as HTMLInputElement).value).toBe('Added from manager')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('Added from manager.fit')
    expect(wrapper.text()).toContain('图像组 · 2 张')
    expect(get.mock.calls.some(([path])=>String(path).endsWith('/'+updatedVersion.id))).toBe(true)
  })

  it('keeps a delayed member update through pagination in the same group',async()=>{
    const group=dataset(48,'Page refresh group',59,1)
    const firstAsset=assetFor(480,'First.fit')
    const addedAsset=assetFor(481,'Added from manager.fit')
    const initialMembers=Array.from({length:11},(_,position)=>member(assetFor(482+position,`Existing ${position}.fit`),59,position))
    const initialVersion=version(group.id,59,initialMembers)
    const updatedVersion=version(group.id,60,[...Array.from({length:11},(_,position)=>member(assetFor(482+position,`Existing ${position}.fit`),60,position)),member(addedAsset,60,11)])
    let currentDataset={...group}
    let currentVersion=initialVersion
    let resolveDataset!:(value:ReturnType<typeof dataset>)=>void
    configureLibrary([{dataset:group,version:initialVersion}])
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([{entry_type:'dataset',dataset:currentDataset,version:currentVersion,import_issue:null}])
      if(path==='/astrophotoflow/api/v1/datasets/'+group.id)return new Promise(resolve=>{resolveDataset=resolve})
      if(path.includes('/datasets/'+group.id+'/versions/'))return path.endsWith('/'+initialVersion.id)?initialVersion:currentVersion
      return page([])
    })
    await mountLibrary();await enterGroup('Page refresh group')
    await wrapper.findAll('button').find(button=>button.text()==='管理成员')!.trigger('click');await flushPromises()
    currentVersion=updatedVersion
    currentDataset={...group,current_version_id:updatedVersion.id,member_count:12,revision:2}
    wrapper.findComponent({name:'DatasetEditor'}).vm.$emit('updated')
    await flushPromises()

    await wrapper.get('select[aria-label="每页显示数量"]').setValue('10');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click');await flushPromises()
    resolveDataset(currentDataset);await flushPromises()

    expect(wrapper.get('select[aria-label="每页显示数量"]').element).toHaveProperty('value','10')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('Added from manager.fit')
    expect(wrapper.text()).toContain('图像组 · 12 张')
    expect(get.mock.calls.some(([path])=>String(path).endsWith('/'+updatedVersion.id))).toBe(true)
  })

  it('does not apply a delayed update after leaving and re-entering the same group',async()=>{
    const group=dataset(49,'Re-enter group',61,1)
    const asset=assetFor(490,'Current.fit')
    const groupVersion=version(group.id,61,[member(asset,61,0)])
    let resolveDataset!:(value:ReturnType<typeof dataset>)=>void
    configureLibrary([{dataset:group,version:groupVersion}])
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([{entry_type:'dataset',dataset:group,version:groupVersion,import_issue:null}])
      if(path==='/astrophotoflow/api/v1/datasets/'+group.id)return new Promise(resolve=>{resolveDataset=resolve})
      if(path.includes('/datasets/'+group.id+'/versions/'))return groupVersion
      return page([])
    })
    await mountLibrary();await enterGroup('Re-enter group')
    await wrapper.findAll('button').find(button=>button.text()==='管理成员')!.trigger('click');await flushPromises()
    wrapper.findComponent({name:'DatasetEditor'}).vm.$emit('updated');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click');await flushPromises()
    await enterGroup('Re-enter group')
    resolveDataset({...group,name:'Stale name'});await flushPromises()

    expect(wrapper.get('h1').text()).toBe('素材库 / Re-enter group')
    expect(wrapper.get('h1').text()).not.toContain('Stale name')
  })

  it('keeps the newest result when dataset refreshes return out of order',async()=>{
    const group=dataset(51,'Refresh race group',63,1)
    const asset=assetFor(510,'Member.fit')
    const groupVersion=version(group.id,63,[member(asset,63,0)])
    let resolvers:Array<(value:ReturnType<typeof dataset>)=>void>=[]
    configureLibrary([{dataset:group,version:groupVersion}])
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/capabilities'))return capabilities
      if(path.includes('/library/items'))return page([{entry_type:'dataset',dataset:group,version:groupVersion,import_issue:null}])
      if(path==='/astrophotoflow/api/v1/datasets/'+group.id)return new Promise(resolve=>{resolvers.push(resolve)})
      if(path.includes('/datasets/'+group.id+'/versions/'))return groupVersion
      return page([])
    })
    await mountLibrary();await enterGroup('Refresh race group')
    await wrapper.findAll('button').find(button=>button.text()==='管理成员')!.trigger('click');await flushPromises()
    const editor=wrapper.findComponent({name:'DatasetEditor'})
    editor.vm.$emit('updated');await flushPromises()
    editor.vm.$emit('updated');await flushPromises()
    expect(resolvers).toHaveLength(3)
    resolvers[2]({...group,name:'Newest result'});await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库 / Newest result')
    resolvers[1]({...group,name:'Older result'});await flushPromises()

    expect(wrapper.get('h1').text()).toBe('素材库 / Newest result')
    expect(wrapper.get('h1').text()).not.toContain('Older result')
  })

  it('keeps a single asset thumbnail on the existing preview path and presents an empty group state',async()=>{
    const group=dataset(50,'Empty group',60,0)
    const emptyVersion=version(group.id,60,[])
    configureLibrary([{dataset:group,version:emptyVersion}])
    await mountLibrary()
    await wrapper.findAll('button').find(button=>button.text()==='图像组 · 0 张')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库 / Empty group')
    expect(wrapper.text()).toContain('此图像组当前没有成员。')
    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click')
    await flushPromises()
    const singleRow=wrapper.findAll('.apf-assets-table tbody tr').find(row=>row.text().includes('unrelated.fit'))!
    const previewRequests=getBlob.mock.calls.length
    await singleRow.get('.apf-thumb').trigger('click')
    await flushPromises()
    expect(wrapper.find('.apf-preview-overlay').exists()).toBe(false)
    expect(getBlob).toHaveBeenCalledTimes(previewRequests)
    expect(getBlob).toHaveBeenCalledWith('/astrophotoflow/api/v1/library/assets/'+idAt(900)+'/versions/'+versionFor(idAt(900),1900).id+'/previews/thumbnail')
  })

  it('cancels a pending group open when the search removes its row',async()=>{
    const group=dataset(84,'Pending group',94,1)
    const single=assetFor(900,'unrelated.fit')
    configureLibrary([{dataset:group,version:version(group.id,94,[member(assetFor(840,'Member.fit'),94,0)])}],single)
    const baseGet=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/library/items')&&path.includes('q=unrelated')
      ?page([{entry_type:'asset',asset:single,import_issue:null}]):baseGet(path))
    let resolveSave!:(value:ReturnType<typeof dataset>)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{resolveSave=resolve}))
    await mountLibrary()
    const errors:unknown[]=[]
    wrapper.vm.$.appContext.config.errorHandler=(error)=>{errors.push(error)}
    const row=wrapper.findAll('.apf-assets-table tbody tr')[0]
    await row.get('.apf-inline-value').trigger('dblclick')
    await row.get('input').setValue('Saved pending group')
    await row.get('input').trigger('keydown',{key:'Enter'});await flushPromises()
    await row.findAll('.apf-member-open').find(button=>button.text().includes('张'))!.trigger('click');await flushPromises()
    await wrapper.get('input[aria-label="搜索"]').setValue('unrelated')
    await new Promise(resolve=>setTimeout(resolve,300));await flushPromises()
    resolveSave({...group,name:'Saved pending group',revision:2});await flushPromises()
    await new Promise(resolve=>setTimeout(resolve,40));await flushPromises()

    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('unrelated.fit')
    expect(wrapper.text()).not.toContain('Pending group')
    expect(wrapper.text()).not.toContain('Member.fit')
    expect(useWorkspaceStore(pinia).query).toBe('unrelated')
    expect(errors.map(error=>String(error))).toEqual([])
  })
})
