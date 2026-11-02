import {
  pendingSoftwareActionSchema,
  type SoftwareConfirmationResult
} from '@astrophotoflow/ui'

import { api } from '@/scripts/api'

export async function confirmSoftware(operationId: string): Promise<SoftwareConfirmationResult> {
  const response = await api.sendNativePage('confirm_software', { operation_id: operationId })
  if (!response.ok) {
    return { ok: false, code: 'NATIVE_BRIDGE_UNAVAILABLE', message: null }
  }
  if (response.reply.error) {
    return {
      ok: false,
      code: response.reply.error.code,
      message: response.reply.error.message
    }
  }
  const pending = pendingSoftwareActionSchema.safeParse(response.reply.result)
  if (!pending.success) {
    return { ok: false, code: 'INVALID_RESPONSE', message: null }
  }
  return { ok: true, pending: pending.data }
}
