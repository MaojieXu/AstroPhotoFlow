import type { QueryClient } from '@tanstack/vue-query'
import { workspaceQueryKey } from '../../../core/query/keys'

/** Asset facts appear in summaries, fixed members and project references. */
export function invalidateLibraryData(cache: QueryClient, workspaceId: string) {
  return Promise.all(['library', 'datasets', 'library-selection', 'projects', 'trash'].map(resource =>
    cache.invalidateQueries({ queryKey: [...workspaceQueryKey(workspaceId), resource] })
  ))
}
