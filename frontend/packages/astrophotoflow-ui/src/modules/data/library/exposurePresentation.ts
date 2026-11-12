import type { ExposureSummary } from '../../../generated/api/types.gen'
import { uiT } from '../../../core/i18n'

/** A group total is supplied by the backend, never summed from the visible page. */
export function formatExposureSummary(summary: ExposureSummary | null | undefined): string {
  if (!summary || summary.subframe_count === 0) return '—'
  if (summary.total_seconds === null) return uiT('apfUi.exposure_total_unknown')
  const duration = formatExposureDuration(summary.total_seconds)
  return summary.unknown_count > 0
    ? uiT('apfUi.exposure_known', { duration, count: summary.unknown_count })
    : duration
}

export function formatExposureDuration(seconds: number): string {
  const milliseconds = Math.round(seconds * 1000)
  const hours = Math.floor(milliseconds / 3_600_000)
  const minutes = Math.floor((milliseconds - hours * 3_600_000) / 60_000)
  const remainder = (milliseconds - hours * 3_600_000 - minutes * 60_000) / 1000
  return [
    hours ? uiT('apfUi.exposure_duration_hours', { value: hours }) : '',
    minutes ? uiT('apfUi.exposure_duration_minutes', { value: minutes }) : '',
    remainder || (!hours && !minutes) ? uiT('apfUi.exposure_duration_seconds', { value: remainder }) : ''
  ].filter(Boolean).join('')
}
