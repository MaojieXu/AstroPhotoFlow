import { describe, expect, expectTypeOf, it } from 'vitest'
import { summaryParameters } from '@ui/modules/data/library/summary'
import { binValue, binEditValue, binEditChoices } from '@ui/modules/data/assets/binning'
import { metadataForMembers } from '../../../fixtures/library-summary'

describe('typed parameter display values', () => {
  it('keeps zero, unknown and mixed distinct without widening numeric fields to arbitrary strings', () => {
    const summary = metadataForMembers([])
    summary.parameters.gain = { state: 'consistent', value: 0 }
    summary.parameters.offset = { state: 'unknown', value: null }
    summary.parameters.iso = { state: 'mixed', value: null }
    summary.parameters.parameter_mode = { state: 'consistent', value: 'gain' }
    summary.camera = { state: 'mixed', value: null }
    const values = summaryParameters({ summary })
    expect(values).toMatchObject({ gain: 0, offset: null, iso: 'mixed', parameter_mode: 'gain', camera_id: 'mixed' })
    expectTypeOf(values.gain).toEqualTypeOf<number | 'mixed' | null>()
  })

  it('keeps asymmetric imported Binning selectable without silently converting it to a standard square value', () => {
    const parameters = { binning_x: 2, binning_y: 1 }
    expect(binValue(parameters)).toBe('Bin2×1')
    expect(binEditValue(parameters)).toBe('legacy:2x1')
    expect(binEditChoices(parameters).some(choice => choice.value === 'legacy:2x1')).toBe(true)
    expect(binEditValue({ binning_x: null, binning_y: null })).toBe('')
    expect(binValue({ binning_x: null, binning_y: null })).toBeNull()
  })
})
