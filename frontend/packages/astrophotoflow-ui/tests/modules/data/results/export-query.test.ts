import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '@ui/core/api/errors'
import { useResultExport } from '@ui/modules/data/results/useResultExport'
import type { ResultExportScope } from '@ui/modules/data/results/useResultExport'
import { exportRequestSchema } from '@ui/modules/data/api/exports'
import type { DataResult,ExportRequest,ExportReceipt } from '@ui/modules/data/api/exports'

const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const source:DataResult={output:{kind:'run_output',run_id:id(1),execution_id:id(2),output_index:0},run_id:id(1),execution_id:id(2),workflow_id:id(3),node_id:'7',state:'completed',error:null,reference:null,input_bindings:{},
  members:[0,1].map(index=>({name:'member-'+index+'.fits',view_base:'/view',selection:{hdu_index:0},format:'fits',metadata:{},byte_size:4096}))}
function receipt(body:ExportRequest,state:ExportReceipt['state']='completed'):ExportReceipt {
  return {request_id:body.request_id,state,source:body.source,target:body.target,member_indexes:body.member_indexes,destination:body.destination??null,settings:body.settings??{},results:[],error:null}
}
let wrapper:ReturnType<typeof mount>|undefined
beforeEach(()=>sessionStorage.clear())
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.useRealTimers();sessionStorage.clear()})
async function setup(){
  const client={result:vi.fn().mockResolvedValue(source),submit:vi.fn().mockImplementation(async(body:ExportRequest)=>receipt(body)),
    status:vi.fn(),cancel:vi.fn(),choose:vi.fn()}
  const scope=ref<ResultExportScope>({workspaceId:'/one',source,target:'library',client})
  let flow!:ReturnType<typeof useResultExport>
  wrapper=mount(defineComponent({setup(){flow=useResultExport(scope);return()=>null}}));await flushPromises()
  const build=vi.fn(async(request_id:string)=>exportRequestSchema.parse({request_id,source:{run_id:source.run_id,execution_id:source.execution_id},member_indexes:[0,1],target:'library',name:'fixed',settings:{format:'original'},selections:{}}))
  return {flow,client,scope,build}
}

it('queries an unknown acceptance before recovery and never posts again when its receipt already exists',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockRejectedValueOnce(new ApiClientError('Unknown acceptance','network'))
  client.status.mockRejectedValue(new ApiClientError('Still unavailable','service',503))
  await flow.submit(build);await flushPromises()
  expect(client.submit).toHaveBeenCalledTimes(1)
  const body=client.submit.mock.calls[0][0]
  client.status.mockResolvedValue(receipt(body))
  await flow.submit(build);await flushPromises()
  expect(client.status).toHaveBeenCalledWith(body.request_id,expect.any(AbortSignal))
  expect(client.submit).toHaveBeenCalledTimes(1)
  expect(flow.receipt.value?.state).toBe('completed')
  expect(build).toHaveBeenCalledTimes(1)
})

it('only an explicit recovery after 404 reuses exactly the frozen original ID and ordered members',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockRejectedValueOnce(new ApiClientError('Unknown acceptance','network'))
  client.status.mockRejectedValue(new ApiClientError('Not accepted','service',404,'RESOURCE_NOT_FOUND'))
  await flow.submit(build);await flushPromises()
  const frozen=structuredClone(client.submit.mock.calls[0][0])
  expect(client.submit).toHaveBeenCalledTimes(1)
  await flow.submit(build);await flushPromises()
  expect(client.submit).toHaveBeenCalledTimes(2)
  expect(client.submit.mock.calls[1][0]).toEqual(frozen)
  expect(frozen.member_indexes).toEqual([0,1])
  expect(build).toHaveBeenCalledTimes(1)
})

it('keeps an uncertain recovery read from automatically replaying the write',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockRejectedValueOnce(new ApiClientError('Unknown acceptance','network'))
  client.status.mockRejectedValue(new ApiClientError('Read unavailable','service',503))
  await flow.submit(build);await flushPromises();await flow.submit(build);await flushPromises()
  expect(client.submit).toHaveBeenCalledTimes(1)
  expect(flow.pendingBody.value).toBeDefined()
  expect(flow.receipt.value).toBeUndefined()
})

it('polls accepted work until a true terminal state and never repeats submission',async()=>{
  vi.useFakeTimers()
  const {flow,client,build}=await setup()
  client.submit.mockImplementationOnce(async(body:ExportRequest)=>receipt(body,'running'))
  client.status.mockImplementation(async(id:string)=>receipt(client.submit.mock.calls[0][0],id?'completed':'failed'))
  await flow.submit(build);await flushPromises()
  expect(flow.receipt.value?.state).toBe('running')
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(flow.receipt.value?.state).toBe('completed')
  const reads=client.status.mock.calls.length
  await vi.advanceTimersByTimeAsync(4000)
  expect(client.status).toHaveBeenCalledTimes(reads)
  expect(client.submit).toHaveBeenCalledTimes(1)
})

