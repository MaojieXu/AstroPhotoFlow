import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { checkedExportReceipt } from './receipt'
import type { ExportRequest } from '../api/exports'
import { exportQueryKey } from './queries'
import type { ExportClient } from './queries'

export function useSubmitResultExport() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: async ({
      client,
      body
    }: {
      workspaceId: string
      client: ExportClient
      body: ExportRequest
    }) => {
      const receipt = await client.submit(body)
      return checkedExportReceipt(receipt, body)
    },
    retry: false,
    onSuccess: (receipt, { workspaceId, body }) =>
      cache.setQueryData(exportQueryKey(workspaceId, body.request_id), receipt)
  })
}
export function useCancelResultExport() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: async ({
      client,
      body
    }: {
      workspaceId: string
      client: ExportClient
      body: ExportRequest
    }) => checkedExportReceipt(await client.cancel(body.request_id), body),
    retry: false,
    onSuccess: (receipt, { workspaceId, body }) =>
      cache.setQueryData(exportQueryKey(workspaceId, body.request_id), receipt)
  })
}
export function useChooseExportDestination() {
  return useMutation({
    mutationFn: ({
      client,
      body,
      signal
    }: {
      client: ExportClient
      body: Parameters<ExportClient['choose']>[0]
      signal: AbortSignal
    }) => client.choose(body, signal),
    retry: false
  })
}
