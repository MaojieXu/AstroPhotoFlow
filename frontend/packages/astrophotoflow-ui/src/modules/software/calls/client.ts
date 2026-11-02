import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
 callResultApiV1RunsPromptIdCallsCallIdGet,
 outputAnalysisApiV1RunsPromptIdCallsCallIdOutputsOutputIndexMembersMemberIndexAnalysisGet
} from '../../../generated/api/sdk.gen'
import type { SoftwareCallResult } from '../../../generated/api/types.gen'
export { zAnalysisResult as analysisResultSchema, zSoftwareCallResult as softwareCallResultSchema } from '../../../generated/api/zod.gen'
export type { AnalysisResult, SoftwareCallResult } from '../../../generated/api/types.gen'

export function createRunResultClient(fetchApi:FetchApi){
 const options={client:createPlatformClient({fetchApi}),throwOnError:true} as const
 return {
  get:async(result:Pick<SoftwareCallResult,'prompt_id'|'call_id'>,signal?:AbortSignal)=>(await callResultApiV1RunsPromptIdCallsCallIdGet<true>({...options,path:{prompt_id:result.prompt_id,call_id:result.call_id},signal})).data,
  analysis:async(result:Pick<SoftwareCallResult,'prompt_id'|'call_id'>,outputIndex:number,memberIndex:number,signal?:AbortSignal)=>(await outputAnalysisApiV1RunsPromptIdCallsCallIdOutputsOutputIndexMembersMemberIndexAnalysisGet<true>({...options,path:{prompt_id:result.prompt_id,call_id:result.call_id,output_index:outputIndex,member_index:memberIndex},signal})).data
 }
}
