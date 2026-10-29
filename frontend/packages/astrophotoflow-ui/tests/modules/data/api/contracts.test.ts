import {describe,expect,it} from 'vitest'
import {assetContentObservationSchema,assetParametersSchema} from '@ui/modules/data/api/contracts'

describe('asset parameter contracts',()=>{
  it.each(['MONO','RGGB','BGGR','GRBG','GBRG','XTRANS','QUAD_BAYER'])('accepts CFA value %s',cfa_pattern=>{
    expect(assetParametersSchema.parse({
      camera_id:null,optical_system_id:null,filter_id:null,parameter_mode:'standard',iso:null,gain:null,offset:null,
      exposure_seconds:null,integration_seconds:null,sensor_temperature_c:null,binning_x:null,binning_y:null,cfa_pattern
    }).cfa_pattern).toBe(cfa_pattern)
  })
})

it('accepts a real nanosecond modification time without weakening observation identity',()=>{
  const id='00000000-0000-4000-8000-000000000001'
  const response={asset_id:id,base_version_id:id,base_revision:1,storage_mode:'managed',stored_hash:'blake3:one',state:'unchanged',observed_hash:'blake3:one',observed_byte_size:135360,observed_mtime_ns:1793223954488571800,error:null}
  expect(assetContentObservationSchema.parse(response).state).toBe('unchanged')
  expect(assetContentObservationSchema.safeParse({...response,asset_id:'invalid'}).success).toBe(false)
})
