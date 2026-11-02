import { toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type {
  AssetOut,
  AssetParametersPatch
} from '../../../generated/api/types.gen'
import { zPatchAssetApiV1LibraryAssetsAssetIdPatchBody } from '../../../generated/api/zod.gen'
import { validatedInput } from '../../../core/api/input'
import { useUpdateAsset } from './mutations'

export function useAssetEditor(workspaceId: MaybeRefOrGetter<string>) {
  const write = useUpdateAsset()
  async function saveField(
    asset: Pick<AssetOut, 'id' | 'revision'>,
    field: string,
    value: string | number | null
  ) {
    let payload: Record<string, unknown>
    if (['frame_class', 'frame_type'].includes(field))
      payload = {
        base_revision: asset.revision,
        classification: { [field]: value }
      }
    else if (
      [
        'camera_id',
        'optical_system_id',
        'filter_id',
        'parameter_mode',
        'iso',
        'gain',
        'offset',
        'exposure_seconds',
        'integration_seconds',
        'sensor_temperature_c',
        'binning_x',
        'binning_y',
        'cfa_pattern'
      ].includes(field)
    )
      payload = {
        base_revision: asset.revision,
        parameters: { [field]: value }
      }
    else payload = { base_revision: asset.revision, [field]: value }
    return write.mutateAsync({
      workspaceId: toValue(workspaceId),
      assetId: asset.id,
      body: validatedInput(
        zPatchAssetApiV1LibraryAssetsAssetIdPatchBody,
        payload
      )
    })
  }
  async function saveParameters(
    asset: Pick<AssetOut, 'id' | 'revision'>,
    parameters: AssetParametersPatch
  ) {
    return write.mutateAsync({
      workspaceId: toValue(workspaceId),
      assetId: asset.id,
      body: validatedInput(zPatchAssetApiV1LibraryAssetsAssetIdPatchBody, {
        base_revision: asset.revision,
        parameters
      })
    })
  }
  return { saveField, saveParameters, pending: write.isPending }
}
