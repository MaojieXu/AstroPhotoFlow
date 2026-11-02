import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'
import { ApiClientError } from '../../../core/api/errors'
import { checkedExportReceipt } from './receipt'
import { createDataExportClient } from '../api/exports'
import type { DataResult, ExportRequest } from '../api/exports'

export type ExportClient = ReturnType<typeof createDataExportClient>
export interface ResultRequest {
  workspaceId: string
  client: ExportClient
  source: Pick<DataResult, 'run_id' | 'execution_id' | 'workflow_id'>
}
export const exportQueryKey = (workspaceId: string, id: string) =>
  [...workspaceQueryKey(workspaceId), 'exports', id] as const
export function useDataResult(
  request: MaybeRefOrGetter<ResultRequest | undefined>
) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return current
        ? [
            ...workspaceQueryKey(current.workspaceId),
            'data-results',
            current.source.run_id,
            current.source.execution_id,
            current.source.workflow_id
          ]
        : ['data-result-idle']
    }),
    enabled: computed(() => Boolean(toValue(request)?.workspaceId)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)!,
        expected = current.source
      const result = await current.client.result(
        expected.run_id,
        expected.execution_id,
        signal
      )
      if (
        result.run_id !== expected.run_id ||
        result.execution_id !== expected.execution_id ||
        result.workflow_id !== expected.workflow_id
      )
        throw new ApiClientError(
          'Data result does not match its native reference',
          'contract'
        )
      return result
    }
  })
}
export function useExportReceipt(
  request: MaybeRefOrGetter<
    | { workspaceId: string; client: ExportClient; body: ExportRequest }
    | undefined
  >
) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return current
        ? exportQueryKey(current.workspaceId, current.body.request_id)
        : ['export-receipt-idle']
    }),
    enabled: computed(() => Boolean(toValue(request)?.workspaceId)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)!,
        expected = current.body
      const receipt = await current.client.status(expected.request_id, signal)
      return checkedExportReceipt(receipt, expected)
    },
    staleTime: Infinity,
    refetchInterval:query=>{
      const data=query.state.data,error=query.state.error
      if(data&&!['queued','running','cancelling'].includes(data.state))return false
      if(error)return error instanceof ApiClientError&&(error.kind==='network'||(error.kind==='service'&&(error.status===503||error.code==='SERVICE_TIMEOUT')))?2000:false
      return data?2000:false
    }
  })
}
