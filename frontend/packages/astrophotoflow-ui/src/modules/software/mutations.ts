import { useMutation, useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import type { SoftwareClient } from './api/client'
import type { SoftwareConfirmationResult } from './api/contracts'
import { softwareQueryKey } from './queries'

type RequestContext = { workspaceId: string; packageId: string; client: SoftwareClient }
type SoftwareActionRequest = RequestContext & (
  | { kind: 'install'; body: Parameters<SoftwareClient['requestInstall']>[1] }
  | { kind: 'uninstall'; body: Parameters<SoftwareClient['requestUninstall']>[1] }
)

function invalidatePackage(cache: QueryClient, workspaceId: string, packageId: string) {
  const key = softwareQueryKey(workspaceId)
  return Promise.all([
    cache.invalidateQueries({ queryKey: [...key, 'catalog'] }),
    cache.invalidateQueries({ queryKey: [...key, 'details', packageId] })
  ])
}

export function useSoftwareActionRequest() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: (request: SoftwareActionRequest) => request.kind === 'install'
      ? request.client.requestInstall(request.packageId, request.body)
      : request.client.requestUninstall(request.packageId, request.body),
    retry: false,
    onSettled: (_data, _error, request) => invalidatePackage(cache, request.workspaceId, request.packageId)
  })
}

export function useSoftwareConfirmation() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: (request: { workspaceId: string; packageId: string; operationId: string; confirm: (id: string) => Promise<SoftwareConfirmationResult> }) => request.confirm(request.operationId),
    retry: false,
    onSettled: (_data, _error, request) => invalidatePackage(cache, request.workspaceId, request.packageId)
  })
}
