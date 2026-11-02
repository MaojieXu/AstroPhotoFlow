import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  libraryTrashApiV1LibraryTrashGet,
  restoreLibraryTrashApiV1LibraryTrashRestorePost,
  libraryTrashDeletePreviewApiV1LibraryTrashDeletePreviewPost,
  libraryTrashDeleteApiV1LibraryTrashDeletePost,
  previewEquipmentDeleteApiV1EquipmentManagementDeletePreviewPost,
  deleteEquipmentEntriesApiV1EquipmentManagementDeletePost
} from '../../../generated/api/sdk.gen'
import type {
  LibraryTrashApiV1LibraryTrashGetData,
  RestoreLibraryTrashApiV1LibraryTrashRestorePostData,
  LibraryTrashDeletePreviewApiV1LibraryTrashDeletePreviewPostData,
  LibraryTrashDeleteApiV1LibraryTrashDeletePostData,
  PreviewEquipmentDeleteApiV1EquipmentManagementDeletePreviewPostData,
  DeleteEquipmentEntriesApiV1EquipmentManagementDeletePostData
} from '../../../generated/api/types.gen'

export function createTrashClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    list: async (
      query: NonNullable<LibraryTrashApiV1LibraryTrashGetData['query']>,
      signal?: AbortSignal
    ) =>
      (
        await libraryTrashApiV1LibraryTrashGet<true>({
          ...options,
          query,
          signal
        })
      ).data,
    restore: async (
      body: RestoreLibraryTrashApiV1LibraryTrashRestorePostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await restoreLibraryTrashApiV1LibraryTrashRestorePost<true>({
          ...options,
          body,
          signal
        })
      ).data,
    preview: async (
      body: LibraryTrashDeletePreviewApiV1LibraryTrashDeletePreviewPostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await libraryTrashDeletePreviewApiV1LibraryTrashDeletePreviewPost<true>(
          { ...options, body, signal }
        )
      ).data,
    remove: async (
      body: LibraryTrashDeleteApiV1LibraryTrashDeletePostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await libraryTrashDeleteApiV1LibraryTrashDeletePost<true>({
          ...options,
          body,
          signal
        })
      ).data,
    equipmentPreview: async (
      body: PreviewEquipmentDeleteApiV1EquipmentManagementDeletePreviewPostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await previewEquipmentDeleteApiV1EquipmentManagementDeletePreviewPost<true>(
          { ...options, body, signal }
        )
      ).data,
    equipmentRemove: async (
      body: DeleteEquipmentEntriesApiV1EquipmentManagementDeletePostData['body'],
      signal?: AbortSignal
    ) =>
      (
        await deleteEquipmentEntriesApiV1EquipmentManagementDeletePost<true>({
          ...options,
          body,
          signal
        })
      ).data
  }
}
