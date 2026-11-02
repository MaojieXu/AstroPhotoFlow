import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  searchLibrary,
  getLibraryFilterOptions,
  listDatasetMembers
} from '../../../generated/api/sdk.gen'
import type {
  SearchLibraryData,
  ListDatasetMembersData
} from '../../../generated/api/types.gen'
import { zSearchLibraryQuery } from '../../../generated/api/zod.gen'

export type LibraryQuery = NonNullable<SearchLibraryData['query']>
export type MemberQuery = NonNullable<ListDatasetMembersData['query']>

/** Convert the filter form's range strings; the generated schema owns API keys and types. */
export function parseLibraryQuery(
  values: Record<string, unknown>
): LibraryQuery {
  return zSearchLibraryQuery.parse(
    Object.fromEntries(
      Object.entries(values)
        .filter(([, value]) => value !== '' && value !== undefined)
        .map(([key, value]) => [
          key,
          typeof value === 'string' && /_(min|max)$/.test(key)
            ? Number(value)
            : value
        ])
    )
  )
}

export function createLibraryClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    search: async (query: LibraryQuery, signal?: AbortSignal) =>
      (await searchLibrary<true>({ ...options, query, signal })).data,
    filters: async (signal?: AbortSignal) =>
      (await getLibraryFilterOptions<true>({ ...options, signal })).data,
    members: async (
      datasetId: string,
      versionId: string,
      query: MemberQuery,
      signal?: AbortSignal
    ) =>
      (
        await listDatasetMembers<true>({
          ...options,
          path: { dataset_id: datasetId, version_id: versionId },
          query,
          signal
        })
      ).data
  }
}
