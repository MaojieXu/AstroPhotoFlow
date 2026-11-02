import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import AssetContentChange from '@ui/modules/data/assets/AssetContentChange.vue'
import { assetContentObservationSchema } from '@ui/modules/data/api/contracts'
import { ApiClientError } from '@ui/core/api/errors'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), assetDetailsApi: (await import('../../../fixtures/library-api')).createAssetApiFixture(get,send), assetApi: { get, send } }))
const id='00000000-0000-4000-8000-000000000001'

beforeEach(()=>{get.mockReset();send.mockReset()})

it('clears the previous asset error and ignores an observation that arrives after selection changes',async()=>{
  send.mockRejectedValueOnce(new Error('A unavailable'))
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/fixture',assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('A unavailable')
    await wrapper.setProps({assetId:'00000000-0000-4000-8000-000000000002'})
    expect(wrapper.text()).not.toContain('A unavailable')
    let complete!:(value:ReturnType<typeof assetContentObservationSchema.parse>)=>void
    send.mockImplementationOnce(()=>new Promise(resolve=>{complete=resolve}))
    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.setProps({assetId:id})
    complete(assetContentObservationSchema.parse({asset_id:'00000000-0000-4000-8000-000000000002',base_version_id:id,base_revision:1,storage_mode:'reference',stored_hash:'blake3:'+'a'.repeat(64),state:'changed',observed_hash:'blake3:'+'b'.repeat(64),observed_byte_size:20,observed_mtime_ns:'1793223954488571800',error:null}))
    await flushPromises()
    expect(wrapper.text()).not.toContain('确认使用新内容')
    expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
    expect(wrapper.emitted('accepted')).toBeUndefined()
  }finally{wrapper.unmount()}
})

it('requires explicit confirmation and accepts only the observed new hash',async()=>{
  send.mockResolvedValueOnce({asset_id:id,base_version_id:id,base_revision:2,storage_mode:'reference',
    stored_hash:'blake3:'+'a'.repeat(64),state:'changed',observed_hash:'blake3:'+'b'.repeat(64),observed_byte_size:20,
    observed_mtime_ns:'3',error:null})
  send.mockResolvedValueOnce({id,name:'M31',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,
    current_version_id:id,classification:{},parameters:{},equipment_snapshot:{},value_sources:{},notes:null,
    status:'active',revision:3,created_at:'2026-10-28T12:00:00Z',current_version:null})
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/fixture',assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('检测到文件内容已变化')
    expect(send).toHaveBeenCalledTimes(1)
    await wrapper.findAll('button').find(button=>button.text()==='确认使用新内容')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[1][3]).toEqual({base_version_id:id,base_revision:2,expected_observed_hash:'blake3:'+'b'.repeat(64)})
    expect(wrapper.emitted('accepted')).toHaveLength(1)
    expect(get).not.toHaveBeenCalled()
  }finally{wrapper.unmount()}
})

it('queries the current asset after an unknown confirmation response without reposting',async()=>{
  send.mockResolvedValueOnce({asset_id:id,base_version_id:id,base_revision:2,storage_mode:'reference',
    stored_hash:'blake3:'+'a'.repeat(64),state:'changed',observed_hash:'blake3:'+'b'.repeat(64),observed_byte_size:20,
    observed_mtime_ns:'3',error:null})
  send.mockRejectedValueOnce(new Error('connection lost'))
  get.mockResolvedValueOnce({id,name:'M31',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,
    current_version_id:'00000000-0000-4000-8000-000000000002',classification:{},parameters:{},equipment_snapshot:{},
    value_sources:{},notes:null,status:'active',revision:3,created_at:'2026-10-28T12:00:00Z',
    current_version:{view_base: `/astrophotoflow/api/v1/library/assets/${id}/versions/${'00000000-0000-4000-8000-000000000002'}/previews`, id:'00000000-0000-4000-8000-000000000002',asset_id:id,version_number:2,storage_mode:'reference',
      storage_location:'roots/science/one.fits',byte_size:20,content_hash:'blake3:'+'b'.repeat(64),availability:'available',
      camera_id:null,optical_system_id:null,filter_id:null,frame_type:null,calibration_level:null,capture_snapshot:null,
      scientific_metadata:{},created_at:'2026-10-28T12:00:00Z'}})
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/fixture',assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='确认使用新内容')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(get).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('accepted')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('connection lost')
  }finally{wrapper.unmount()}
})

const changed={asset_id:id,base_version_id:id,base_revision:2,storage_mode:'reference',
  stored_hash:'blake3:'+'a'.repeat(64),state:'changed',observed_hash:'blake3:'+'b'.repeat(64),observed_byte_size:20,
  observed_mtime_ns:'3',error:null}

it('does not apply a late accepted result after workspace identity changes',async()=>{
  send.mockResolvedValueOnce(changed)
  let finish!:(value:unknown)=>void
  send.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/one',assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='确认使用新内容')!.trigger('click');await flushPromises()
    await wrapper.setProps({workspaceId:'/two'})
    finish({id,name:'M31',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,
      current_version_id:id,classification:{},parameters:{},equipment_snapshot:{},value_sources:{},notes:null,
      status:'active',revision:3,created_at:'2026-10-28T12:00:00Z',current_version:null})
    await flushPromises()
    expect(wrapper.emitted('accepted')).toBeUndefined()
    expect(wrapper.text()).not.toContain('检测到文件内容已变化')
    expect(send).toHaveBeenCalledTimes(2)
  }finally{wrapper.unmount()}
})

it('reports both uncertain acceptance and failed verification without claiming success or replaying',async()=>{
  send.mockResolvedValueOnce(changed).mockRejectedValueOnce(new Error('Connection lost'))
  get.mockRejectedValueOnce(new ApiClientError('Verification unavailable','service',503,'VERIFY_UNAVAILABLE'))
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/one',assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='确认使用新内容')!.trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('Connection lost')
    expect(wrapper.text()).toContain('Verification unavailable')
    expect(wrapper.emitted('accepted')).toBeUndefined()
    expect(send).toHaveBeenCalledTimes(2)
    expect(get).toHaveBeenCalledTimes(1)
  }finally{wrapper.unmount()}
})
