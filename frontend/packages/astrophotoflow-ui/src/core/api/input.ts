import type { ZodType } from 'zod'
import { ApiClientError } from './errors'
import { uiT } from '../i18n'

/** Validate untrusted form data without filling defaults into a sparse patch. */
export function validatedInput<Output, Input>(
  schema: ZodType<Output, Input>,
  value: unknown
): Input {
  const result = schema.safeParse(value)
  if (!result.success) {
    throw new ApiClientError(
      uiT('apfUi.request_failed'),
      'contract',
      undefined,
      'INVALID_REQUEST',
      undefined,
      result.error.issues.map((issue) => ({
        path: issue.path.join('.'),
        message: issue.message
      }))
    )
  }
  // The schema just validated this external input. Its output may add defaults,
  // which must not turn an omitted update into a clearing/overriding operation.
  return value as Input
}
