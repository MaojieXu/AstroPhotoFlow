import { assetFixture } from '../../../fixtures/library-members'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import App from '@ui/modules/data/App.vue'
import { zAssetOut } from '@ui/generated/api/zod.gen'
import { libraryAsset } from '../../../fixtures/library-summary'

const {get,send,getBlob}=vi.hoisted(()=>({get:vi.fn(),send:vi.fn(),getBlob:vi.fn()}))
vi.mock('@ui/modules/data/api/index',async()=>{
  const fixture=await import('../../../fixtures/library-api')
  return {libraryApi:fixture.createLibraryApiFixture(get),catalogApi:fixture.createCatalogApiFixture(get),
    mutationApi:fixture.createMutationApiFixture(send),importApi:fixture.createImportApiFixture(get,send),
    datasetApi:fixture.createDatasetApiFixture(get,send),trashApi:fixture.createTrashApiFixture(get,send),assetApi:{get,getBlob,send}}
})
const asset=zAssetOut.parse(assetFixture({
                              id:'00000000-0000-4000-8000-000000000001',
                              name:'M31',
                              scope:'shared',
                              owner_project_id:null,
                              role:'raw',
                              calibration_level:null,
                              classification:{frame_class:'subframe',frame_type:'light'},
                              parameters:{parameter_mode:'gain',gain:10,offset:0},
                              equipment_snapshot:{},
                              value_sources:{},
                              notes:null,
                              status:'active',
                              revision:4,
                              created_at:'2026-10-28T12:00:00Z',
                              availability: 'unknown',
                              content_hash: null,
                              byte_size: null
                            }))
let current=asset
beforeEach(()=>{
  current=asset;get.mockReset();send.mockReset();getBlob.mockReset()
  get.mockImplementation(async(path:string)=>{
    if(path.endsWith('/capabilities'))return {stage:'ingestion',shared_library_read:true,project_assets_read:true,project_management:true,equipment_management:true,asset_import:false,asset_reference_write:true,asset_preview:true,asset_metadata_edit:true,dataset_management:true,asset_task_management:true,calibration_matching:false,asset_publish:false}
    if(path.includes('/library/items'))return {items:[libraryAsset(current)],total:1,limit:50,offset:0}
    if(path.includes('/filter-options'))return {frame_classes:[],frame_types:[],roles:[],parameter_modes:[],bin_values:[],equipment:{camera_id:[],optical_system_id:[],filter_id:[]}}
    return {items:[],total:0,limit:200,offset:0}
  })
})

it('saves zero gain from the live Workspace without resending offset, classification or a content version',async()=>{
  send.mockImplementation(async()=>{current={...asset,revision:5,parameters:{...asset.parameters,gain:0}};return current})
  const wrapper=mount(App,{global:{plugins:[createPinia()]}})
  try {
    await flushPromises()
    await wrapper.get('.apf-mode-field .apf-inline-value').trigger('dblclick');await flushPromises()
    const gain=wrapper.get('input[aria-label="Gain"]')
    await gain.setValue('0');await gain.trigger('keydown',{key:'Enter'});await flushPromises()
    expect(send).toHaveBeenCalledTimes(1)
    const [path,,method,body]=send.mock.calls[0]
    expect(path).toBe('/astrophotoflow/api/v1/library/assets/'+asset.id)
    expect(method).toBe('PATCH')
    expect(body).toEqual({base_revision:4,parameters:{gain:0}})
    expect(asset.parameters.gain).toBe(10)
    expect(wrapper.get('.apf-mode-field').text()).toContain('0')
  }finally{wrapper.unmount()}
})

it('retains a live Workspace draft and its original revision after a rejected edit',async()=>{
  send.mockRejectedValue(new Error('revision conflict'))
  const wrapper=mount(App,{global:{plugins:[createPinia()]}})
  try {
    await flushPromises()
    await wrapper.get('.apf-column-name .apf-inline-value').trigger('dblclick');await flushPromises()
    const input=wrapper.get('.apf-column-name input')
    await input.setValue('Draft name');await input.trigger('keydown',{key:'Enter'});await flushPromises()
    expect(wrapper.get('.apf-inline-error').text()).toContain('revision conflict')
    expect(input.element).toHaveProperty('value','Draft name')
    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][3]).toEqual({base_revision:4,name:'Draft name'})
    expect(asset.name).toBe('M31')
  }finally{wrapper.unmount()}
})
