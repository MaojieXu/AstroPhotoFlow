import { mount,flushPromises } from '@vue/test-utils'
import { defineComponent,ref } from 'vue'
import { afterEach,expect,it,vi } from 'vitest'
import { useSoftwareCall,useCallAnalysis } from '@ui/modules/software/calls/queries'
import type { CallRequest,AnalysisRequest } from '@ui/modules/software/calls/queries'
import type { SoftwareCallResult,AnalysisResult } from '@ui/generated/api/types.gen'
const id=(n:number)=>'00000000-0000-4000-8000-'+String(n).padStart(12,'0')
const result:SoftwareCallResult={prompt_id:id(1),call_id:id(2),log_url:"/checked/log",workflow_id:id(3),node_id:'7',calculation_signature:'fixed',state:'completed',ports:[],
  package_id:null,software_version:null,bundle_version:null,bundle_commit:null,development_source:null,operation_id:null,definition_token:null,preview_error:null,observation:null,error:null}
let wrapper:ReturnType<typeof mount>|undefined
afterEach(()=>{wrapper?.unmount();wrapper=undefined})

it('rejects a backend call that belongs to another workflow even when prompt and call IDs match',async()=>{
  const client={get:vi.fn().mockResolvedValue({...result,workflow_id:id(4)}),analysis:vi.fn()}
  const request=ref<CallRequest>({workspaceId:'/one',client,result})
  let query!:ReturnType<typeof useSoftwareCall>
  wrapper=mount(defineComponent({setup(){query=useSoftwareCall(request);return()=>null}}));await flushPromises()
  expect(query.data.value).toBeUndefined()
  expect(query.error.value?.message).toContain('does not match')
  expect(client.get).toHaveBeenCalledTimes(1)
})

it('cancels an obsolete analysis member and prevents its late data from replacing the current member',async()=>{
  const value=(member:number):AnalysisResult=>({kind:'text',title:'Member '+member,source:'synthetic',unit:null,columns:[],rows:[],values:{},text:'member '+member,sample:null,member_index:member})
  let finish!:(value:AnalysisResult[])=>void
  const client={get:vi.fn(),analysis:vi.fn().mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve})).mockResolvedValue([value(1)])}
  const request=ref<AnalysisRequest>({workspaceId:'/one',client,result,outputIndex:0,memberIndex:0})
  let query!:ReturnType<typeof useCallAnalysis>
  wrapper=mount(defineComponent({setup(){query=useCallAnalysis(request);return()=>null}}));await flushPromises()
  const signal=client.analysis.mock.calls[0][3] as AbortSignal
  request.value={...request.value,memberIndex:1};await flushPromises()
  expect(signal.aborted).toBe(true)
  expect(query.data.value?.[0].member_index).toBe(1)
  finish([value(0)]);await flushPromises()
  expect(query.data.value?.[0].member_index).toBe(1)
  expect(client.analysis).toHaveBeenCalledTimes(2)
})
