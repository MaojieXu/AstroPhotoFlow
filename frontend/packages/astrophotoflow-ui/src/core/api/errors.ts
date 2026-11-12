import { zErrorEnvelope } from '../../generated/api/zod.gen'
import { uiT } from '../i18n'
import type { ErrorEnvelope } from '../../generated/api/types.gen'

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly kind: 'network' | 'service' | 'contract',
    readonly status?: number,
    readonly code?: string,
    readonly requestId?: string,
    readonly fields?: ErrorEnvelope['error']['fields']
  ) {
    super(message)
    this.name = 'ApiClientError'
  }
}

export function classifyPlatformError(
  error: unknown,
  response?: Response
): unknown {
  if (
    error instanceof ApiClientError ||
    (typeof error === 'object' &&
      error !== null &&
      'name' in error &&
      error.name === 'AbortError')
  )
    return error
  if (response && !response.ok) {
    const parsed = zErrorEnvelope.safeParse(error)
    if (parsed.success) {
      return new ApiClientError(
        parsed.data.error.message,
        'service',
        response.status,
        parsed.data.error.code,
        parsed.data.request_id,
        parsed.data.error.fields
      )
    }
    return new ApiClientError(
      uiT('apfUi.the_service_error_response_does_not_match_the_api_contract'),
      'contract',
      response.status
    )
  }
  return new ApiClientError(
    uiT(
      error instanceof SyntaxError
        ? 'apfUi.the_service_response_is_not_valid_json'
        : 'apfUi.the_successful_service_response_does_not_match_the_api_contract'
    ),
    'contract',
    response?.status
  )
}
