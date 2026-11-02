import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { createPlatformClient } from '../api/client'
import type { FetchApi } from '../api/client'
import { getServiceHealth } from '../../generated/api/sdk.gen'

/** A transport connection is verified once before its workspace-scoped queries. */
export function useWorkspaceIdentity(
  fetchApi: FetchApi,
  connectionId: MaybeRefOrGetter<string | undefined>
) {
  const client = createPlatformClient({ fetchApi })
  return useQuery({
    queryKey: computed(
      () => ['native-workspace', toValue(connectionId) ?? null] as const
    ),
    enabled: computed(() => Boolean(toValue(connectionId))),
    queryFn: async ({ signal }) =>
      (await getServiceHealth<true>({ client, signal, throwOnError: true }))
        .data,
    staleTime: Infinity,
    gcTime: 0,
    refetchOnMount: false,
    retry: false
  })
}
