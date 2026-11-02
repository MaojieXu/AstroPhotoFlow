import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useStableQueryInput } from '../../../core/query/viewInput'
import type { ListViewInput } from '../../../core/query/viewInput'
import { parseLibraryQuery } from './client'
import { useLibraryQuery } from './queries'
import type { LibraryPageRequest } from './queries'

export type LibraryFilters = Record<string, string[] | string>
export interface LibraryViewInput extends ListViewInput {
  category: 'all' | 'light' | 'calibration'
  filters: LibraryFilters
  sort: { by: string; order: 'asc' | 'desc' }
}
function filterParameters(filters: LibraryFilters) {
  const names: Record<string, string> = {
    frame_classes: 'frame_class',
    frame_types: 'frame_type',
    roles: 'role',
    exposure_seconds_min: 'exposure_min',
    exposure_seconds_max: 'exposure_max',
    integration_seconds_min: 'integration_min',
    integration_seconds_max: 'integration_max',
    sensor_temperature_c_min: 'temperature_min',
    sensor_temperature_c_max: 'temperature_max'
  }
  return Object.fromEntries(
    Object.entries(filters).map(([key, value]) => [names[key] ?? key, value])
  )
}
export function useLibraryView(
  input: MaybeRefOrGetter<LibraryViewInput>,
  paused: MaybeRefOrGetter<boolean>
) {
  const desired = computed<LibraryPageRequest | undefined>(() => {
    const state = toValue(input)
    if (!state.active || !state.workspaceId) return
    const filters = filterParameters(state.filters)
    const category: Record<string, string[]> =
      state.category === 'light'
        ? { frame_type: ['light'] }
        : state.category === 'calibration'
          ? { role: ['calibration'] }
          : {}
    const empty = Object.entries(category).some(
      ([key, values]) =>
        filters[key] !== undefined &&
        filters[key].length > 0 &&
        !filters[key].includes(values[0])
    )
    const limit = state.pageSize === 'all' ? 200 : state.pageSize,
      offset = state.pageSize === 'all' ? 0 : state.offset
    return {
      workspaceId: state.workspaceId,
      query: {
        ...parseLibraryQuery({
          ...filters,
          ...category,
          limit,
          offset,
          q: state.search || undefined,
          sort_by: state.sort.by,
          order: state.sort.order
        }),
        limit,
        offset
      },
      all: state.pageSize === 'all',
      empty
    }
  })
  const request = useStableQueryInput(
    desired,
    paused,
    (state) => state.workspaceId
  )
  return { request, query: useLibraryQuery(request, paused) }
}
