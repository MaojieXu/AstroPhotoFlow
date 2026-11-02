import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import { zMediaSelection, zMediaState } from '../../../generated/api/zod.gen'
import type {
  MediaSelection,
  MediaState
} from '../../../generated/api/types.gen'

export {
  zMediaSelection as mediaSelectionSchema,
  zMediaState as mediaStateSchema
} from '../../../generated/api/zod.gen'
export type {
  MediaSelection,
  MediaState
} from '../../../generated/api/types.gen'

export type MediaMember = {
  title: string
  basePath: string
  selection?: Partial<MediaSelection>
}
export type MediaViewerRequest = {
  index: number
  total: number
  member: (index: number, signal: AbortSignal) => Promise<MediaMember>
}

export function createMediaClient(fetchApi: FetchApi) {
  // These addresses come from inspected members or checked result references.
  const client = createPlatformClient({
    fetchApi,
    baseUrl: window.location.origin
  })
  return {
    prepare: async (
      base: string,
      selection: Partial<MediaSelection>,
      signal?: AbortSignal
    ) => {
      const { data } = await client.post<{ 200: MediaState }, unknown, true>({
        url: base + '/viewer',
        body: selection,
        signal,
        throwOnError: true,
        requestValidator: async () => {
          await zMediaSelection.parseAsync(selection)
        },
        responseValidator: async (data) => {
          await zMediaState.parseAsync(data)
        }
      })
      return data
    },
    status: async (base: string, key: string, signal?: AbortSignal) => {
      const { data } = await client.get<{ 200: MediaState }, unknown, true>({
        url: base + '/viewer/' + encodeURIComponent(key) + '/status',
        signal,
        throwOnError: true,
        responseValidator: async (data) => {
          await zMediaState.parseAsync(data)
        }
      })
      return data
    },
    release: async (base: string, consumerId: string) => {
      await client.delete<{ 204: undefined }, unknown, true>({
        url: base + '/viewer/consumer/' + encodeURIComponent(consumerId),
        parseAs: 'text',
        keepalive: true,
        throwOnError: true
      })
    },
    image: async (url: string, signal: AbortSignal) => {
      const { data } = await client.get<{ 200: Blob }, unknown, true>({
        url,
        signal,
        parseAs: 'blob',
        throwOnError: true
      })
      return data
    }
  }
}
