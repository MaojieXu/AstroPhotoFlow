import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'
import { mutationApi, trashApi } from '../api'

function invalidateEquipment(
  cache: ReturnType<typeof useQueryClient>,
  workspaceId: string
) {
  return Promise.all(
    ['equipment', 'trash'].map((resource) =>
      cache.invalidateQueries({
        queryKey: [...workspaceQueryKey(workspaceId), resource]
      })
    )
  )
}

export function useUpdateEquipment() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({
      equipmentId,
      body
    }: {
      workspaceId: string
      equipmentId: string
      body: Parameters<typeof mutationApi.patchEquipment>[1]
    }) => mutationApi.patchEquipment(equipmentId, body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) =>
      invalidateEquipment(cache, workspaceId)
  })
}

export function useCreateEquipment() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({
      body
    }: {
      workspaceId: string
      body: Parameters<typeof mutationApi.createEquipment>[0]
    }) => mutationApi.createEquipment(body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) =>
      invalidateEquipment(cache, workspaceId)
  })
}

type SetupWrite = { workspaceId: string } & (
  | { action: 'create'; body: Parameters<typeof mutationApi.createSetup>[0] }
  | {
      action: 'update'
      setupId: string
      body: Parameters<typeof mutationApi.patchSetup>[1]
    }
)

export function useSaveSetup() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: (request: SetupWrite) =>
      request.action === 'create'
        ? mutationApi.createSetup(request.body)
        : mutationApi.patchSetup(request.setupId, request.body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) =>
      invalidateEquipment(cache, workspaceId)
  })
}

type PresetWrite = { workspaceId: string } & (
  | {
      action: 'create'
      setupId: string
      body: Parameters<typeof mutationApi.createPreset>[1]
    }
  | {
      action: 'update'
      presetId: string
      body: Parameters<typeof mutationApi.patchPreset>[1]
    }
)

export function useSavePreset() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: (request: PresetWrite) =>
      request.action === 'create'
        ? mutationApi.createPreset(request.setupId, request.body)
        : mutationApi.patchPreset(request.presetId, request.body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) =>
      invalidateEquipment(cache, workspaceId)
  })
}

/** A finite confirmation preview is an explicit operation, never a polled list. */
export function useEquipmentDeletePreview() {
  return useMutation({
    mutationFn: (body: Parameters<typeof trashApi.equipmentPreview>[0]) => trashApi.equipmentPreview(body),
    retry: false
  })
}

export function useDeleteEquipmentEntries() {
  const cache = useQueryClient()
  return useMutation({
    mutationFn: ({ body }: { workspaceId: string; body: Parameters<typeof trashApi.equipmentRemove>[0] }) => trashApi.equipmentRemove(body),
    retry: false,
    onSettled: (_data, _error, { workspaceId }) => invalidateEquipment(cache, workspaceId)
  })
}
