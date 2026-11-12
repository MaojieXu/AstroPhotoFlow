import {
  addProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesPost,
  addProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesPost,
  removeProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesReferenceIdDelete,
  removeProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesReferenceIdDelete
} from '../../../generated/api/sdk.gen'
import type {
  AddProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesPostData,
  AddProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesPostData,
  RemoveProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesReferenceIdDeleteData,
  RemoveProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesReferenceIdDeleteData
} from '../../../generated/api/types.gen'
import {
  updateDatasetMemberParametersApiV1DatasetsDatasetIdMemberParametersPatch,
  removeLibraryEntriesApiV1LibraryItemsDelete
} from '../../../generated/api/sdk.gen'
import type {
  UpdateDatasetMemberParametersApiV1DatasetsDatasetIdMemberParametersPatchData,
  RemoveLibraryEntriesApiV1LibraryItemsDeleteData
} from '../../../generated/api/types.gen'
import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  createProjectApiV1ProjectsPost,
  patchProjectApiV1ProjectsProjectIdPatch,
  createEquipmentApiV1EquipmentPost,
  patchEquipmentApiV1EquipmentEquipmentIdPatch,
  createSetupApiV1EquipmentSetupsPost,
  patchSetupApiV1EquipmentSetupsSetupIdPatch,
  patchAssetApiV1LibraryAssetsAssetIdPatch,
  patchDatasetApiV1DatasetsDatasetIdPatch,
  archiveManagementEntriesApiV1SettingsTrashArchivePost
} from '../../../generated/api/sdk.gen'
import type {
  CreateProjectApiV1ProjectsPostData,
  PatchProjectApiV1ProjectsProjectIdPatchData,
  CreateEquipmentApiV1EquipmentPostData,
  PatchEquipmentApiV1EquipmentEquipmentIdPatchData,
  CreateSetupApiV1EquipmentSetupsPostData,
  PatchSetupApiV1EquipmentSetupsSetupIdPatchData,
  AssetPatch,
  DatasetPatch,
  ArchiveManagementEntriesApiV1SettingsTrashArchivePostData
} from '../../../generated/api/types.gen'
import { zAssetOut, zDatasetOut } from '../../../generated/api/zod.gen'

export function createMutationClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    addProjectAsset: async (
      projectId: string,
      body: AddProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesPostData['body']
    ) =>
      (
        await addProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesPost<true>(
          { ...options, path: { project_id: projectId }, body }
        )
      ).data,
    addProjectDataset: async (
      projectId: string,
      body: AddProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesPostData['body']
    ) =>
      (
        await addProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesPost<true>(
          { ...options, path: { project_id: projectId }, body }
        )
      ).data,
    removeProjectAsset: async (
      projectId: string,
      referenceId: string,
      body: RemoveProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesReferenceIdDeleteData['body']
    ) =>
      (
        await removeProjectAssetReferenceApiV1ProjectsProjectIdAssetReferencesReferenceIdDelete<true>(
          {
            ...options,
            path: { project_id: projectId, reference_id: referenceId },
            body
          }
        )
      ).data,
    removeProjectDataset: async (
      projectId: string,
      referenceId: string,
      body: RemoveProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesReferenceIdDeleteData['body']
    ) =>
      (
        await removeProjectDatasetReferenceApiV1ProjectsProjectIdDatasetReferencesReferenceIdDelete<true>(
          {
            ...options,
            path: { project_id: projectId, reference_id: referenceId },
            body
          }
        )
      ).data,
    patchMembers: async (
      id: string,
      body: UpdateDatasetMemberParametersApiV1DatasetsDatasetIdMemberParametersPatchData['body']
    ) =>
      (
        await updateDatasetMemberParametersApiV1DatasetsDatasetIdMemberParametersPatch<true>(
          { ...options, path: { dataset_id: id }, body }
        )
      ).data,
    removeLibrary: async (
      body: RemoveLibraryEntriesApiV1LibraryItemsDeleteData['body']
    ) =>
      (
        await removeLibraryEntriesApiV1LibraryItemsDelete<true>({
          ...options,
          body
        })
      ).data,
    createProject: async (body: CreateProjectApiV1ProjectsPostData['body']) =>
      (await createProjectApiV1ProjectsPost<true>({ ...options, body })).data,
    patchProject: async (
      id: string,
      body: PatchProjectApiV1ProjectsProjectIdPatchData['body']
    ) =>
      (
        await patchProjectApiV1ProjectsProjectIdPatch<true>({
          ...options,
          body,
          path: { project_id: id }
        })
      ).data,
    createEquipment: async (
      body: CreateEquipmentApiV1EquipmentPostData['body']
    ) =>
      (await createEquipmentApiV1EquipmentPost<true>({ ...options, body }))
        .data,
    patchEquipment: async (
      id: string,
      body: PatchEquipmentApiV1EquipmentEquipmentIdPatchData['body']
    ) =>
      (
        await patchEquipmentApiV1EquipmentEquipmentIdPatch<true>({
          ...options,
          body,
          path: { equipment_id: id }
        })
      ).data,
    createSetup: async (
      body: CreateSetupApiV1EquipmentSetupsPostData['body']
    ) =>
      (await createSetupApiV1EquipmentSetupsPost<true>({ ...options, body }))
        .data,
    patchSetup: async (
      id: string,
      body: PatchSetupApiV1EquipmentSetupsSetupIdPatchData['body']
    ) =>
      (
        await patchSetupApiV1EquipmentSetupsSetupIdPatch<true>({
          ...options,
          body,
          path: { setup_id: id }
        })
      ).data,
    patchAsset: async (
      id: string,
      body: AssetPatch
    ) =>
      zAssetOut.parse((
        await patchAssetApiV1LibraryAssetsAssetIdPatch<true>({
          ...options,
          body,
          path: { asset_id: id }
        })
      ).data),
    patchDataset: async (
      id: string,
      body: DatasetPatch
    ) =>
      zDatasetOut.parse((
        await patchDatasetApiV1DatasetsDatasetIdPatch<true>({
          ...options,
          body,
          path: { dataset_id: id }
        })
      ).data),
    archive: async (
      body: ArchiveManagementEntriesApiV1SettingsTrashArchivePostData['body']
    ) =>
      (
        await archiveManagementEntriesApiV1SettingsTrashArchivePost<true>({
          ...options,
          body
        })
      ).data
  }
}
