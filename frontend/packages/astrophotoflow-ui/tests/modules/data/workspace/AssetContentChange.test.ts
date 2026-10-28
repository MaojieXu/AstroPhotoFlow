import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, expect, it, vi } from 'vitest'
import AssetContentChange from '@ui/modules/data/workspace/AssetContentChange.vue'

const { get, send } = vi.hoisted(() => ({ get: vi.fn(), send: vi.fn() }))
vi.mock('@ui/modules/data/api/index', () => ({ assetApi: { get, send } }))
const id='00000000-0000-4000-8000-000000000001'

beforeEach(()=>{get.mockReset();send.mockReset()})

it('requires explicit confirmation and accepts only the observed new hash',async()=>{
  send.mockResolvedValueOnce({asset_id:id,base_version_id:id,base_revision:2,storage_mode:'reference',
    stored_hash:'blake3:old',state:'changed',observed_hash:'blake3:new',observed_byte_size:20,
    observed_mtime_ns:3,error:null})
  send.mockResolvedValueOnce({id,name:'M31',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,
    current_version_id:id,classification:null,parameters:{},equipment_snapshot:{},value_sources:{},notes:null,
    status:'active',revision:3,created_at:'2026-10-28T12:00:00Z',current_version:null})
  const wrapper=mount(AssetContentChange,{props:{assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    expect(wrapper.text()).toContain('检测到文件内容已变化')
    expect(send).toHaveBeenCalledTimes(1)
    await wrapper.findAll('button').find(button=>button.text()==='确认使用新内容')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(send.mock.calls[1][3]).toEqual({base_version_id:id,base_revision:2,expected_observed_hash:'blake3:new'})
  }finally{wrapper.unmount()}
})

it('queries the current asset after an unknown confirmation response without reposting',async()=>{
  send.mockResolvedValueOnce({asset_id:id,base_version_id:id,base_revision:2,storage_mode:'reference',
    stored_hash:'blake3:old',state:'changed',observed_hash:'blake3:new',observed_byte_size:20,
    observed_mtime_ns:3,error:null})
  send.mockRejectedValueOnce(new Error('connection lost'))
  get.mockResolvedValueOnce({id,name:'M31',scope:'shared',owner_project_id:null,role:'raw',calibration_level:null,
    current_version_id:'00000000-0000-4000-8000-000000000002',classification:null,parameters:{},equipment_snapshot:{},
    value_sources:{},notes:null,status:'active',revision:3,created_at:'2026-10-28T12:00:00Z',
    current_version:{id:'00000000-0000-4000-8000-000000000002',asset_id:id,version_number:2,storage_mode:'reference',
      storage_location:'roots/science/one.fits',byte_size:20,content_hash:'blake3:new',availability:'available',
      camera_id:null,optical_system_id:null,filter_id:null,frame_type:null,calibration_level:null,capture_snapshot:null,
      scientific_metadata:{},created_at:'2026-10-28T12:00:00Z'}})
  const wrapper=mount(AssetContentChange,{props:{assetId:id,hasVersion:true}})
  try{
    await wrapper.get('button').trigger('click');await flushPromises()
    await wrapper.findAll('button').find(button=>button.text()==='确认使用新内容')!.trigger('click');await flushPromises()
    expect(send).toHaveBeenCalledTimes(2)
    expect(get).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('accepted')).toHaveLength(1)
    expect(wrapper.text()).not.toContain('connection lost')
  }finally{wrapper.unmount()}
})
