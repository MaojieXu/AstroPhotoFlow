import { expect,it,vi } from 'vitest'
import { createRunResultClient } from '@ui/modules/software/calls/client'

const identity={prompt_id:'00000000-0000-4000-8000-000000000001',call_id:'00000000-0000-4000-8000-000000000002'}
const result={...identity,log_url:"/checked/log",node_id:'12',workflow_id:null,calculation_signature:null,package_id:'siril',software_version:'1.4.4',bundle_version:null,bundle_commit:null,development_source:null,operation_id:'stats',definition_token:'fixed',state:'completed',ports:[],preview_error:null,observation:null,error:null}
it('reads the exact native prompt/call and validates the generated result',async()=>{
 const fetchApi=vi.fn().mockResolvedValue(Response.json(result))
 await expect(createRunResultClient(fetchApi).get(identity)).resolves.toMatchObject(result)
 expect(fetchApi.mock.calls[0][0]).toBe(`/astrophotoflow/api/v1/runs/${identity.prompt_id}/calls/${identity.call_id}`)
 expect(fetchApi.mock.calls[0][1]?.method).toBe('GET')
})
it('reads only the selected output member analysis and preserves zero/null',async()=>{
 const analysis={kind:'series',title:'Histogram',source:'histogram.csv',unit:null,columns:['x','y'],rows:[[1,0]],values:{minimum:0},text:null,sample:null,member_index:3}
 const fetchApi=vi.fn().mockResolvedValue(Response.json([analysis]))
 await expect(createRunResultClient(fetchApi).analysis(identity,2,3)).resolves.toEqual([analysis])
 expect(fetchApi.mock.calls[0][0]).toBe(`/astrophotoflow/api/v1/runs/${identity.prompt_id}/calls/${identity.call_id}/outputs/2/members/3/analysis`)
})
it('does not replace a malformed result with empty analysis or a completed state',async()=>{
 const fetchApi=vi.fn().mockResolvedValue(Response.json({state:'completed'}))
 await expect(createRunResultClient(fetchApi).get(identity)).rejects.toMatchObject({kind:'contract'})
})
