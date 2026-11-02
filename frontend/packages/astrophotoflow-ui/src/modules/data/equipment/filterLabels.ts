import { uiT } from '../../../core/i18n'
import type { FilterSpecs } from '../../../generated/api/types.gen'

type FilterLabelInput = { name: string; specs?: FilterSpecs }

/** A display label never changes the physical filter or its member identity. */
export function filterLabel(filter: FilterLabelInput): string {
  const channel = filter.specs?.channel?.trim()
  const bandwidth = filter.specs?.bandwidth_nm
  const label = channel || uiT('apfUi.unspecified_filter_channel')
  const width = bandwidth == null || !Number.isFinite(bandwidth) || bandwidth <= 0 ? '' : ` ${bandwidth}nm`
  return `${label}${width}${channel || !filter.name ? '' : ` · ${filter.name}`}`
}

export function filterChoiceLabel(filter: FilterLabelInput): string {
  const label = filterLabel(filter)
  return filter.specs?.channel?.trim() ? `${label} · ${filter.name}` : label
}
