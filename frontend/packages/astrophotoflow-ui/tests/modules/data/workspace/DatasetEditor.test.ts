import {flushPromises,mount} from '@vue/test-utils'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {nextTick} from 'vue'
import DatasetEditor from '@ui/modules/data/workspace/DatasetEditor.vue'

const {get,send}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn()}))
vi.mock('@ui/modules/data/api/index',()=>({assetApi:{get,send}}))

const createdAt='2026-10-23T20:00:00Z'
const datasetId='00000000-0000-4000-8000-000000009100'
const datasetVersionId='00000000-0000-4000-8000-000000009101'
const assetId='00000000-0000-4000-8000-000000009102'
const assetVersionId='00000000-0000-4000-8000-000000009103'
const version={
  id:assetVersionId,asset_id:assetId,version_number:1,storage_mode:'reference',storage_location:'test/member.fits',
  byte_size:1,content_hash:null,availability:'available',camera_id:null,optical_system_id:null,filter_id:null,
  frame_type:'light',calibration_level:null,capture_snapshot:null,scientific_metadata:null,created_at:createdAt
}
const asset={
  id:assetId,name:'Member.fits',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,
  current_version_id:assetVersionId,classification:{frame_class:'subframe',frame_type:'light'},
  parameters:{exposure_seconds:30},equipment_snapshot:{},value_sources:{},notes:null,status:'active',revision:1,created_at:createdAt,current_version:version
}
const member={id:'00000000-0000-4000-8000-000000009104',dataset_version_id:datasetVersionId,
  asset_version_id:assetVersionId,position:0,relative_path:null,asset,version}
const dataset={id:datasetId,name:'Test Dataset',notes:null,status:'active',revision:1,
  current_version_id:datasetVersionId,member_count:1,created_at:createdAt,updated_at:createdAt}
const datasetVersion={id:datasetVersionId,dataset_id:datasetId,version_number:1,created_at:createdAt,members:[member]}

async function doubleClick(element:Element){
  element.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:1}))
  await nextTick()
  element.dispatchEvent(new MouseEvent('click',{bubbles:true,detail:2}))
  await nextTick()
  element.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true}))
  await nextTick()
}

describe('dataset member inline editing',()=>{
  let wrapper:ReturnType<typeof mount>
  beforeEach(()=>{
    get.mockReset();send.mockReset()
    get.mockImplementation(async(path:string)=>{
      if(path.endsWith('/datasets/'+datasetId))return dataset
      if(path.endsWith('/versions/'+datasetVersionId))return datasetVersion
      if(path.includes('/library/assets'))return {items:[asset],total:1,limit:200,offset:0}
      throw new Error('Unexpected request: '+path)
    })
  })
  afterEach(()=>wrapper?.unmount())

  it('opens a member enum editor without toggling its selection',async()=>{
    wrapper=mount(DatasetEditor,{props:{datasetId},attachTo:document.body})
    await flushPromises()
    const row=wrapper.get('.apf-dataset-choice')
    const checkbox=row.get('input[type="checkbox"]')
    expect((checkbox.element as HTMLInputElement).checked).toBe(true)

    const status=row.findAll('.apf-inline-value').at(-1)!
    await doubleClick(status.element)
    await flushPromises()

    expect(row.find('select').exists()).toBe(true)
    expect((checkbox.element as HTMLInputElement).checked).toBe(true)
    expect(send).not.toHaveBeenCalled()
  })

  it('emits a parent refresh only after the inline save releases its busy state',async()=>{
    const events:string[]=[]
    send.mockResolvedValue({...dataset,name:'Renamed',revision:2})
    wrapper=mount(DatasetEditor,{props:{datasetId},attrs:{onSaving:(active:boolean)=>events.push(active?'saving':'idle'),onUpdated:()=>events.push('updated')}})
    await flushPromises()
    await doubleClick(wrapper.get('.apf-inline-value').element)
    const input=wrapper.get('input[type="text"]')
    await input.setValue('Renamed')
    await input.trigger('keydown',{key:'Enter'})
    await flushPromises()

    expect(send).toHaveBeenCalledWith('/astrophotoflow/api/v1/datasets/'+datasetId,expect.anything(),'PATCH',{
      base_revision:1,name:'Renamed'
    })
    expect(events.indexOf('idle')).toBeGreaterThanOrEqual(0)
    expect(events.indexOf('idle')).toBeLessThan(events.indexOf('updated'))
  })

  it('keeps a failed dataset field protected when a different field is cancelled',async()=>{
    send.mockRejectedValue(new Error('field save failed'))
    wrapper=mount(DatasetEditor,{props:{datasetId}})
    await flushPromises()
    await doubleClick(wrapper.get('.apf-inline-value').element)
    const name=wrapper.get('input[type="text"]')
    await name.setValue('Changed')
    await name.trigger('keydown',{key:'Enter'})
    await flushPromises()
    expect(wrapper.text()).toContain('field save failed')

    const notes=wrapper.findAll('.apf-inline-value').find(button=>button.element.parentElement?.parentElement?.textContent?.startsWith('备注'))!
    await doubleClick(notes.element)
    await flushPromises()
    await wrapper.get('textarea').trigger('keydown',{key:'Escape'})
    await flushPromises()

    expect(wrapper.text()).toContain('field save failed')
  })
})
