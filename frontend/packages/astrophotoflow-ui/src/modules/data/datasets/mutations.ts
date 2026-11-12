import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { onScopeDispose, watch } from 'vue'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { datasetApi, mutationApi, libraryApi } from '../api'
import { invalidateLibraryData } from '../library/invalidation'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import { libraryQueryKey } from '../library/queries'

export function useCreateDataset() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: { workspaceId: string; body: Parameters<typeof datasetApi.create>[0] }) => datasetApi.create(body),
    // A failed response can still have an uncertain outcome. Re-read, never replay.
    onSettled: (_data, _error, { workspaceId }) => Promise.all([
      client.invalidateQueries({ queryKey: libraryQueryKey(workspaceId) }),
      client.invalidateQueries({ queryKey: [...workspaceQueryKey(workspaceId), 'datasets'] }),
      client.invalidateQueries({ queryKey: [...workspaceQueryKey(workspaceId), 'library-selection'] })
    ])
  })
}

export function useSaveDatasetDescription() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ datasetId, body }: { workspaceId: string; datasetId: string; body: Parameters<typeof mutationApi.patchDataset>[1] }) => mutationApi.patchDataset(datasetId, body),
    retry: false,
    onSettled: (_data, _error, { workspaceId, datasetId }) => invalidateLibraryData(cache, workspaceId, {datasetIds:[datasetId]})
  })
}

export function useUpdateDatasetMembers() {
  const cache = useQueryClient()
  const connectionReady = useQueryAvailability()
  let disposed = false
  let connectionGeneration = 0
  watch(connectionReady, available => { if (!available) connectionGeneration++ }, {flush:'sync'})
  onScopeDispose(() => { disposed = true })
  function requireCurrentConnection(expectedGeneration: number) {
    if (disposed || !connectionReady.value || expectedGeneration !== connectionGeneration)
      throw new ApiClientError(uiT('apfUi.workspace_identity_unverified'), 'service', 409, 'WORKSPACE_UNVERIFIED')
  }
  return useMutation({
    mutationFn: async (request: {
      workspaceId: string; datasetId: string; revision: number;
      changes: Pick<Parameters<typeof mutationApi.patchMembers>[1], 'parameters' | 'classification'>
    }) => {
      const expectedGeneration = connectionGeneration
      requireCurrentConnection(expectedGeneration)
      const revisions = new Map<string, number>()
      let offset = 0
      for (;;) {
        const page = await libraryApi.members(request.datasetId, {limit:200, offset, sort_by:'position', order:'asc'})
        requireCurrentConnection(expectedGeneration)
        for (const member of page.items) {
          const previous = revisions.get(member.asset.id)
          if (previous !== undefined && previous !== member.asset.revision)
            throw new Error(uiT('apfUi.another_window_modified_this_record_your_draft_is_retained_read_the_cu'))
          revisions.set(member.asset.id, member.asset.revision)
        }
        offset += page.items.length
        if (offset >= page.total) break
        if (!page.items.length) throw new ApiClientError('Fixed member page ended before its total', 'contract')
      }
      return mutationApi.patchMembers(request.datasetId, {
        base_revision:request.revision,
        members:[...revisions].map(([asset_id,revision])=>({asset_id,revision})), ...request.changes
      })
    },
    retry: false,
    onSettled: (data, _error, { workspaceId, datasetId }) => invalidateLibraryData(cache, workspaceId,
      {datasetIds:[datasetId],assetIds:data?.assets.map(asset=>asset.id)})
  })
}
