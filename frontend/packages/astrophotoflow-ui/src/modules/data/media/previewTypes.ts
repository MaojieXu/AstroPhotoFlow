import type { AssetOut, AssetVersionOut } from '../../../generated/api/types.gen'

// A view target, not another HTTP DTO or a scientific input.
export type PreviewPhoto = {
  assetId: AssetOut['id']
  versionId: AssetVersionOut['id']
  title: string
  basePath: string
}
