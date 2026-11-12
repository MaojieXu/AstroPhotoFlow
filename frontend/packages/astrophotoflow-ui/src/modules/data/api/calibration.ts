import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import { checkImageCalibration, getDatasetCalibration, getImageCalibration, searchImageCalibration, updateImageCalibration, updateDatasetCalibration } from '../../../generated/api/sdk.gen'
import type { CalibrationCheckRequest, SearchImageCalibrationData, UpdateImageCalibrationData, UpdateDatasetCalibrationData } from '../../../generated/api/types.gen'

export function createCalibrationClient(fetchApi: FetchApi) {
  const options = { client: createPlatformClient({ fetchApi }), throwOnError: true } as const
  return {
    dataset: async (datasetId: string, signal?: AbortSignal) =>
      (await getDatasetCalibration<true>({ ...options, path: { dataset_id: datasetId }, signal })).data,
    image: async (assetId: string, signal?: AbortSignal) =>
      (await getImageCalibration<true>({ ...options, path: { asset_id: assetId }, signal })).data,
    check: async (body: CalibrationCheckRequest) =>
      (await checkImageCalibration<true>({ ...options, body })).data,
    search: async (body: SearchImageCalibrationData['body'], signal?: AbortSignal) =>
      (await searchImageCalibration<true>({ ...options, body, signal })).data,
    updateImage: async (assetId: string, body: UpdateImageCalibrationData['body']) =>
      (await updateImageCalibration<true>({ ...options, path:{asset_id:assetId}, body })).data,
    updateDataset: async (datasetId: string, body: UpdateDatasetCalibrationData['body']) =>
      (await updateDatasetCalibration<true>({ ...options, path:{dataset_id:datasetId}, body })).data
  }
}

export const calibrationApi = createCalibrationClient((path, init) => fetch(path, init))
