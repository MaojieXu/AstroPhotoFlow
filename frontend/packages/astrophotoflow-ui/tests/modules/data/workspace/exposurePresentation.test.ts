import { describe, expect, it } from 'vitest'
import { formatExposureDuration, formatExposureSummary } from '@ui/modules/data/library/exposurePresentation'

describe('derived group exposure display', () => {
  it('formats the complete backend total without multiplying visible members', () => {
    expect(formatExposureSummary({subframe_count:147,known_count:147,unknown_count:0,total_seconds:44_100,complete:true})).toBe('12小时15分')
    expect(formatExposureDuration(1.25)).toBe('1.25秒')
    expect(formatExposureDuration(59.9999)).toBe('1分')
  })

  it('distinguishes no subframes, wholly unknown, partially unknown and valid zero', () => {
    expect(formatExposureSummary({subframe_count:0,known_count:0,unknown_count:0,total_seconds:null,complete:true})).toBe('—')
    expect(formatExposureSummary({subframe_count:3,known_count:0,unknown_count:3,total_seconds:null,complete:false})).toBe('累计曝光未知')
    expect(formatExposureSummary({subframe_count:5,known_count:2,unknown_count:3,total_seconds:600,complete:false})).toBe('10分 · 3张曝光未知')
    expect(formatExposureSummary({subframe_count:2,known_count:2,unknown_count:0,total_seconds:0,complete:true})).toBe('0秒')
  })
})
