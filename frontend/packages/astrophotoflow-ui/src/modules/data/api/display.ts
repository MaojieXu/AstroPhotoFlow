import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import { readPreviewImage } from '../../../core/api/images'
import { zDisplayPreviewState } from '../../../generated/api/zod.gen'
import type { DisplayPreviewState } from '../../../generated/api/types.gen'

/** Preview bases may identify a fixed project reference or a library version. */
export function createDisplayPreviewClient(fetchApi: FetchApi) {
  const client = createPlatformClient({
    fetchApi,
    baseUrl: window.location.origin
  })
  const responseValidator = async (data: unknown) => {
    await zDisplayPreviewState.parseAsync(data)
  }
  return {
    prepare: async (base: string, signal?: AbortSignal) =>
      (
        await client.post<{ 200: DisplayPreviewState }, unknown, true>({
          url: base + '/display/auto-stretch',
          signal,
          throwOnError: true,
          responseValidator
        })
      ).data,
    status: async (base: string, signal?: AbortSignal) =>
      (
        await client.get<{ 200: DisplayPreviewState }, unknown, true>({
          url: base + '/display/status',
          signal,
          throwOnError: true,
          responseValidator
        })
      ).data,
    image: (base: string, signal?: AbortSignal) =>
      readPreviewImage(client, base + '/display', signal)
  }
}
