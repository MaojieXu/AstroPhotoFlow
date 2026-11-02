import {
  zAssetOut,
  zAssetVersionOut,
  zDatasetMemberOut
} from '@ui/generated/api/zod.gen'

const created = '2026-10-22T20:00:00Z'

function versionFixture(assetId: unknown, version: Record<string, unknown>) {
  const capture = version.capture_snapshot
  // Explicitly adapt the historical captured fixture, not production input.
  const snapshot =
    typeof capture === 'object' &&
    capture !== null &&
    'parameter_mode' in capture
      ? { parameters: capture }
      : (capture ?? null)
  return zAssetVersionOut.parse({
    version_number: 1,
    storage_mode: 'managed',
    storage_location: 'test/source.fits',
    byte_size: 10,
    content_hash: null,
    availability: 'available',
    camera_id: null,
    optical_system_id: null,
    filter_id: null,
    frame_type: null,
    calibration_level: null,
    scientific_metadata: null,
    created_at: created,
    asset_id: assetId,
    view_base: `/astrophotoflow/api/v1/library/assets/${assetId}/versions/${version.id}/previews`,
    ...version,
    capture_snapshot: snapshot
  })
}

export function fixedMemberFixture(
  asset: Record<string, unknown>,
  version: Record<string, unknown>,
  datasetVersionId: string,
  position: number
) {
  const fixed = versionFixture(asset.id, version)
  const current = asset.current_version
  const record = zAssetOut.parse({
    scope: 'shared',
    owner_project_id: null,
    role: 'raw',
    calibration_level: null,
    classification: {},
    parameters: {},
    value_sources: {},
    notes: null,
    status: 'active',
    revision: 1,
    created_at: created,
    current_version_id: fixed.id,
    ...asset,
    equipment_snapshot: asset.equipment_snapshot ?? {},
    current_version:
      typeof current === 'object' && current !== null
        ? versionFixture(asset.id, { ...current })
        : fixed
  })
  return zDatasetMemberOut.parse({
    id: `00000000-0000-4000-8000-${String(500000 + position).padStart(12, '0')}`,
    dataset_version_id: datasetVersionId,
    asset_version_id: fixed.id,
    position,
    relative_path: null,
    calibration_overrides: {},
    asset: record,
    version: fixed
  })
}
