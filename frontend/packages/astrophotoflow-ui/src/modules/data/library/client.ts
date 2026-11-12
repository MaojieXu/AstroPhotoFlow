import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getLibraryLocation,
  openLibraryDirectory,
  rebuildDatasetManifest,
  planLibraryOrganization,
  organizeLibrary,
  getLibraryOrganization,
  searchLibrary,
  getLibraryFilterOptions,
  getLibraryChangeState,
  listDatasetMembers,
  listDatasetMemberSummaries
} from '../../../generated/api/sdk.gen'
import type {
  LibraryLocationOut,
  LibraryOrganizeRequest,
  LibraryOrganizeExecute,
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
    location: async (entryType: LibraryLocationOut['entry_type'], entryId: string, signal?: AbortSignal) =>
      (await getLibraryLocation<true>({ ...options, path: { entry_type: entryType, entry_id: entryId }, signal })).data,
    openDirectory: async (entryType: LibraryLocationOut['entry_type'], entryId: string) =>
      (await openLibraryDirectory<true>({ ...options, path: { entry_type: entryType, entry_id: entryId } })).data,
    rebuildManifest: async (datasetId: string, baseRevision: number) =>
      (await rebuildDatasetManifest<true>({ ...options, path: { dataset_id: datasetId }, body: { base_revision: baseRevision } })).data,
    planOrganization: async (body: LibraryOrganizeRequest) =>
      (await planLibraryOrganization<true>({ ...options, body })).data,
    organize: async (body: LibraryOrganizeExecute) =>
      (await organizeLibrary<true>({ ...options, body })).data,
    organization: async (requestId: string) =>
      (await getLibraryOrganization<true>({ ...options, path: { request_id: requestId } })).data,
    changeState: async (signal?: AbortSignal) =>
      (await getLibraryChangeState<true>({ ...options, signal })).data,
    memberSummaries: async (datasetId: string, query: MemberQuery, signal?: AbortSignal) =>
      zDatasetMemberSummaryPage.parse((await listDatasetMemberSummaries<true>({
        ...options, path: { dataset_id: datasetId }, query, signal
      })).data),
    search: async (query: LibraryQuery, signal?: AbortSignal) =>
      (await searchLibrary<true>({ ...options, query, signal })).data,
    filters: async (signal?: AbortSignal) =>
      (await getLibraryFilterOptions<true>({ ...options, signal })).data,
    members: async (
      datasetId: string,
      query: NonNullable<ListDatasetMembersData['query']>,
      signal?: AbortSignal
    ) =>
      zDatasetMemberPage.parse((
        await listDatasetMembers<true>({
          ...options,
          path: { dataset_id: datasetId },
          query: { ...query, image_query: false },
          signal
        })
      ).data)
  }
}
