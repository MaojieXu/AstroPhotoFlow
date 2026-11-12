import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getAssetApiV1LibraryAssetsAssetIdGet,
  observeContentApiV1LibraryAssetsAssetIdContentObservationPost
} from '../../../generated/api/sdk.gen'

export function createAssetClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    get: async (id: string, signal?: AbortSignal) =>
      (
        await getAssetApiV1LibraryAssetsAssetIdGet<true>({
          ...options,
          path: { asset_id: id },
          signal
        })
      ).data,
    observe: async (id: string, signal?: AbortSignal) =>
      (
        await observeContentApiV1LibraryAssetsAssetIdContentObservationPost<true>(
          {
            ...options,
            path: { asset_id: id },
            signal
          }
        )
      ).data
  }
}
