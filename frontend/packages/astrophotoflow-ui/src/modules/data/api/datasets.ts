import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getDatasetApiV1DatasetsDatasetIdGet,
  listCalibrationTargetsApiV1CalibrationTargetsGet,
  createDatasetApiV1DatasetsPost,
  editImageDatasetMembers,
  getCalibrationOperation,
  replaceDatasetMembers
} from '../../../generated/api/sdk.gen'
import type {
  ListCalibrationTargetsApiV1CalibrationTargetsGetData,
  DatasetCreate,
  ImageDatasetCreate,
  ImageDatasetEditMembers,
  ReplaceDatasetMembersData
} from '../../../generated/api/types.gen'
import { zDatasetOut, zImageOperationOut } from '../../../generated/api/zod.gen'

export function createDatasetClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    get: async (id: string, signal?: AbortSignal) =>
      (
        await getDatasetApiV1DatasetsDatasetIdGet<true>({
          ...options,
          path: { dataset_id: id },
          signal
        })
      ).data,
    calibrationTargets: async (
      query: NonNullable<
        ListCalibrationTargetsApiV1CalibrationTargetsGetData['query']
      >,
      signal?: AbortSignal
    ) =>
      (
        await listCalibrationTargetsApiV1CalibrationTargetsGet<true>({
          ...options,
          query,
          signal
        })
      ).data,
    createFromMembers: async (body: ImageDatasetCreate) =>
      zImageOperationOut.parse((await createDatasetApiV1DatasetsPost<true>({ ...options, body })).data),
    operation: async (id: string) =>
      (await getCalibrationOperation<true>({ ...options, path: { request_id: id } })).data,
    create: async (body: DatasetCreate) =>
      zDatasetOut.parse((await createDatasetApiV1DatasetsPost<true>({ ...options, body })).data),
    editMembers: async (id: string, body: ImageDatasetEditMembers) =>
      (await editImageDatasetMembers<true>({ ...options, path: { dataset_id: id }, body })).data,
    replaceMembers: async (
      id: string,
      body: ReplaceDatasetMembersData['body']
    ) =>
      (
        await replaceDatasetMembers<true>({
          ...options,
          path: { dataset_id: id },
          body
        })
      ).data
  }
}
