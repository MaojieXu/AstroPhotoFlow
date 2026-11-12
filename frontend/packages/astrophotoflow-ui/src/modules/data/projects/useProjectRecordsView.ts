import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useStableQueryInput } from '../../../core/query/viewInput'
import type { ListViewInput } from '../../../core/query/viewInput'
import {
  zListProjectsApiV1ProjectsGetQuery,
  zListProjectAssetsApiV1ProjectsProjectIdAssetsGetQuery,
  zListProjectDatasetsApiV1ProjectsProjectIdDatasetsGetQuery
} from '../../../generated/api/zod.gen'
import { nonEmptyQuery } from '../api/catalog'
import { useProjectRecordsQuery } from './queries'
import type { ProjectRecordsRequest } from './queries'

export interface ProjectRecordsViewInput extends ListViewInput {
  kind: 'projects' | 'assets' | 'datasets'
  projectId: string | null
  status: 'active' | 'archived' | 'all'
  targetName: string
  role: string
  frameType: string
  masters?: boolean
}
export function useProjectRecordsView(
  input: MaybeRefOrGetter<ProjectRecordsViewInput>,
  paused: MaybeRefOrGetter<boolean>
) {
  const desired = computed<ProjectRecordsRequest | undefined>(() => {
    const state = toValue(input)
    if (!state.active || !state.workspaceId) return
    const common = {
      limit: state.pageSize === 'all' ? 200 : state.pageSize,
      offset: state.pageSize === 'all' ? 0 : state.offset,
      q: state.search || undefined
    }
    const base = {
      workspaceId: state.workspaceId,
      all: state.pageSize === 'all'
    }
    if (state.kind === 'projects')
      return {
        ...base,
        kind: 'projects',
        query: zListProjectsApiV1ProjectsGetQuery.parse(
          nonEmptyQuery({
            ...common,
            status: state.status,
            target_name: state.targetName
          })
        )
      }
    if (!state.projectId) return
    return state.kind === 'assets'
      ? {
          ...base,
          kind: 'assets',
          projectId: state.projectId,
          query: zListProjectAssetsApiV1ProjectsProjectIdAssetsGetQuery.parse(
            nonEmptyQuery({
              ...common,
              role: state.role,
              frame_type: state.frameType,
              frame_class: state.masters ? "masterframe" : undefined
            })
          )
        }
      : {
          ...base,
          kind: 'datasets',
          projectId: state.projectId,
          query:
            zListProjectDatasetsApiV1ProjectsProjectIdDatasetsGetQuery.parse(
              common
            )
        }
  })
  const request = useStableQueryInput(desired, paused, (state) =>
    JSON.stringify([
      state.workspaceId,
      state.kind,
      state.kind === 'projects' ? null : state.projectId,
      state.kind === 'assets' ? state.query.frame_class : null
    ])
  )
  return { request, query: useProjectRecordsQuery(request, paused) }
}
