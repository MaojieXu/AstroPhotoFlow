import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import AssetContentChange from '@ui/modules/data/assets/AssetContentChange.vue'
import { assetContentObservationSchema } from '@ui/modules/data/api/contracts'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', async () => ({ libraryApi: (await import('../../../fixtures/library-api')).createLibraryApiFixture(get), catalogApi: (await import('../../../fixtures/library-api')).createCatalogApiFixture(get), mutationApi: (await import('../../../fixtures/library-api')).createMutationApiFixture(send), trashApi: (await import('../../../fixtures/library-api')).createTrashApiFixture(get,send), importApi: (await import('../../../fixtures/library-api')).createImportApiFixture(get,send), datasetApi: (await import('../../../fixtures/library-api')).createDatasetApiFixture(get,send), assetDetailsApi: (await import('../../../fixtures/library-api')).createAssetApiFixture(get,send), assetApi: { get, send } }))
const id='00000000-0000-4000-8000-000000000001'

beforeEach(()=>{get.mockReset();send.mockReset()})

it('clears the previous asset error and ignores an observation that arrives after selection changes',async()=>{
  send.mockRejectedValueOnce(new Error('A unavailable'))
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/fixture',assetId:id,hasOriginal:true}})
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
    complete(assetContentObservationSchema.parse({asset_id:'00000000-0000-4000-8000-000000000002',base_revision:1,storage_mode:'reference',stored_hash:'blake3:'+'a'.repeat(64),state:'changed',observed_hash:'blake3:'+'b'.repeat(64),observed_byte_size:20,observed_mtime_ns:'1793223954488571800',error:null}))
    await flushPromises()
    expect(wrapper.text()).not.toContain('确认使用新内容')
    expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
    expect(wrapper.emitted('accepted')).toBeUndefined()
  }finally{wrapper.unmount()}
})

it('reports changed originals and requests restoration or reimport',async()=>{
  send.mockResolvedValueOnce({asset_id:id,base_revision:2,storage_mode:'reference',
    stored_hash:'blake3:'+'a'.repeat(64),state:'changed',observed_hash:'blake3:'+'b'.repeat(64),observed_byte_size:20,
    observed_mtime_ns:'3',error:null})
  const wrapper=mount(AssetContentChange,{props:{workspaceId:'/fixture',assetId:id,hasOriginal:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('原件内容已变化')
    expect(wrapper.text()).toContain('新素材导入')
    expect(send).toHaveBeenCalledTimes(1)
    expect(get).not.toHaveBeenCalled()
    expect(wrapper.findAll('button')).toHaveLength(1)
  }finally{wrapper.unmount()}
})
