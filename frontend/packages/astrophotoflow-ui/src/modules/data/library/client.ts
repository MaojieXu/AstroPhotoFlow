import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  searchLibrary,
  getLibraryFilterOptions,
  getLibraryChangeState,
  listDatasetMembers,
  listDatasetMemberSummaries
} from '../../../generated/api/sdk.gen'
import type {
  SearchLibraryData,
  ListDatasetMembersData,
  ListDatasetMemberSummariesData
} from '../../../generated/api/types.gen'
import { zDatasetMemberPage, zDatasetMemberSummaryPage, zSearchLibraryQuery } from '../../../generated/api/zod.gen'

export type LibraryQuery = NonNullable<SearchLibraryData['query']>
export type MemberQuery = NonNullable<ListDatasetMemberSummariesData['query']>

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
    changeState: async (signal?: AbortSignal) =>
      (await getLibraryChangeState<true>({ ...options, signal })).data,
    memberSummaries: async (datasetId: string, versionId: string, query: MemberQuery, signal?: AbortSignal) =>
      zDatasetMemberSummaryPage.parse((await listDatasetMemberSummaries<true>({
        ...options, path: { dataset_id: datasetId, version_id: versionId }, query, signal
      })).data),
    search: async (query: LibraryQuery, signal?: AbortSignal) =>
      (await searchLibrary<true>({ ...options, query, signal })).data,
    filters: async (signal?: AbortSignal) =>
      (await getLibraryFilterOptions<true>({ ...options, signal })).data,
    members: async (
      datasetId: string,
      versionId: string,
      query: NonNullable<ListDatasetMembersData['query']>,
      signal?: AbortSignal
    ) =>
      zDatasetMemberPage.parse((
        await listDatasetMembers<true>({
          ...options,
          path: { dataset_id: datasetId, version_id: versionId },
          query: { ...query, image_query: false },
          signal
        })
      ).data)
  }
}
