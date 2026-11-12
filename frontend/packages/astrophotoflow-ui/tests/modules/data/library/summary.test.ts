import { describe, expect, it } from 'vitest'
import { summaryRaw, summaryText, summaryClassificationText } from '@ui/modules/data/library/summary'
import { metadataForMembers } from '../../../fixtures/library-summary'

describe('server field summaries', () => {
  const asset = {id: 'a', name: 'sample', parameters: {gain: 0, offset: 0}, classification: {frame_class: 'video', frame_type: null}}
  const row = {summary: metadataForMembers([{asset}])}
  it('retains zero and separates unknown from mixed without member arrays', () => {
    expect(summaryRaw(row, 'gain')).toBe(0)
    expect(summaryText(row, 'offset')).toBe('0')
    expect(summaryText(row, 'iso')).toBe('—')
    const mixed = {...row, summary: {...row.summary, parameters: {...row.summary.parameters, gain: {state: 'mixed' as const, value: null}}}}
    expect(summaryRaw(mixed, 'gain')).toBe('mixed')
    expect(summaryText(mixed, 'gain')).toBe('混合')
  })
  it('keeps a known video classification without inventing a frame purpose', () => {
    expect(summaryClassificationText(row)).toBe('视频')
    expect(summaryRaw(row, 'frame_type')).toBe('')
  })
})
