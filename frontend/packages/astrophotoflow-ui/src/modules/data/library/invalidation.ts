import type { QueryClient } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'

/** Asset facts appear in summaries, fixed members and project references. */
export function invalidateLibraryData(cache: QueryClient, workspaceId: string,
  target?: { assetIds?: readonly string[]; datasetIds?: readonly string[] }) {
  if (target) {
    const assets = new Set(target.assetIds), datasets = new Set(target.datasetIds)
    function references(value: unknown): boolean {
      if (typeof value !== 'object' || value === null) return false
      if ('id' in value && typeof value.id === 'string' && (assets.has(value.id) || datasets.has(value.id))) return true
      if ('asset_id' in value && typeof value.asset_id === 'string' && assets.has(value.asset_id)) return true
      if ('dataset_id' in value && typeof value.dataset_id === 'string' && datasets.has(value.dataset_id)) return true
      if ('asset' in value && references(value.asset)) return true
      if ('dataset' in value && references(value.dataset)) return true
      if ('page' in value && references(value.page)) return true
      return 'items' in value && Array.isArray(value.items) && value.items.some(references)
    }
    const scoped = cache.getQueryCache().findAll({ queryKey: workspaceQueryKey(workspaceId) })
    for (const query of scoped) {
      if (query.queryKey[2] === 'datasets' && typeof query.queryKey[3] === 'string' && references(query.state.data)) datasets.add(query.queryKey[3])
    }
    return cache.invalidateQueries({ predicate: query =>
      query.queryKey[0] === 'workspace' && query.queryKey[1] === workspaceId && (
        ['library', 'library-selection'].includes(String(query.queryKey[2])) ||
        query.queryKey[2] === 'datasets' && datasets.has(String(query.queryKey[3])) || references(query.state.data)
      ) })
  }
  return Promise.all(['library', 'datasets', 'library-selection', 'projects', 'trash'].map(resource =>
    cache.invalidateQueries({ queryKey: [...workspaceQueryKey(workspaceId), resource] })
  ))
}
