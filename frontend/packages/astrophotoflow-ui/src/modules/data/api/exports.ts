import { createPlatformClient } from '../../../core/api/client'
import type { FetchApi } from '../../../core/api/client'
import {
  getDataApiV1DataNodesRunIdExecutionIdGet,
  submitApiV1ExportsPost,
  statusApiV1ExportsRequestIdGet,
  cancelApiV1ExportsRequestIdCancelPost,
  selectExportDestination
} from '../../../generated/api/sdk.gen'
import type {
  ExportRequest,
  ExportSelection
} from '../../../generated/api/types.gen'

export {
  zDataNodeResult as dataResultSchema,
  zExportReceipt as exportReceiptSchema,
  zExportRequest as exportRequestSchema
} from '../../../generated/api/zod.gen'
export type {
  DataNodeResult as DataResult,
  ExportReceipt,
  ExportRequest
} from '../../../generated/api/types.gen'

export function createDataExportClient(fetchApi: FetchApi) {
  const options = {
    client: createPlatformClient({ fetchApi }),
    throwOnError: true
  } as const
  return {
    result: async (run: string, execution: string, signal?:AbortSignal) =>
      (
        await getDataApiV1DataNodesRunIdExecutionIdGet<true>({
          ...options,
          path: { run_id: run, execution_id: execution },signal
        })
      ).data,
    submit: async (body: ExportRequest) =>
      (await submitApiV1ExportsPost<true>({ ...options, body })).data,
    status: async (id: string, signal?:AbortSignal) =>
      (
        await statusApiV1ExportsRequestIdGet<true>({
          ...options,
          path: { request_id: id },signal
        })
      ).data,
    cancel: async (id: string) =>
      (
        await cancelApiV1ExportsRequestIdCancelPost<true>({
          ...options,
          path: { request_id: id }
        })
      ).data,
    choose: async (body: ExportSelection, signal?:AbortSignal) =>
      (await selectExportDestination<true>({ ...options, body, signal })).data
  }
}
