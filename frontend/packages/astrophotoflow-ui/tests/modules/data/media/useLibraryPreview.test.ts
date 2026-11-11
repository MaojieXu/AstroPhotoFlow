import { effectScope } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { afterEach,beforeEach,expect,it,vi } from 'vitest'
import { useLibraryPreview } from '@ui/modules/data/media/useLibraryPreview'
import { datasetMemberFixture } from '../../../fixtures/library-members'
import { libraryAsset,libraryDataset } from '../../../fixtures/library-summary'
import type { DatasetMemberPage } from '@ui/generated/api/types.gen'

const {members}=vi.hoisted(()=>({members:vi.fn()}))
vi.mock('@ui/modules/data/api',()=>({libraryApi:{members}}))
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const first=datasetMemberFixture({id:id(1),name:'First.fit'},id(3),0)
const second=datasetMemberFixture({id:id(4),name:'Second.fit'},id(3),1)
const group=libraryDataset({id:id(6),name:'Fixed group'},{members:[first,second]})
const page=(items:DatasetMemberPage['items'],total=items.length):DatasetMemberPage=>({items,total,limit:1,offset:0})
let scope=effectScope()
beforeEach(()=>{scope=effectScope();members.mockReset()})
afterEach(()=>scope.stop())

it('cancels a closed group read and rejects its late result',async()=>{
  let finish!: (value:DatasetMemberPage)=>void
  members.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
  const onError=vi.fn()
  const preview=scope.run(()=>useLibraryPreview({nativeViewer:()=>false,waitForEdits:async()=>true,onError}))!
  const opening=preview.open(group);await flushPromises()
  const signal=members.mock.calls[0][2] as AbortSignal
  preview.close();expect(signal.aborted).toBe(true)
  finish(page([first],2));await opening
  expect(preview.photo.value).toBeUndefined();expect(preview.media.value).toBeUndefined()
  expect(onError).not.toHaveBeenCalled()
})

it('keeps a newer photo after the older group response arrives',async()=>{
  let finish!: (value:DatasetMemberPage)=>void
  members.mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
  const preview=scope.run(()=>useLibraryPreview({nativeViewer:()=>false,waitForEdits:async()=>true,onError:vi.fn()}))!
  const opening=preview.open(group);await flushPromises()
  await preview.open(libraryAsset(second.asset))
  expect(preview.photo.value?.assetId).toBe(second.asset.id)
  finish(page([first],2));await opening
  expect(preview.photo.value?.assetId).toBe(second.asset.id)
  expect(preview.photo.value?.assetId).toBe(second.asset.id)
})

it('aborts lazy native member reads after their owning viewer closes',async()=>{
  let finish!: (value:DatasetMemberPage)=>void
  members.mockResolvedValueOnce(page([first],2)).mockImplementation(()=>new Promise(resolve=>{finish=resolve}))
  const preview=scope.run(()=>useLibraryPreview({nativeViewer:()=>true,waitForEdits:async()=>true,onError:vi.fn()}))!
  await preview.open(group)
  const view=preview.media.value!
  const reading=view.member(1,new AbortController().signal)
  const signal=members.mock.calls[1][2] as AbortSignal
  preview.close();expect(signal.aborted).toBe(true)
  finish(page([second],2))
  await expect(reading).rejects.toMatchObject({name:'AbortError'})
  await expect(view.member(0,new AbortController().signal)).rejects.toMatchObject({name:'AbortError'})
})

it('opens a image without requiring an existing thumbnail',async()=>{
  const preview=scope.run(()=>useLibraryPreview({nativeViewer:()=>true,waitForEdits:async()=>true,onError:vi.fn()}))!
  const withoutThumbnail={...second.asset}
  await preview.open(libraryAsset(withoutThumbnail))
  const viewer=preview.media.value!
  expect(viewer.total).toBe(1)
  const member=await viewer.member(0,new AbortController().signal)
  expect(member.basePath).toContain(`/assets/${second.asset.id}/previews`)
  expect(members).not.toHaveBeenCalled()
})


it('retains the existing preview while a new group resolves or fails',async()=>{
  let reject!: (reason:Error)=>void
  members.mockImplementation(()=>new Promise((_resolve, fail)=>{reject=fail}))
  const onError=vi.fn()
  const preview=scope.run(()=>useLibraryPreview({nativeViewer:()=>false,waitForEdits:async()=>true,onError}))!
  await preview.open(libraryAsset(second.asset))
  const old=preview.photo.value
  const opening=preview.open(group);await flushPromises()
  expect(preview.photo.value).toBe(old)
  reject(new Error('read failed'));await opening
  expect(preview.photo.value).toBe(old)
  expect(onError).toHaveBeenCalledOnce()
})
