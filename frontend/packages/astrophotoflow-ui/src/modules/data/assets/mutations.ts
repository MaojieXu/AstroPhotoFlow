import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { onScopeDispose, watch } from 'vue'
import { useQueryAvailability } from '../../../core/query/availability'
import { mutationApi, assetDetailsApi } from '../api'
import { invalidateLibraryData } from '../library/invalidation'
import { uiT } from '../../../core/i18n'

export function useUpdateAsset() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ assetId, body }: { workspaceId: string; assetId: string; body: Parameters<typeof mutationApi.patchAsset>[1] }) => mutationApi.patchAsset(assetId, body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => invalidateLibraryData(cache, workspaceId)
  })
}

export function useObserveAssetContent() {
  return useMutation({
    mutationFn: (assetId: string) => assetDetailsApi.observe(assetId),
    retry: false
  })
}

export function useAcceptAssetContent() {
  const cache = useQueryClient()
  const connectionReady = useQueryAvailability()
  let disposed = false
  let connectionGeneration = 0
  watch(connectionReady, available => { if (!available) connectionGeneration++ }, {flush:'sync'})
  onScopeDispose(() => { disposed = true })
  return useMutation({
    mutationFn: async ({ assetId, body }: {
      workspaceId: string; assetId: string; body: Parameters<typeof assetDetailsApi.accept>[1]
    }) => {
      const expectedGeneration = connectionGeneration
      try {
        return await assetDetailsApi.accept(assetId, body)
      } catch (cause) {
        if (disposed || !connectionReady.value || expectedGeneration !== connectionGeneration) throw cause
        // An uncertain POST is reconciled by the observed version/hash, never replayed.
        let latest: Awaited<ReturnType<typeof assetDetailsApi.get>>
        try {
          latest = await assetDetailsApi.get(assetId)
        } catch (readCause) {
          if (!(readCause instanceof Error)) throw cause
          const message = cause instanceof Error ? cause.message : uiT('apfUi.could_not_accept_the_new_asset_content')
          throw new Error(uiT('apfUi.value_could_not_verify_the_current_asset_value', {p0:message,p1:readCause.message}), {cause})
        }
        if (latest.id === assetId && latest.current_version_id !== body.base_version_id && latest.current_version?.content_hash === body.expected_observed_hash)
          return latest
        throw cause
      }
    },
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => invalidateLibraryData(cache, workspaceId)
  })
}
