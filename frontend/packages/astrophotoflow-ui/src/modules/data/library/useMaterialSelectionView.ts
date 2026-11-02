import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useStableQueryInput } from '../../../core/query/viewInput'
import type { ListViewInput } from '../../../core/query/viewInput'
import {
  zListDatasetsApiV1DatasetsGetQuery,
  zListLibraryAssetsQuery
} from '../../../generated/api/zod.gen'
import { useLibrarySelectionQuery } from './selectionQueries'
import type { LibrarySelectionRequest } from './selectionQueries'

export interface MaterialSelectionViewInput extends ListViewInput {
  kind: 'assets' | 'datasets'
  status: 'active' | 'archived' | 'all'
  role: string
  frameType: string
}
export function useMaterialSelectionView(
  input: MaybeRefOrGetter<MaterialSelectionViewInput>,
  paused: MaybeRefOrGetter<boolean>
) {
  const desired = computed<LibrarySelectionRequest | undefined>(() => {
    const state = toValue(input)
    if (!state.active || !state.workspaceId) return
    const common = {
      limit: state.pageSize === 'all' ? 200 : state.pageSize,
      offset: state.pageSize === 'all' ? 0 : state.offset,
      q: state.search || undefined
    }
    return state.kind === 'datasets'
      ? {
          workspaceId: state.workspaceId,
          kind: 'datasets',
          all: state.pageSize === 'all',
          query: zListDatasetsApiV1DatasetsGetQuery.parse({
            ...common,
            status: state.status
          })
        }
      : {
          workspaceId: state.workspaceId,
          kind: 'assets',
          all: state.pageSize === 'all',
          query: zListLibraryAssetsQuery.parse({
            ...common,
            ...(state.role ? { role: state.role } : {}),
            ...(state.frameType ? { frame_type: state.frameType } : {})
          })
        }
  })
  const request = useStableQueryInput(desired, paused, (state) =>
    JSON.stringify([state.workspaceId, state.kind])
  )
  return { request, query: useLibrarySelectionQuery(request, paused) }
}
