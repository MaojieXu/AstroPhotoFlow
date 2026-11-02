import { useMutation, useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'
import { trashApi, mutationApi } from '../api'
import { invalidateLibraryData } from '../library/invalidation'

function invalidateTrashChanges(client: QueryClient, workspaceId: string) {
  return Promise.all(['trash', 'library', 'datasets', 'library-selection', 'projects'].map(resource =>
    client.invalidateQueries({ queryKey: [...workspaceQueryKey(workspaceId), resource] })
  ))
}

export function useRestoreTrash() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: { workspaceId: string; body: Parameters<typeof trashApi.restore>[0] }) => trashApi.restore(body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => invalidateTrashChanges(client, workspaceId)
  })
}

export function useDeleteTrash() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: { workspaceId: string; body: Parameters<typeof trashApi.remove>[0] }) => trashApi.remove(body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => invalidateTrashChanges(client, workspaceId)
  })
}

export function useRemoveLibraryEntries() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: { workspaceId: string; body: Parameters<typeof mutationApi.removeLibrary>[0] }) => mutationApi.removeLibrary(body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => invalidateLibraryData(cache, workspaceId)
  })
}

export function useArchiveManagement() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: { workspaceId: string; body: Parameters<typeof mutationApi.archive>[0] }) => mutationApi.archive(body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => Promise.all(['projects', 'equipment', 'trash'].map(resource =>
      cache.invalidateQueries({ queryKey: [...workspaceQueryKey(workspaceId), resource] })
    ))
  })
}

/** Confirmation scope is explicit; a preflight never retries itself. */
export function usePreviewTrash() {
  return useMutation({mutationFn: (body:Parameters<typeof trashApi.preview>[0])=>trashApi.preview(body),retry:false})
}
