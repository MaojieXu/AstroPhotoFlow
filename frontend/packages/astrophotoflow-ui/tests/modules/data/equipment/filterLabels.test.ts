import { expect, it } from 'vitest'
import { filterChoiceLabel, filterLabel } from '@ui/modules/data/equipment/filterLabels'

it('formats an explicit channel and optional bandwidth while keeping physical names in choices', () => {
  const broad = { name: 'L-Pro', specs: { channel: 'RGB' } }
  const narrow = { name: 'Physical Ha 7', specs: { channel: 'Ha', bandwidth_nm: 7 } }
  expect(filterLabel(broad)).toBe('RGB')
  expect(filterLabel(narrow)).toBe('Ha 7nm')
  expect(filterChoiceLabel(narrow)).toBe('Ha 7nm · Physical Ha 7')
  expect(filterLabel({ name: 'Multi', specs: { channel: 'Ha + OIII' } })).toBe('Ha + OIII')
})

it('does not infer a channel from a physical name', () => {
  expect(filterLabel({ name: 'Ha 7nm', specs: { bandwidth_nm: 7 } })).toBe('未指定通道 7nm · Ha 7nm')
  expect(filterChoiceLabel({ name: 'L-Pro' })).toBe('未指定通道 · L-Pro')
})
