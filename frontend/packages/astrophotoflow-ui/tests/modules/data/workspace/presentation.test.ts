import { expect, it } from 'vitest'
import { parameterSummary } from '@ui/modules/data/workspace/presentation'

it('distinguishes recorded zero from a missing number without inferring a parameter mode',()=>{
  expect(parameterSummary({parameter_mode:'standard',gain:0})).toBe('模式未指定 · Gain 0')
  expect(parameterSummary({parameter_mode:'standard',gain:null})).toBe('未指定')
  expect(parameterSummary({parameter_mode:'gain',gain:0,offset:0})).toBe('Gain · 0 / Offset · 0')
})
