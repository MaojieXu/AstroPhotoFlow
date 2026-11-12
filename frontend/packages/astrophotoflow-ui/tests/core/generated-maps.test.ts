import { expect, it } from 'vitest'
import { normalizeEnumMaps, normalizeJsonValue } from '../../openapi-input'
import { calibrationBindingsSchema } from '@ui/modules/data/api/contracts'
import { zNodeCapability, zJsonValue } from '@ui/generated/api/zod.gen'

it('retains nested JSON null, zero and arrays in generated contracts',()=>{
  const value={zero:0,empty:null,values:[false,'',{},[1,{nested:true}]]}
  expect(zJsonValue.parse(value)).toEqual(value)
  const original={components:{schemas:{JsonValue:{},Other:{}}}}
  const normalized=normalizeJsonValue(original)
  expect(original.components.schemas.JsonValue).toEqual({})
  expect(normalized).not.toBe(original)
  const constrained={components:{schemas:{JsonValue:{type:'string'}}}}
  expect(normalizeJsonValue(constrained)).toBe(constrained)
})

it.each([undefined,()=>{},Symbol('invalid'),1n,Number.NaN,Infinity,{nested:undefined},[()=>{}]])('generated JSON rejects non-JSON values: %s',value=>{
  expect(zJsonValue.safeParse(value).success).toBe(false)
})

it('normalizes finite-key maps without making members required or mutating the source', () => {
  const schema = {
    type: 'object',
    propertyNames: { enum: ['en', 'zh'] },
    additionalProperties: { $ref: '#/models/Display' }
  }
  expect(normalizeEnumMaps(schema)).toEqual({
    type: 'object',
    additionalProperties: false,
    properties: {
      en: { $ref: '#/models/Display' },
      zh: { $ref: '#/models/Display' }
    }
  })
  expect(schema.propertyNames.enum).toEqual(['en', 'zh'])
  const open = { type: 'object', additionalProperties: { type: 'number' } }
  expect(normalizeEnumMaps(open)).toEqual(open)
})

it('generated calibration and locale maps reject unknown keys while preserving sparse null choices', () => {
  expect(calibrationBindingsSchema.parse({})).toEqual({})
  expect(calibrationBindingsSchema.parse({ dark: null })).toEqual({
    dark: null
  })
  expect(calibrationBindingsSchema.safeParse({ invented: null }).success).toBe(
    false
  )
  expect(zNodeCapability.shape.display.safeParse({ fr: {} }).success).toBe(
    false
  )
})
