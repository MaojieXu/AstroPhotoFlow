export { zBundlePreviewRequest as bundlePreviewRequestSchema } from '../../../generated/api/zod.gen'
import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import {
  previewApiV1SoftwarePreviewPost,
  releaseApiV1SoftwarePreviewConsumerIdDelete
} from '../../../generated/api/sdk.gen'
import type { BundlePreviewRequest } from '../../../generated/api/types.gen'

export type { BundlePreviewRequest } from '../../../generated/api/types.gen'

export function createBundlePreviewClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    async render(
      body: BundlePreviewRequest,
      signal: AbortSignal
    ): Promise<Blob> {
      const { data, response } = await previewApiV1SoftwarePreviewPost<true>({
        ...options,
        body,
        signal,
        parseAs: 'blob'
      })
      if (
        !response.headers
          .get('Content-Type')
          ?.toLowerCase()
          .startsWith('image/png')
      )
        throw new ApiClientError(
          uiT(
            'apfUi.the_preview_response_type_does_not_match_the_api_contract'
          ),
          'contract',
          response.status
        )
      return data
    },
    async release(consumerId: string): Promise<void> {
      await releaseApiV1SoftwarePreviewConsumerIdDelete<true>({
        ...options,
        path: { consumer_id: consumerId },
        keepalive: true
      })
    }
  }
}
