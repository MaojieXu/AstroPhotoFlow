import { ApiClientError } from '../../../core/api/errors'
import type { ExportReceipt, ExportRequest } from '../api/exports'

export function checkedExportReceipt(
  receipt: ExportReceipt,
  expected: ExportRequest
): ExportReceipt {
  if (
    receipt.request_id !== expected.request_id ||
    receipt.source.run_id !== expected.source.run_id ||
    receipt.source.execution_id !== expected.source.execution_id ||
    receipt.target !== expected.target ||
    JSON.stringify(receipt.member_indexes) !==
      JSON.stringify(expected.member_indexes)
  )
    throw new ApiClientError(
      'Export receipt does not match its frozen request',
      'contract'
    )
  return receipt
}
