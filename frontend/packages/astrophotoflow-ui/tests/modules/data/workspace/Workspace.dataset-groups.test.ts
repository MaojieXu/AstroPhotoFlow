import { previewJpegFixture } from '../../../fixtures/library-api'
import type { DatasetMemberOut } from '@ui/generated/api/types.gen'
import { assetFixture, datasetMemberFixture } from '../../../fixtures/library-members'
import { libraryAsset, libraryDataset, metadataForMembers, exposureForMembers } from '../../../fixtures/library-summary'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '@ui/modules/data/api/client'
import App from '@ui/modules/data/App.vue'
import LibraryCanvasSource from '@ui/modules/data/library/LibraryCanvasSource.vue'
import type { Asset } from '@ui/modules/data/api/contracts'
import realApiFixtureJson from '../../../fixtures/dataset-groups-real-api.json?raw'
import { useWorkspaceStore } from '@ui/modules/data/workspace/store'

const { get, getBlob, send } = vi.hoisted(() => ({get:vi.fn(),getBlob:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), displayPreviewApi: (await import('../../../fixtures/library-api')).createDisplayPreviewApiFixture(get,send,getBlob),assetApi:{get,getBlob,send}}))

const createdAt='2026-10-22T20:00:00Z'
const idAt=(index:number)=>'00000000-0000-4000-8000-'+String(index).padStart(12,'0')
const capabilities={stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,
  asset_import:false,asset_reference_write:false,asset_preview:true,asset_metadata_edit:true,
  dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
const page=(items:unknown[])=>({items,total:items.length,limit:50,offset:0})
const assetFor=(index:number,name:string,revision=1):Asset=>assetFixture({id:idAt(index),name,
  classification:{frame_class:'subframe',frame_type:'light'},parameters:{camera_id:null,optical_system_id:null,filter_id:null,
    parameter_mode:'standard',iso:null,gain:null,offset:null,exposure_seconds:30,integration_seconds:null,sensor_temperature_c:null,
    binning_x:1,binning_y:1,cfa_pattern:null},notes:'Initial note',revision,
  storage_mode:'reference',storage_location:'test/'+index+'.fits',byte_size:100})
const member=(asset:Asset,datasetId:number,position:number)=>datasetMemberFixture(asset,idAt(datasetId),position)
const dataset=(index:number,name:string,count:number)=>({id:idAt(index),name,notes:null,status:'active',revision:1,
  calibration_status:'Unknown',calibration_counts:{UnCalibrated:0,Calibrated:0,Unknown:count},member_count:count,created_at:createdAt,updated_at:createdAt})
const contents=(members:DatasetMemberOut[])=>({members})
const realApiFixture: {dataset:ReturnType<typeof dataset>;contents:ReturnType<typeof contents>}=JSON.parse(realApiFixtureJson)

let wrapper:ReturnType<typeof mount>
let pinia:ReturnType<typeof createPinia>
let urlNumber=0
beforeEach(async()=>{
  pinia=createPinia();setActivePinia(pinia)
  get.mockReset();getBlob.mockReset();send.mockReset();urlNumber=0
  vi.stubGlobal('ResizeObserver',class{observe(){}disconnect(){}})
  class BrowserURL extends URL {}
  Object.assign(BrowserURL,{createObjectURL:vi.fn(()=>`blob:${++urlNumber}`),revokeObjectURL:vi.fn()})
  vi.stubGlobal('URL',BrowserURL)
  getBlob.mockResolvedValue(await previewJpegFixture('preview'))
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
function configureLibrary(groups:Array<{dataset:ReturnType<typeof dataset>;contents:{members:DatasetMemberOut[]}}>,single=assetFor(900,'unrelated.fit')){
  groups.forEach(group=>Object.assign(group.dataset,{summary:metadataForMembers(group.contents.members),exposure_summary:exposureForMembers(group.contents.members),input_ready:group.contents.members.length>0}))
  assets.clear()
  groups.flatMap(group=>group.contents.members).forEach(item=>assets.set(item.asset.id,assetFixture(item.asset)))
  assets.set(single.id,single)
  get.mockImplementation(async(path:string)=>{
    if(path.endsWith('/capabilities'))return capabilities
    if(path.endsWith('/library/filter-options'))return {frame_classes:[],frame_types:[],roles:['raw'],parameter_modes:[],bin_values:[],equipment:{camera_id:[],optical_system_id:[],filter_id:[]},numeric_ranges:{}}
    const currentGroups=groups.map(group=>({...group,contents:{...group.contents,members:group.contents.members.map(item=>({...item,asset:assets.get(item.asset.id)!}))}}))
    if(path.includes('/library/items'))return page([
      ...currentGroups.map(group=>libraryDataset(group.dataset,group.contents)), libraryAsset(assets.get(single.id)!)
    ])
    const match=path.match(/\/datasets\/([^/?]+)\//)
    if(match){const group=currentGroups.find(item=>item.dataset.id===match[1]);if(group){
      if(path.includes('/members?')){
        const query=new URL(path,'http://local').searchParams
        const matching=group.contents.members.filter(item=>!query.get('q')||item.asset.name.toLowerCase().includes(query.get('q')!.toLowerCase()))
        const sort=query.get('sort_by')??'position', direction=query.get('order')==='desc'?-1:1
        const sortValue=(item:typeof matching[number]):unknown=>sort==='position'?item.position:sort==='name'?item.asset.name:sort==='parameter_mode'?item.asset.parameters?.gain??item.asset.parameters?.iso:item.asset.parameters?.[sort as keyof NonNullable<Asset['parameters']>]
        matching.sort((a,b)=>{
          const left=sortValue(a),right=sortValue(b)
          if(left==null)return right==null?0:1
          if(right==null)return -1
          return (typeof left==='number'&&typeof right==='number'?left-right:String(left).localeCompare(String(right)))*direction
        })
        const offset=Number(query.get('offset')??0),limit=Number(query.get('limit')??50)
        return {items:matching.slice(offset,offset+limit),total:matching.length,limit,offset}
      }
      throw new Error('Default member browsing must not fetch a complete dataset')
    }}
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
  it('silently replaces a missing member thumbnail after background generation',async()=>{
    const group=dataset(8301,'Background thumbnails',1)
    const asset=assetFor(8303,'Background.fit')
    const fixed=member(asset,8301,0)
    configureLibrary([{dataset:group,contents:contents([fixed])}])
    let ready=false
    getBlob.mockImplementation(async(path:string)=>{
      if(path.includes('/members/')&&!ready)throw new Error('not ready')
      return previewJpegFixture('preview')
    })
    const nativeInterval=globalThis.setInterval
    let refresh:(()=>void)|undefined
    const interval=vi.spyOn(globalThis,'setInterval').mockImplementation((callback,delay,...args)=>{
      if(delay===3000&&typeof callback==='function')refresh=()=>callback(...args)
      return nativeInterval(callback,delay,...args)
    })
    try {
      await mountLibrary();await enterGroup('Background thumbnails')
      expect(wrapper.find('.apf-assets-table tbody tr .apf-thumb img').exists()).toBe(false)
      expect(refresh).toBeDefined()
      ready=true
      refresh?.()
      await flushPromises()
      expect(wrapper.find('.apf-assets-table tbody tr .apf-thumb img').exists()).toBe(true)
      expect(wrapper.find('[role="progressbar"]').exists()).toBe(false)
    } finally {
      interval.mockRestore()
    }
  })

  it('offers the dataset and member references through a whole draggable row',async()=>{
    const group=dataset(8101,'Canvas group',1)
    const asset=assetFor(8103,'Pinned canvas member.fit')
    const pinned=member(asset,8101,0)
    configureLibrary([{dataset:group,contents:contents([pinned])}])
    await mountLibrary()
    expect(wrapper.find('button[aria-label="将 Canvas group 加入画布"]').exists()).toBe(false)
    const groupSources=wrapper.findAllComponents(LibraryCanvasSource).filter(item=>item.props('source')?.id===group.id)
    expect(groupSources).toHaveLength(1)
    expect(groupSources[0].props('as')).toBe('tr')
    for(const item of groupSources)expect(item.props('source')).toEqual({entry_type:'dataset',id:group.id})
    await enterGroup('Canvas group')
    const memberSources=wrapper.findAllComponents(LibraryCanvasSource)
    expect(memberSources).toHaveLength(1)
    expect(memberSources[0].props('as')).toBe('tr')
    for(const item of memberSources)expect(item.props('source')).toEqual({entry_type:'asset',id:asset.id})
    expect(send).not.toHaveBeenCalled()
  })

  it('clicks a group member thumbnail to preview its original',async()=>{
    const group=dataset(8001,'Preview group',1)
    const asset=assetFor(8003,'Pinned member.fit')
    const pinned=member(asset,8001,0)
    configureLibrary([{dataset:group,contents:contents([pinned])}])
    await mountLibrary();await enterGroup('Preview group')
    send.mockResolvedValue({asset_id:asset.id,size:'display',status:'available',width:1080,height:720,error:null,
      stretch:{algorithm:'auto-mtf-1',input_offset:0,white_balance:[1],shadows:0,highlights:255,midtones:.2}})
    await wrapper.get('button.apf-thumb').trigger('click');await flushPromises()
    await vi.waitFor(() => expect(wrapper.find('[role="dialog"] img').exists()).toBe(true))
    expect(send.mock.calls.at(-1)![0]).toBe('/astrophotoflow/api/v1/library/assets/'+asset.id+'/previews/display/auto-stretch')
    expect(wrapper.get('[role="dialog"]').text()).toContain('Pinned member.fit')
    expect(wrapper.get('[role="dialog"] img').attributes('src')).toContain('blob:')
  })

  it('removes redundant manager entries while keeping direct group browsing',async()=>{
    const group=dataset(9001,'Direct group',1)
    configureLibrary([{dataset:group,contents:contents([member(assetFor(9003,'Direct member.fit'),9001,0)])}])
    await mountLibrary()
    expect(wrapper.text()).not.toMatch(/管理成员|编辑成员|编辑图像组成员/)
    await enterGroup('Direct group')
    expect(wrapper.text()).toContain('Direct member.fit')
    expect(wrapper.text()).not.toMatch(/管理成员|编辑成员|编辑图像组成员/)
  })

  it('opens a group when its row is selected but preserves inline field clicks',async()=>{
    const group=dataset(9,'Selectable group',1)
    const groupVersion=contents([member(assetFor(90,'Selectable.fit'),9,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
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

  it('loads only the current dataset members and restores outer library state on return',async()=>{
    const first=dataset(10,'Group A',2),second=dataset(11,'Group B',1)
    const firstVersion=contents([member(assetFor(100,'A-1.fit'),10,0),member(assetFor(101,'A-2.fit'),10,1)])
    const secondVersion=contents([member(assetFor(200,'B-only.fit'),11,0)])
    configureLibrary([{dataset:first,contents:firstVersion},{dataset:second,contents:secondVersion}])
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
    expect(get.mock.calls.map(([path])=>String(path))).toContainEqual(expect.stringContaining('/datasets/'+first.id+'/members?'))

    await wrapper.get('select[aria-label="显示方式"]').setValue('simple')
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
    const group=dataset(12,'Navigation group',1)
    const groupVersion=contents([member(assetFor(120,'Member.fit'),12,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
    await mountLibrary();await enterGroup('Navigation group')

    await wrapper.get('nav button[aria-label="设备管理"]').trigger('click');await flushPromises()
    expect(get.mock.calls.some(([path])=>String(path).startsWith('/astrophotoflow/api/v1/equipment-setups?')&&String(path).includes('status=active'))).toBe(true)
    expect(wrapper.get('h1').text()).toBe('设备管理')
    for(const [label,path] of [['我的设备','/astrophotoflow/api/v1/equipment?status=active'],['设备组合','/astrophotoflow/api/v1/equipment-setups?status=active']] as const){
      await wrapper.findAll('.apf-management-tabs button').find(button=>button.text()===label)!.trigger('click');await flushPromises()
      expect(get.mock.calls.some(([request])=>String(request).startsWith(path.split('?')[0]+'?')&&String(request).includes('status=active'))).toBe(true)
    }
    await wrapper.get('nav button[aria-label="素材库"]').trigger('click');await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.findAll('.apf-assets-table tbody tr').some(row=>row.text().includes('Member.fit'))).toBe(false)
    expect(get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0]).toContain('sort_by=created_at')
  })

  it('closes outer filters on entry and keeps them unchanged inside the group',async()=>{
    const group=dataset(13,'Filter group',1)
    const groupVersion=contents([member(assetFor(130,'Filter member.fit'),13,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
    await mountLibrary()
    const filterButton=wrapper.findAll('button').find(button=>button.text().startsWith('筛选'))!
    await filterButton.trigger('click');await flushPromises()
    expect(wrapper.find('.apf-filter-panel').exists()).toBe(true)
    const role = wrapper.findAll('.apf-filter-panel fieldset').find(group => group.get('legend').text() === '分类')!
    await role.get('input[type="checkbox"]').setValue(true)
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
    // The restored scope is still fresh: use its cache rather than force another GET.
    expect(get.mock.calls.filter(([path])=>String(path).includes('/library/items')).length).toBe(listRequestsBefore)
    expect(wrapper.get('.apf-assets-table tbody tr').text()).toContain('Filter group')
    const outerRequest=get.mock.calls.filter(([path])=>String(path).includes('/library/items')).at(-1)![0] as string
    expect(new URL(outerRequest,'http://comfy.test').searchParams.getAll('role')).toEqual(['raw'])
  })

  it('ignores a delayed member response after leaving the group',async()=>{
    const group=dataset(14,'Late group',1)
    const groupVersion=contents([member(assetFor(140,'Late member.fit'),14,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
    let resolveVersion!:(value:ReturnType<typeof page>)=>void
    get.mockImplementation((path:string)=>{
      if(path.endsWith('/capabilities'))return Promise.resolve(capabilities)
      if(path.includes('/library/items'))return Promise.resolve(page([libraryDataset(group,groupVersion)]))
      if(path.includes('/datasets/'+group.id+'/members?'))return new Promise(resolve=>{resolveVersion=resolve})
      if(path.includes('/projects'))return Promise.resolve(page([]))
      return Promise.resolve(page([]))
    })
    await mountLibrary()
    await wrapper.findAll('.apf-member-open').find(button=>button.text().includes('图像组'))!.trigger('click')
    await flushPromises()
    await wrapper.get('nav button[aria-label="设备管理"]').trigger('click');await flushPromises()
    resolveVersion(page(groupVersion.members));await flushPromises()
    expect(wrapper.get('h1').text()).toBe('设备管理')
    expect(wrapper.text()).not.toContain('Late group')
    expect(wrapper.text()).not.toContain('Late member.fit')
  })

  it('ignores a delayed member response after returning to the outer library',async()=>{
    const group=dataset(16,'Return late group',1)
    const groupVersion=contents([member(assetFor(160,'Return late member.fit'),16,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
    let resolveVersion!:(value:ReturnType<typeof page>)=>void
    get.mockImplementation((path:string)=>{
      if(path.endsWith('/capabilities'))return Promise.resolve(capabilities)
      if(path.includes('/library/items'))return Promise.resolve(page([libraryDataset(group,groupVersion)]))
      if(path.includes('/datasets/'+group.id+'/members?'))return new Promise(resolve=>{resolveVersion=resolve})
      return Promise.resolve(page([]))
    })
    await mountLibrary()
    await wrapper.findAll('.apf-member-open').find(button=>button.text().includes('图像组'))!.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='← 返回素材库')!.trigger('click');await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    resolveVersion(page(groupVersion.members));await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库')
    expect(wrapper.text()).not.toContain('Return late member.fit')
  })

  it('searches, sorts, and paginates within the selected group',async()=>{
    const group=dataset(25,'Paged group',12)
    const members=Array.from({length:12},(_,position)=>member(assetFor(250+position,`Member ${String(12-position).padStart(2,'0')}.fit`),25,position))
    const groupVersion=contents(members)
    configureLibrary([{dataset:group,contents:groupVersion}])
    await mountLibrary();await enterGroup('Paged group')

    const pageSize=wrapper.get('select[aria-label="每页数量"]')
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
    configureLibrary([{dataset:realApiFixture.dataset,contents:realApiFixture.contents}])
    const store=useWorkspaceStore(pinia)
    store.query='outer search';store.offset=20;store.pageSize=20
    await mountLibrary();await enterGroup(realApiFixture.dataset.name)

    expect(realApiFixture.contents.members).toHaveLength(31)
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(31)
    await wrapper.get('select[aria-label="每页数量"]').setValue('10');await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(10)
    await wrapper.findAll('button').find(button=>button.text()==='下一页')!.trigger('click');await flushPromises()
    expect(wrapper.findAll('.apf-assets-table tbody tr')).toHaveLength(10)
    const searchedName=realApiFixture.contents.members[20].asset.name
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

  it('shows the member thumbnail and uses the latest asset revision for consecutive edits',async()=>{
    const group=dataset(30,'Editing group',2)
    const asset=assetFor(300,'Editable.fit')
    const fixed=member(asset,30,0)
    const untouched=member(assetFor(301,'Untouched.fit'),30,1)
    const groupVersion=contents([fixed,untouched])
    configureLibrary([{dataset:group,contents:groupVersion}])
    await mountLibrary();await enterGroup('Editing group')

    expect(wrapper.get('.apf-assets-table tbody tr button.apf-thumb').element.tagName).toBe('BUTTON')
    expect(getBlob).toHaveBeenCalledWith('/astrophotoflow/api/v1/datasets/'+group.id+'/members/'+fixed.asset_id+'/thumbnail', expect.any(AbortSignal))
    expect(get.mock.calls.some(([path])=>String(path).includes('/datasets/'+group.id+'/members?'))).toBe(true)
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
    expect(get.mock.calls.filter(([path])=>String(path).includes('/datasets/')&&String(path).includes('/members?')).every(([path])=>String(path).startsWith('/astrophotoflow/api/v1/datasets/'+group.id+'/members?'))).toBe(true)
  })

  it('sorts exposure and temperature numerically and keeps missing values last in either direction',async()=>{
    const group=dataset(31,'Numeric group',4)
    const numericMember=(index:number,name:string,exposure:number|null,temperature:number|null,position:number)=>{
      const asset=assetFor(index,name)
      asset.parameters.exposure_seconds=exposure
      asset.parameters.sensor_temperature_c=temperature
      return member(asset,31,position)
    }
    const groupVersion=contents([
      numericMember(310,'Half.fit',0.5,-5,0),
      numericMember(311,'Quarter.fit',0.25,-10,1),
      numericMember(312,'Zero.fit',0,0,2),
      numericMember(313,'Missing.fit',null,null,3)
    ])
    configureLibrary([{dataset:group,contents:groupVersion}])
    await mountLibrary();await enterGroup('Numeric group')
    const names=()=>wrapper.findAll('.apf-assets-table tbody tr').map(row=>row.find('td:nth-child(2) button.apf-inline-value').text())
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
    const group=dataset(32,'Gain group',4)
    const gainMember=(index:number,name:string,gain:number|null,position:number)=>{
      const asset=assetFor(index,name)
      asset.parameters.parameter_mode='gain';asset.parameters.iso=null;asset.parameters.gain=gain
      return member(asset,32,position)
    }
    const groupVersion=contents([
      gainMember(320,'Half gain.fit',0.5,0),
      gainMember(321,'Quarter gain.fit',0.25,1),
      gainMember(322,'Zero gain.fit',0,2),
      gainMember(323,'Missing gain.fit',null,3)
    ])
    configureLibrary([{dataset:group,contents:groupVersion}])
    await mountLibrary();await enterGroup('Gain group')
    const names=()=>wrapper.findAll('.apf-assets-table tbody tr').map(row=>row.find('td:nth-child(2) button.apf-inline-value').text())
    const parameterMode=wrapper.findAll('.apf-sort-button').find(button=>button.text().startsWith('ISO／Gain'))!
    await parameterMode.trigger('click');await flushPromises()
    expect(names()).toEqual(['Zero gain.fit','Quarter gain.fit','Half gain.fit','Missing gain.fit'])
    await parameterMode.trigger('click');await flushPromises()
    expect(names()).toEqual(['Half gain.fit','Quarter gain.fit','Zero gain.fit','Missing gain.fit'])
  })

  it('keeps a failed member edit draft and reports a revision conflict',async()=>{
    const group=dataset(45,'Conflict group',1)
    const asset=assetFor(450,'Conflict.fit')
    const groupVersion=contents([member(asset,45,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
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
    const group=dataset(48,'Saving group',1)
    const groupVersion=contents([member(assetFor(480,'Saving member.fit'),48,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
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

    Object.assign(group,{name:'Saved group',revision:2});resolveSave(group)
    await new Promise(resolve=>setTimeout(resolve,40))
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('素材库 / Saved group')
    expect(wrapper.text()).toContain('Saving member.fit')
  })

  it('keeps the outer list and failed draft when any group entry is attempted',async()=>{
    const group=dataset(49,'Protected group',1)
    const groupVersion=contents([member(assetFor(490,'Protected member.fit'),49,0)])
    configureLibrary([{dataset:group,contents:groupVersion}])
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

  it('keeps a single asset thumbnail on the existing preview path and presents an empty group state',async()=>{
    const group=dataset(50,'Empty group',0)
    const emptyVersion=contents([])
    configureLibrary([{dataset:group,contents:emptyVersion}])
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
    expect(getBlob).toHaveBeenCalledWith('/astrophotoflow/api/v1/library/assets/'+idAt(900)+'/previews/thumbnail', expect.any(AbortSignal))
  })

  it('cancels a pending group open when the search removes its row',async()=>{
    const group=dataset(84,'Pending group',1)
    const single=assetFor(900,'unrelated.fit')
    configureLibrary([{dataset:group,contents:contents([member(assetFor(840,'Member.fit'),84,0)])}],single)
    const baseGet=get.getMockImplementation()!
    get.mockImplementation(async(path:string)=>path.includes('/library/items')&&path.includes('q=unrelated')
      ?page([libraryAsset(single)]):baseGet(path))
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


it('keeps content observation aware of a standalone original', async () => {
  configureLibrary([])
  await mountLibrary()
  await wrapper.findAll('.apf-assets-table tbody tr').find(row => row.text().includes('unrelated.fit'))!.trigger('click')
  await flushPromises()
  expect(wrapper.findComponent({name: 'AssetContentChange'}).props('hasOriginal')).toBe(true)
})
