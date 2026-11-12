import { useQuery } from '@tanstack/vue-query'
import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { workspaceQueryKey } from '../../../core/query/keys'
import type { ScienceReference, createCanvasDataClient } from '../api/canvas'

export interface CanvasInspectionRequest {
  workspaceId: string
  reference: ScienceReference
  memberIndex: number
}
export function useCanvasInspection(
  request: MaybeRefOrGetter<CanvasInspectionRequest | undefined>,
  client: Pick<ReturnType<typeof createCanvasDataClient>, 'inspect'>
) {
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return current
        ? [
            ...workspaceQueryKey(current.workspaceId),
            'canvas-inspection',
            current.reference,
            current.memberIndex
          ]
        : ['canvas-inspection-idle']
    }),
    enabled: computed(() => Boolean(toValue(request)?.workspaceId)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      if (!current)
        throw new Error('Canvas inspection requires a material reference')
      const { reference, memberIndex } = current
      const result = await client.inspect(reference, memberIndex, signal)
      const matches = reference.kind === 'asset'
        ? result.asset_id === reference.asset_id
        : !reference.asset_ids || reference.asset_ids.includes(result.asset_id)
      if (result.member_index !== memberIndex || !matches)
        throw new ApiClientError(
          'Canvas metadata does not match its selected member',
          'contract'
        )
      return result
    },
    retry: false,
    refetchInterval: (query) =>
      !query.state.error && query.state.data?.preview_status === 'pending'
        ? 1500
        : false
  })
}
