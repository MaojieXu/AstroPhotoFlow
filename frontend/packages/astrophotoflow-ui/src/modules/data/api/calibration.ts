import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import { checkImageCalibration, getDatasetCalibration, getImageCalibration, searchImageCalibration, updateImageCalibration, updateDatasetCalibrationMembers } from '../../../generated/api/sdk.gen'
import type { CalibrationCheckRequest, GetDatasetCalibrationData, SearchImageCalibrationData, UpdateImageCalibrationData, UpdateDatasetCalibrationMembersData } from '../../../generated/api/types.gen'

export function createCalibrationClient(fetchApi: FetchApi) {
  const options = { client: createPlatformClient({ fetchApi }), throwOnError: true } as const
  return {
    dataset: async (datasetId: string, versionId: string, query: GetDatasetCalibrationData['query'], signal?: AbortSignal) =>
      (await getDatasetCalibration<true>({ ...options, path: { dataset_id: datasetId, version_id: versionId }, query, signal })).data,
    image: async (assetId: string, versionId: string, signal?: AbortSignal) =>
      (await getImageCalibration<true>({ ...options, path: { asset_id: assetId, asset_version_id: versionId }, signal })).data,
    check: async (body: CalibrationCheckRequest) =>
      (await checkImageCalibration<true>({ ...options, body })).data,
    search: async (body: SearchImageCalibrationData['body'], signal?: AbortSignal) =>
      (await searchImageCalibration<true>({ ...options, body, signal })).data,
    updateImage: async (assetId: string, versionId: string, body: UpdateImageCalibrationData['body']) =>
      (await updateImageCalibration<true>({ ...options, path:{asset_id:assetId,asset_version_id:versionId}, body })).data,
    updateMembers: async (datasetId: string, body: UpdateDatasetCalibrationMembersData['body']) =>
      (await updateDatasetCalibrationMembers<true>({ ...options, path:{dataset_id:datasetId}, body })).data
  }
}

export const calibrationApi = createCalibrationClient((path, init) => fetch(path, init))
