import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'

export function libraryError(cause: unknown): ApiClientError {
  if (cause instanceof ApiClientError) return cause
  return new ApiClientError(uiT('apfUi.request_failed'), 'contract')
}

export function libraryErrorText(value: ApiClientError) {
  if (value.kind === 'network')
    return uiT(
      'apfUi.asset_service_is_disconnected_check_whether_it_is_running'
    )
  if (value.kind === 'contract') return value.message
  if (value.code === 'SERVICE_NOT_CONFIGURED')
    return uiT('apfUi.local_service_credentials_are_not_configured')
  if (value.code === 'SERVICE_UNAVAILABLE')
    return uiT('apfUi.asset_service_is_currently_unavailable')
  if (value.code === 'SERVICE_TIMEOUT')
    return uiT('apfUi.asset_service_timed_out')
  if (value.code === 'AUTHENTICATION_REQUIRED')
    return uiT('apfUi.local_service_authentication_failed')
  if (value.code === 'REVISION_CONFLICT')
    return uiT(
      'apfUi.another_window_modified_this_record_your_draft_is_retained_read_the_cu'
    )
  return (
    value.message +
    (value.requestId ? uiT('apfUi.request') + value.requestId + '）' : '')
  )
}
