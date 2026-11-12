import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { createPlatformClient } from '../../core/api/client'
import type { FetchApi } from '../../core/api/client'
import { ApiClientError } from '../../core/api/errors'
import { workspaceQueryKey } from '../../core/query/keys'
import { getServiceHealth } from '../../generated/api/sdk.gen'
import type { SoftwarePackageDetails } from './api/contracts'
import type { SoftwareClient } from './api/client'

// The native software tab resolves the local service identity before using caches.
export function useSoftwareWorkspace(fetchApi: FetchApi, connectionEpoch: MaybeRefOrGetter<number>) {
  const client = createPlatformClient({ fetchApi })
  return useQuery({
    queryKey: computed(() => ['software-workspace', toValue(connectionEpoch)] as const),
    queryFn: async ({ signal }) => (await getServiceHealth<true>({ client, signal, throwOnError: true })).data,
    staleTime: 0,
    refetchOnMount: 'always'
  })
}

export function softwareQueryKey(workspaceId: string) {
  return [...workspaceQueryKey(workspaceId), 'software'] as const
}

type SoftwareScope = { workspaceId: string; client: SoftwareClient }
export type SoftwareDetailsRequest = SoftwareScope & { packageId: string; operationId?: string }

export function softwareDetailsKey(request: SoftwareDetailsRequest) {
  return [...softwareQueryKey(request.workspaceId), 'details', request.packageId, request.operationId ?? null] as const
}

export function useSoftwareCatalog(request: MaybeRefOrGetter<SoftwareScope>) {
  return useQuery({
    queryKey: computed(() => [...softwareQueryKey(toValue(request).workspaceId), 'catalog'] as const),
    enabled: computed(() => Boolean(toValue(request).workspaceId)),
    queryFn: ({ signal }) => toValue(request).client.listPackages(signal),
    refetchInterval: 10_000
  })
}

export function useSoftwareDetails(request: MaybeRefOrGetter<SoftwareDetailsRequest>, paused: MaybeRefOrGetter<boolean>) {
  const cache = useQueryClient()
  const queryKey = computed(() => softwareDetailsKey(toValue(request)))
  const query = useQuery({
    queryKey,
    enabled: computed(() => Boolean(toValue(request).workspaceId) && !toValue(paused)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      try {
        return await current.client.getPackage(current.packageId, current.operationId, signal)
      } catch (cause) {
        if (!(cause instanceof ApiClientError) || cause.code !== 'SOFTWARE_ACTION_EXPIRED') throw cause
        return current.client.getPackage(current.packageId, undefined, signal)
      }
    },
    refetchInterval: current => current.state.data?.current_action?.state === 'running' ? 1_000 : 10_000
  })
  watch(() => toValue(paused), value => {
    if (value) void cache.cancelQueries({ queryKey: queryKey.value })
  }, { flush: 'sync' })
  function adopt(current: SoftwareDetailsRequest, details: SoftwarePackageDetails) {
    cache.setQueryData(softwareDetailsKey(current), details)
  }
  return { ...query, adopt }
}

export function useSoftwareReleases(request: MaybeRefOrGetter<SoftwareScope & { packageId: string }>) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return [...softwareQueryKey(current.workspaceId), 'releases', current.packageId] as const
    }),
    enabled: computed(() => Boolean(toValue(request).workspaceId)),
    queryFn: ({ signal }) => {
      const current = toValue(request)
      return current.client.listReleases(current.packageId, signal)
    },
    // Checking official releases is deliberate, not a background network poll.
    staleTime: Infinity,
    refetchOnMount: 'always',
    refetchInterval: false
  })
}
