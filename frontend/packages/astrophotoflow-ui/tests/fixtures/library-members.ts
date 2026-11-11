import { zAssetOut, zDatasetMemberOut } from '@ui/generated/api/zod.gen'

const created = '2026-10-22T20:00:00Z'

export function assetFixture(asset: Record<string, unknown>) {
  return zAssetOut.parse({
    calibration_status: 'Unknown',
    scope: 'shared',
    owner_project_id: null,
    role: 'raw',
    calibration_level: null,
    classification: {},
    parameters: {},
    equipment_snapshot: {},
    value_sources: {},
    notes: null,
    status: 'active',
    revision: 1,
    created_at: created,
    storage_mode: 'managed',
    storage_location: 'test/source.fits',
    byte_size: 10,
    content_hash: 'blake3:' + 'a'.repeat(64),
    availability: 'available',
    capture_snapshot: null,
    scientific_metadata: null,
    view_base: `/astrophotoflow/api/v1/library/assets/${asset.id}/previews`,
    ...asset
  })
}

export function datasetMemberFixture(
  asset: Record<string, unknown>,
  datasetId: string,
  position: number
) {
  const record = assetFixture(asset)
  return zDatasetMemberOut.parse({
    id: `00000000-0000-4000-8000-${String(500000 + position).padStart(12, '0')}`,
    dataset_id: datasetId,
    asset_id: record.id,
    position,
    relative_path: null,
    asset: record
  })
}
