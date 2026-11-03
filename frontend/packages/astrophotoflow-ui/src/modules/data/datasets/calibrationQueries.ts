import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { datasetApi } from '../api'
import { readPages } from '../library/pagination'

export type CalibrationRead = { workspaceId: string; datasetId: string; versionId?: string }

export function useCalibrationData(
  request: MaybeRefOrGetter<CalibrationRead | undefined>,
  paused: MaybeRefOrGetter<boolean>
) {
  const cache = useQueryClient()
  const key = computed(() => {
    const current = toValue(request)
    return current
      ? [...workspaceQueryKey(current.workspaceId), 'datasets', current.datasetId, 'calibration-editor', current.versionId ?? 'current']
      : ['calibration-editor-idle']
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey: key,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      if (!current) throw new Error('Calibration editing requires a fixed dataset target')
      const [dataset, versions, targets] = await Promise.all([
        datasetApi.get(current.datasetId, signal),
        readPages(offset => datasetApi.versions(current.datasetId, { limit: 200, offset: offset ?? 0 }, signal), true, signal),
        readPages(offset => datasetApi.calibrationTargets({ limit: 200, offset: offset ?? 0 }, signal), true, signal)
      ])
      const versionId = current.versionId ?? dataset.current_version_id
      const version = versionId ? await datasetApi.version(current.datasetId, versionId, signal) : undefined
      signal.throwIfAborted()
      return { dataset, versions: versions.items, targets: targets.items, version }
    },
    staleTime: Infinity
  })
  watch(() => toValue(paused), value => {
    if (value) void cache.cancelQueries({ queryKey: key.value })
  }, { flush: 'sync' })
  return query
}
