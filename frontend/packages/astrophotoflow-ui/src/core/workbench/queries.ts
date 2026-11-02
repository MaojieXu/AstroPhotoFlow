import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { ApiClientError } from '../client'
import type { WorkbenchClient } from '../client'
import { configurationKey, workbenchKey } from './keys'

export function useWorkbenchConfiguration(
  client: MaybeRefOrGetter<WorkbenchClient>
) {
  return useQuery({
    queryKey: computed(() => configurationKey(toValue(client))),
    queryFn: ({ signal }) => toValue(client).getConfiguration(signal),
    staleTime: 0,
    refetchOnMount: 'always',
    gcTime: 0
  })
}
export interface RestartObservation {
  client: WorkbenchClient
  operationId: string
  deadline: number
}
export class RestartObservationExpired extends Error {}
export function transientRestartError(cause: unknown) {
  return (
    cause instanceof ApiClientError &&
    (cause.kind === 'network' ||
      cause.status === 503 ||
      cause.code === 'SERVICE_TIMEOUT')
  )
}
export function useRestartObservation(
  target: MaybeRefOrGetter<RestartObservation | undefined>
) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(target)
      return current
        ? [...workbenchKey(current.client), 'restart', current.operationId]
        : ['workbench-restart-idle']
    }),
    enabled: computed(() => Boolean(toValue(target))),
    queryFn: async ({ signal }) => {
      const current = toValue(target)
      if (!current)
        throw new Error(
          'Restart observation requires its original operation identity'
        )
      const remaining = current.deadline - Date.now()
      if (remaining <= 0) throw new RestartObservationExpired()
      try {
        const result = await current.client.restartResult(
          current.operationId,
          AbortSignal.any([signal, AbortSignal.timeout(remaining)])
        )
        if (result && result.operation_id !== current.operationId)
          throw new ApiClientError(
            'Restart result does not match the requested operation',
            'contract'
          )
        return result
      } catch (cause) {
        if (Date.now() >= current.deadline)
          throw new RestartObservationExpired()
        throw cause
      }
    },
    retry: false,
    staleTime: 0,
    gcTime: 0,
    refetchInterval: (query) =>
      query.state.error instanceof RestartObservationExpired ||
      (query.state.data && query.state.data.state !== 'in_progress')
        ? false
        : 1000
  })
}
