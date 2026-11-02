import { useMutation, useQueryClient } from '@tanstack/vue-query'
import type { WorkbenchClient } from '../client'
import type { ConfigSave } from '../contracts'
import { configurationKey } from './keys'

export function useSaveWorkbenchConfiguration() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({
      client,
      body
    }: {
      client: WorkbenchClient
      body: ConfigSave
    }) => client.saveConfiguration(body),
    retry: false,
    // A conflict/unknown save keeps the edit basis; only an explicit read adopts it.
    onSuccess: (data, { client }) =>
      cache.setQueryData(configurationKey(client), data)
  })
}
export function useSelectWorkbenchDirectory() {
  return useMutation({
    mutationFn: ({
      client,
      path,
      signal
    }: {
      client: WorkbenchClient
      path: string
      signal: AbortSignal
    }) => client.selectDirectory(path, signal),
    retry: false
  })
}
export function useRestartWorkbench() {
  return useMutation({
    mutationFn: ({
      client,
      operationId
    }: {
      client: WorkbenchClient
      operationId: string
    }) => client.restart(operationId),
    retry: false
  })
}
