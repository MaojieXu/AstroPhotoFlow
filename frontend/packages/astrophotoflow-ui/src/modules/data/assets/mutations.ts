import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { mutationApi, assetDetailsApi } from '../api'
import { invalidateLibraryData } from '../library/invalidation'

export function useUpdateAsset() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ assetId, body }: { workspaceId: string; assetId: string; body: Parameters<typeof mutationApi.patchAsset>[1] }) => mutationApi.patchAsset(assetId, body),
    retry: false,
    onSettled: (_data, _error, { workspaceId, assetId }) => invalidateLibraryData(cache, workspaceId, {assetIds:[assetId]})
  })
}

export function useObserveAssetContent() {
  return useMutation({
    mutationFn: (assetId: string) => assetDetailsApi.observe(assetId),
    retry: false
  })
}
