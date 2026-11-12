import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { workspaceQueryKey } from '@ui/core/query/keys'
import { queryAvailabilityKey } from '@ui/core/query/availability'
import { useUpdateAsset } from '@ui/modules/data/assets/mutations'
import { useUpdateDatasetMembers } from '@ui/modules/data/datasets/mutations'
import { useArchiveManagement } from '@ui/modules/data/trash/mutations'

const { patchAsset, patchMembers, archive, members } = vi.hoisted(() => ({
  patchAsset:vi.fn(), patchMembers:vi.fn(), archive:vi.fn(), members:vi.fn()
}))
vi.mock('@ui/modules/data/api/index',()=>({mutationApi:{patchAsset,patchMembers,archive},libraryApi:{members}}))

let wrapper:ReturnType<typeof mount>|undefined
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.resetAllMocks()})
const id='00000000-0000-4000-8000-000000000001'
function setup<T>(create:()=>T){
  let owner!:T,cache!:QueryClient
  const connectionReady=ref(true)
  wrapper=mount(defineComponent({setup(){owner=create();cache=useQueryClient();return ()=>null}}),{
    global:{provide:{[queryAvailabilityKey as symbol]:connectionReady}}
  })
  for(const workspace of ['/a','/b'])for(const resource of ['library','datasets','projects','equipment','trash'])
    cache.setQueryData([...workspaceQueryKey(workspace),resource],{retained:workspace})
  return {owner,cache,connectionReady}
}

describe('owned writes and fixed-scope invalidation',()=>{
  it.each(['disconnect','reconnected','close'])('does not start a member PATCH after %s interrupts revision collection',async(mode)=>{
    const {owner,connectionReady}=setup(useUpdateDatasetMembers)
    let finish!:(value:unknown)=>void
    members.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    const pending=owner.mutateAsync({workspaceId:'/a',datasetId:id,revision:3,changes:{parameters:{gain:0}}})
    const rejected=expect(pending).rejects.toThrow('工作区身份尚未确认')
    await vi.waitFor(()=>expect(members).toHaveBeenCalledTimes(1))
    if(mode==='close'){wrapper!.unmount();wrapper=undefined}
    else {connectionReady.value=false;if(mode==='reconnected')connectionReady.value=true}
    finish({items:[{asset:{id:'first',revision:2}}],total:1,limit:200,offset:0})
    await rejected
    expect(patchMembers).not.toHaveBeenCalled()
  })
  it('invalidates the originating workspace after a delayed asset acknowledgement without changing another workspace',async()=>{
    const {owner,cache}=setup(useUpdateAsset)
    let finish!:(value:unknown)=>void
    patchAsset.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
    const body={base_revision:4,parameters:{gain:0,offset:null}}
    const pending=owner.mutateAsync({workspaceId:'/a',assetId:id,body})
    await vi.waitFor(()=>expect(patchAsset).toHaveBeenCalledTimes(1))
    cache.setQueryData([...workspaceQueryKey('/b'),'library'],{newView:true})
    cache.setQueryData([...workspaceQueryKey('/a'),'datasets','group-a','members'],{items:[{asset:{id}}]})
    cache.setQueryData([...workspaceQueryKey('/a'),'datasets','group-b','members'],{items:[{asset:{id:'other'}}]})
    finish({id,revision:5});await pending
    expect(patchAsset).toHaveBeenCalledWith(id,body)
    expect(cache.getQueryState([...workspaceQueryKey('/a'),'library'])?.isInvalidated).toBe(true)
    expect(cache.getQueryState([...workspaceQueryKey('/a'),'datasets','group-a','members'])?.isInvalidated).toBe(true)
    expect(cache.getQueryState([...workspaceQueryKey('/a'),'datasets','group-b','members'])?.isInvalidated).toBe(false)
    expect(cache.getQueryState([...workspaceQueryKey('/b'),'library'])?.isInvalidated).toBe(false)
    expect(cache.getQueryData([...workspaceQueryKey('/b'),'library'])).toEqual({newView:true})
  })

  it('reconciles an uncertain archive by invalidation without replaying it',async()=>{
    const {owner,cache}=setup(useArchiveManagement)
    archive.mockRejectedValue(new Error('Outcome unknown'))
    await expect(owner.mutateAsync({workspaceId:'/a',body:{items:[{entry_type:'project',id,revision:4}]}})).rejects.toThrow('Outcome unknown')
    expect(archive).toHaveBeenCalledTimes(1)
    expect(cache.getQueryState([...workspaceQueryKey('/a'),'projects'])?.isInvalidated).toBe(true)
    expect(cache.getQueryState([...workspaceQueryKey('/a'),'equipment'])?.isInvalidated).toBe(true)
    expect(cache.getQueryState([...workspaceQueryKey('/b'),'projects'])?.isInvalidated).toBe(false)
  })

  it('collects revisions from every current dataset page in order before exactly one member write',async()=>{
    const {owner}=setup(useUpdateDatasetMembers)
    members.mockResolvedValueOnce({items:[{asset:{id:'first',revision:2}}],total:2,limit:1,offset:0})
      .mockResolvedValueOnce({items:[{asset:{id:'second',revision:7}}],total:2,limit:1,offset:1})
    patchMembers.mockResolvedValue({dataset_id:id,revision:4,assets:[{id:'first'},{id:'second'}]})
    await owner.mutateAsync({workspaceId:'/a',datasetId:id,revision:3,changes:{parameters:{gain:0,offset:null}}})
    expect(members.mock.calls.map(call=>[call[0],call[1].offset])).toEqual([[id,0],[id,1]])
    expect(patchMembers).toHaveBeenCalledExactlyOnceWith(id,{
      base_revision:3,members:[{asset_id:'first',revision:2},{asset_id:'second',revision:7}],parameters:{gain:0,offset:null}
    })
  })

  it('does not write a partial member scope or replay the collection when a page ends early',async()=>{
    const {owner}=setup(useUpdateDatasetMembers)
    members.mockResolvedValueOnce({items:[{asset:{id:'first',revision:2}}],total:2,limit:1,offset:0})
      .mockResolvedValueOnce({items:[],total:2,limit:1,offset:1})
    await expect(owner.mutateAsync({workspaceId:'/a',datasetId:id,revision:3,changes:{parameters:{gain:0}}})).rejects.toThrow('Fixed member page ended')
    expect(members).toHaveBeenCalledTimes(2)
    expect(patchMembers).not.toHaveBeenCalled()
  })
})