it('keeps frozen intentions and receipts isolated by workspace',async()=>{
  const {flow,client,scope,build}=await setup()
  await flow.submit(build);await flushPromises()
  const oldId=flow.requestId.value
  expect(oldId).toBeTruthy()
  scope.value={...scope.value,workspaceId:'/two'};await flushPromises()
  expect(flow.requestId.value).toBe('')
  expect(flow.receipt.value).toBeUndefined()
  expect(client.status).not.toHaveBeenCalled()
  expect(client.submit).toHaveBeenCalledTimes(1)
  scope.value={...scope.value,workspaceId:'/one'};await flushPromises()
  expect(flow.requestId.value).toBe(oldId)
})

it('cancels receipt reading on close without sending an export cancellation',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockRejectedValueOnce(new ApiClientError('Unknown acceptance','network'))
  client.status.mockImplementation(()=>new Promise(()=>{}))
  await flow.submit(build);await flushPromises()
  const signal=client.status.mock.calls[0][1] as AbortSignal
  wrapper!.unmount();wrapper=undefined
  expect(signal.aborted).toBe(true)
  expect(client.cancel).not.toHaveBeenCalled()
})

it('rejects receipts with another member scope instead of displaying them as this request',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockImplementationOnce(async(body:ExportRequest)=>({...receipt(body),member_indexes:[0]}))
  client.status.mockRejectedValue(new ApiClientError('Unavailable','service',503))
  await flow.submit(build);await flushPromises()
  expect(String(flow.error.value)).toContain('does not match')
  expect(flow.receipt.value).toBeUndefined()
  expect(client.submit).toHaveBeenCalledTimes(1)
})


it('queries an uncertain cancellation without claiming stopped until the receipt says cancelled',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockImplementationOnce(async(body:ExportRequest)=>receipt(body,'running'))
  await flow.submit(build);await flushPromises()
  const body=client.submit.mock.calls[0][0]
  client.cancel.mockRejectedValueOnce(new ApiClientError('Cancel response unknown','network'))
  client.status.mockResolvedValueOnce(receipt(body,'cancelling'))
  await flow.cancel();await flushPromises()
  expect(client.cancel).toHaveBeenCalledTimes(1)
  expect(flow.receipt.value?.state).toBe('cancelling')
  expect(flow.active.value).toBe(true)
  client.status.mockResolvedValue(receipt(body,'cancelled'))
  await flow.refresh();await flushPromises()
  expect(flow.receipt.value?.state).toBe('cancelled')
  expect(client.cancel).toHaveBeenCalledTimes(1)
})


it.each(['contract','service'] as const)('does not treat an unrecognized %s 404 as permission to replay acceptance',async(kind)=>{
  const {flow,client,build}=await setup()
  client.submit.mockRejectedValueOnce(new ApiClientError('Unknown acceptance','network'))
  client.status.mockRejectedValue(new ApiClientError('Ambiguous 404',kind,404,'HTTP_ERROR'))
  await flow.submit(build);await flushPromises();await flow.submit(build);await flushPromises()
  expect(client.submit).toHaveBeenCalledTimes(1)
  expect(flow.receipt.value).toBeUndefined()
})


it('continues observing the original active request through a temporary status failure',async()=>{
  vi.useFakeTimers()
  const {flow,client,build}=await setup()
  client.submit.mockImplementationOnce(async(body:ExportRequest)=>receipt(body,'running'))
  client.status.mockRejectedValueOnce(new ApiClientError('Temporarily offline','service',503))
    .mockImplementation(async()=>receipt(client.submit.mock.calls[0][0],'completed'))
  await flow.submit(build);await flushPromises()
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(flow.receipt.value?.state).toBe('running')
  await vi.advanceTimersByTimeAsync(2000);await flushPromises()
  expect(flow.receipt.value?.state).toBe('completed')
  expect(client.submit).toHaveBeenCalledTimes(1)
})

it('exposes a domain failure from a valid receipt instead of hiding its reason',async()=>{
  const {flow,client,build}=await setup()
  client.submit.mockImplementationOnce(async(body:ExportRequest)=>({...receipt(body,'failed'),error:'Synthetic output unavailable'}))
  await flow.submit(build);await flushPromises()
  expect(flow.receipt.value?.state).toBe('failed')
  expect(flow.error.value).toBe('Synthetic output unavailable')
})
