import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'
import type { SoftwareCallResult } from '../../../generated/api/types.gen'
import { createRunResultClient } from './client'
import { ApiClientError } from '../../../core/api/errors'

type Client = ReturnType<typeof createRunResultClient>
export interface CallRequest {
  workspaceId: string
  client: Client
  result: Pick<
    SoftwareCallResult,
    'prompt_id' | 'call_id' | 'workflow_id' | 'calculation_signature'
  >
}
export function useSoftwareCall(
  request: MaybeRefOrGetter<CallRequest | undefined>
) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return current
        ? [
            ...workspaceQueryKey(current.workspaceId),
            'software',
            'calls',
            current.result.prompt_id,
            current.result.call_id,
            current.result.workflow_id,
            current.result.calculation_signature ?? null
          ]
        : ['software-call-idle']
    }),
    enabled: computed(() => Boolean(toValue(request)?.workspaceId)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)!,
        expected = current.result
      const result = await current.client.get(expected, signal)
      if (
        result.prompt_id !== expected.prompt_id ||
        result.call_id !== expected.call_id ||
        result.workflow_id !== expected.workflow_id ||
        (expected.calculation_signature &&
          result.calculation_signature !== expected.calculation_signature)
      )
        throw new ApiClientError(
          'Software call does not match its native result reference',
          'contract'
        )
      return result
    }
  })
}
export interface AnalysisRequest {
  workspaceId: string
  client: Client
  result: Pick<SoftwareCallResult, 'prompt_id' | 'call_id' | 'workflow_id'>
  outputIndex: number
  memberIndex: number
}
export function useCallAnalysis(
  request: MaybeRefOrGetter<AnalysisRequest | undefined>
) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return current
        ? [
            ...workspaceQueryKey(current.workspaceId),
            'software',
            'calls',
            current.result.prompt_id,
            current.result.call_id,
            current.result.workflow_id,
            'analysis',
            current.outputIndex,
            current.memberIndex
          ]
        : ['call-analysis-idle']
    }),
    enabled: computed(() => Boolean(toValue(request)?.workspaceId)),
    queryFn: ({ signal }) => {
      const current = toValue(request)!
      return current.client.analysis(
        current.result,
        current.outputIndex,
        current.memberIndex,
        signal
      )
    }
  })
}
