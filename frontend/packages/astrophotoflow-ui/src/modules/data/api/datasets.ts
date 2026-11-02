import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getDatasetApiV1DatasetsDatasetIdGet,
  getDatasetVersionApiV1DatasetsDatasetIdVersionsVersionIdGet,
  listDatasetVersionsApiV1DatasetsDatasetIdVersionsGet,
  listCalibrationTargetsApiV1CalibrationTargetsGet,
  createDatasetApiV1DatasetsPost,
  createDatasetVersionApiV1DatasetsDatasetIdVersionsPost
} from '../../../generated/api/sdk.gen'
import type {
  ListDatasetVersionsApiV1DatasetsDatasetIdVersionsGetData,
  ListCalibrationTargetsApiV1CalibrationTargetsGetData,
  CreateDatasetApiV1DatasetsPostData,
  CreateDatasetVersionApiV1DatasetsDatasetIdVersionsPostData
} from '../../../generated/api/types.gen'

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
    version: async (id: string, versionId: string, signal?: AbortSignal) =>
      (
        await getDatasetVersionApiV1DatasetsDatasetIdVersionsVersionIdGet<true>(
          {
            ...options,
            path: { dataset_id: id, version_id: versionId },
            signal
          }
        )
      ).data,
    versions: async (
      id: string,
      query: NonNullable<
        ListDatasetVersionsApiV1DatasetsDatasetIdVersionsGetData['query']
      >,
      signal?: AbortSignal
    ) =>
      (
        await listDatasetVersionsApiV1DatasetsDatasetIdVersionsGet<true>({
          ...options,
          path: { dataset_id: id },
          query,
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
    create: async (body: CreateDatasetApiV1DatasetsPostData['body']) =>
      (await createDatasetApiV1DatasetsPost<true>({ ...options, body })).data,
    publish: async (
      id: string,
      body: CreateDatasetVersionApiV1DatasetsDatasetIdVersionsPostData['body']
    ) =>
      (
        await createDatasetVersionApiV1DatasetsDatasetIdVersionsPost<true>({
          ...options,
          path: { dataset_id: id },
          body
        })
      ).data
  }
}
