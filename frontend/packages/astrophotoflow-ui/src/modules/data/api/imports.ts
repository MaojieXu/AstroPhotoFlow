import { selectLocalImportApiV1ImportsSelectLocalPost } from '../../../generated/api/sdk.gen'
import type { SelectLocalImportApiV1ImportsSelectLocalPostData } from '../../../generated/api/types.gen'
import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  listAssetTasksApiV1AssetTasksGet,
  getAssetTaskApiV1AssetTasksTaskIdGet,
  resumeAssetTaskApiV1AssetTasksTaskIdResumePost,
  retryAssetTaskApiV1AssetTasksTaskIdRetryPost,
  createImportApiV1ImportsPost
} from '../../../generated/api/sdk.gen'
import type {
  ListAssetTasksApiV1AssetTasksGetData,
  GetAssetTaskApiV1AssetTasksTaskIdGetData,
  RetryAssetTaskApiV1AssetTasksTaskIdRetryPostData,
  ImportCreate
} from '../../../generated/api/types.gen'
import { zAssetTaskOut, zImportAccepted } from '../../../generated/api/zod.gen'

export function createImportClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    select: async (
      body: SelectLocalImportApiV1ImportsSelectLocalPostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await selectLocalImportApiV1ImportsSelectLocalPost<true>({
          ...options,
          body,
          signal
        })
      ).data,
    list: async (
      query: NonNullable<ListAssetTasksApiV1AssetTasksGetData['query']>,
      signal?: AbortSignal
    ) =>
      (
        await listAssetTasksApiV1AssetTasksGet<true>({
          ...options,
          query,
          signal
        })
      ).data,
    get: async (
      id: string,
      query: NonNullable<GetAssetTaskApiV1AssetTasksTaskIdGetData['query']>,
      signal?: AbortSignal
    ) =>
      zAssetTaskOut.parse((
        await getAssetTaskApiV1AssetTasksTaskIdGet<true>({
          ...options,
          path: { task_id: id },
          query: { ...query, image_query: false },
          signal
        })
      ).data),
    resume: async (id: string, signal?: AbortSignal) =>
      (
        await resumeAssetTaskApiV1AssetTasksTaskIdResumePost<true>({
          ...options,
          path: { task_id: id },
          signal
        })
      ).data,
    retry: async (
      id: string,
      body: RetryAssetTaskApiV1AssetTasksTaskIdRetryPostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await retryAssetTaskApiV1AssetTasksTaskIdRetryPost<true>({
          ...options,
          path: { task_id: id },
          body,
          signal
        })
      ).data,
    submit: async (
      body: ImportCreate,
      signal?: AbortSignal
    ) =>
      zImportAccepted.parse((await createImportApiV1ImportsPost<true>({ ...options, body, signal }))
        .data)
  }
}
