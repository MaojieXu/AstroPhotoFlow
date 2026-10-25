import {describe,expect,it} from 'vitest'
import {assetParametersSchema} from '@frontend/assets/contracts'

describe('asset parameter contracts',()=>{
  it.each(['MONO','RGGB','BGGR','GRBG','GBRG','XTRANS','QUAD_BAYER'])('accepts CFA value %s',cfa_pattern=>{
    expect(assetParametersSchema.parse({
      camera_id:null,optical_system_id:null,filter_id:null,parameter_mode:'standard',iso:null,gain:null,offset:null,
      exposure_seconds:null,integration_seconds:null,sensor_temperature_c:null,binning_x:null,binning_y:null,cfa_pattern
    }).cfa_pattern).toBe(cfa_pattern)
  })
})
