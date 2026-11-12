import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import { zCanvasInspectRequest } from '../../../generated/api/zod.gen'
import {
  canvasDataApiV1LibraryCanvasDataPost,
  inspectCanvasApiV1LibraryCanvasDataInspectPost
} from '../../../generated/api/sdk.gen'
import type {
  CanvasDataRequest,
  CanvasDataOut
} from '../../../generated/api/types.gen'

export {
  zCanvasDataRequest as canvasDataRequestSchema,
  zCanvasDataOut as canvasDataSchema,
  zCanvasInspectOut as canvasInspectSchema
} from '../../../generated/api/zod.gen'
export const scienceReferenceSchema = zCanvasInspectRequest.shape.reference
export type {
  CanvasDataRequest,
  CanvasDataOut as CanvasData,
  CanvasInspectOut as CanvasInspect
} from '../../../generated/api/types.gen'
export type ScienceReference = CanvasDataOut['reference']

export function createCanvasDataClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    inspect: async (
      reference: ScienceReference,
      memberIndex: number,
      signal?: AbortSignal
    ) =>
      (
        await inspectCanvasApiV1LibraryCanvasDataInspectPost<true>({
          ...options,
          body: { reference, member_index: memberIndex },
          signal
        })
      ).data,
    prepare: async (body: CanvasDataRequest, signal?: AbortSignal) =>
      (
        await canvasDataApiV1LibraryCanvasDataPost<true>({
          ...options,
          body,
          signal
        })
      ).data
  }
}
