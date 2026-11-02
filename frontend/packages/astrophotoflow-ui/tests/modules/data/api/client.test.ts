import { describe,expect,it,vi } from 'vitest'
import { ApiClientError } from '@ui/core/api/errors'
import { createPlatformClient } from '@ui/core/api/client'
import { createPreviewImageClient } from '@ui/core/api/images'
import { createCatalogClient } from '@ui/modules/data/api/catalog'
import { createProjectApiV1ProjectsPost } from '@ui/generated/api/sdk.gen'

const project={id:'1f740b2c-75f3-4f76-8f85-f08ade40a33f',name:'M31',target_name:null,notes:null,status:'active',revision:1,created_at:'2026-10-22T20:00:00Z',updated_at:'2026-10-22T20:00:00Z'}
const response=(value:unknown,status=200)=>Response.json(value,{status})

describe('generated data transports',()=>{
 it('passes cancellation to the actual request without changing the sparse body',async()=>{
  const fetchApi=vi.fn().mockResolvedValue(response(project))
  const controller=new AbortController()
  await createProjectApiV1ProjectsPost<true>({client:createPlatformClient({fetchApi}),throwOnError:true,body:{name:'M31'},signal:controller.signal})
  expect(fetchApi.mock.calls[0][0]).toBe('/astrophotoflow/api/v1/projects')
  expect(fetchApi.mock.calls[0][1]).toMatchObject({method:'POST',body:JSON.stringify({name:'M31'})})
  controller.abort()
  expect(fetchApi.mock.calls[0][1].signal.aborted).toBe(true)
 })
 it('fetches updated preview bytes without cache and enforces JPEG',async()=>{
  const fetchApi=vi.fn().mockResolvedValue(new Response('pixels',{headers:{'Content-Type':'image/jpeg'}}))
  const client=createPreviewImageClient(fetchApi)
  await client.getBlob('/display')
  expect(fetchApi).toHaveBeenCalledWith('/display',expect.objectContaining({cache:'no-store'}))
  fetchApi.mockResolvedValue(new Response('pixels',{headers:{'Content-Type':'image/png'}}))
  await expect(client.getBlob('/display')).rejects.toMatchObject({kind:'contract'})
 })
 it('accepts a real empty page response',async()=>{
  const empty={items:[],total:0,limit:50,offset:0}
  await expect(createCatalogClient(vi.fn().mockResolvedValue(response(empty))).projects({})).resolves.toEqual(empty)
 })
 it('keeps revision conflicts distinct',async()=>{
  const fetchApi=vi.fn().mockResolvedValue(response({error:{code:'REVISION_CONFLICT',message:'changed',fields:[]},request_id:'ce88796a-b7bb-488d-9f15-645d04a87be5'},409))
  await expect(createCatalogClient(fetchApi).projects({})).rejects.toMatchObject({kind:'service',status:409,code:'REVISION_CONFLICT',requestId:'ce88796a-b7bb-488d-9f15-645d04a87be5'})
 })
 it('does not convert malformed responses to empty data',async()=>{
  await expect(createCatalogClient(vi.fn().mockResolvedValue(response({items:[],total:-1,limit:50,offset:0}))).projects({})).rejects.toBeInstanceOf(ApiClientError)
 })
 it('reports a network failure without fabricating a response',async()=>{
  await expect(createCatalogClient(vi.fn().mockRejectedValue(new TypeError('offline'))).projects({})).rejects.toMatchObject({kind:'network'})
 })
})

it('does not start a preview read whose signal is already aborted',async()=>{
 const fetchApi=vi.fn();const controller=new AbortController();controller.abort()
 await expect(createPreviewImageClient(fetchApi).getBlob('/thumbnail',controller.signal)).rejects.toMatchObject({name:'AbortError'})
 expect(fetchApi).not.toHaveBeenCalled()
})
it.each(['json','blob'] as const)('aborts the actual %s read without wrapping it as a service failure',async kind=>{
 let announceStarted:(()=>void)|undefined
 const started=new Promise<void>(resolve=>{announceStarted=resolve})
 const fetchApi=vi.fn((_path:string,init?:RequestInit)=>new Promise<Response>((_resolve,reject)=>{
  announceStarted?.();init?.signal?.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true})
 }))
 const controller=new AbortController()
 const pending=kind==='json'?createCatalogClient(fetchApi).projects({},controller.signal):createPreviewImageClient(fetchApi).getBlob('/thumbnail',controller.signal)
 const rejected=expect(pending).rejects.toMatchObject({name:'AbortError'})
 await started;controller.abort();await rejected
 expect(fetchApi.mock.calls[0][1]?.signal?.aborted).toBe(true)
})
