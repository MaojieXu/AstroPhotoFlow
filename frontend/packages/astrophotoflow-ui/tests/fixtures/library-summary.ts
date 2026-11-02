import { zLibraryItemPage, zLibraryMetadataSummary } from '@ui/generated/api/zod.gen'

type SampleAsset = { id: string; name: string; parameters?: Record<string, unknown> | null; classification?: Record<string, unknown> | null; equipment_snapshot?: Record<string, { name?: string } | null>; scope?: string; status?: string; revision?: number; notes?: string | null; created_at?: string; current_version_id?: string | null; current_version?: SampleVersion | null } & Record<string, unknown>
type SampleVersion = { id: string; version_number?: number; storage_mode?: string; availability?: string; content_hash?: string | null; byte_size?: number | null; scientific_metadata?: Record<string, unknown> | null }
type SampleMember = { asset: SampleAsset; version: SampleVersion }
type SampleDataset = { id: string; name: string; notes?: string | null; status?: string; revision?: number; created_at?: string; current_version_id?: string | null }

function values(items: unknown[]) {
  const known = items.filter(value => value !== undefined && value !== null)
  if (!known.length) return {state: 'unknown', value: null}
  if (known.length !== items.length || new Set(known.map(value => JSON.stringify(value))).size !== 1) return {state: 'mixed', value: null}
  return {state: 'consistent', value: known[0]}
}

export function metadataForMembers(members: SampleMember[]) {
  const keys = ['parameter_mode', 'iso', 'gain', 'offset', 'exposure_seconds', 'integration_seconds', 'sensor_temperature_c', 'binning_x', 'binning_y', 'cfa_pattern']
  const equipment = Object.fromEntries((['camera', 'optical_system', 'filter'] as const).map(slot => {
    const key = slot + '_id'
    const labels = members.map(member => { const name = member.asset.equipment_snapshot?.[key]?.name; return name ? {id: member.asset.parameters?.[key] ?? null, name} : null })
    const summary = values(labels)
    if (summary.state === 'unknown' && members.some(member => member.asset.parameters?.[key] != null)) summary.state = 'mixed'
    return [slot, summary]
  }))
  return zLibraryMetadataSummary.parse({
    classification: Object.fromEntries(['frame_class', 'frame_type'].map(key => [key, values(members.map(member => member.asset.classification?.[key]))])),
    parameters: Object.fromEntries(keys.map(key => [key, values(members.map(member => key === 'parameter_mode' && member.asset.parameters?.[key] === undefined ? 'standard' : member.asset.parameters?.[key]))])),
    ...equipment, storage_mode: values(members.map(member => member.version.storage_mode)), availability: values(members.map(member => member.version.availability)),
  })
}

export function libraryAsset(asset: SampleAsset) {
  const version = asset.current_version
  return zLibraryItemPage.shape.items.element.parse({view_base:version?`/astrophotoflow/api/v1/library/assets/${asset.id}/versions/${version.id}/previews`:null,entry_type: 'asset', id: asset.id, name: asset.name, notes: asset.notes ?? null,
    status: asset.status ?? 'active', revision: asset.revision ?? 1, created_at: asset.created_at ?? '2026-10-22T20:00:00Z',
    version_id: asset.current_version_id ?? version?.id ?? null, version_number: version?.version_number ?? null,
    member_count: 1, matching_member_count: 1, input_ready: Boolean(version?.availability === 'available' && version.content_hash && version.byte_size != null),
    summary: metadataForMembers([{asset, version: version ?? {id: ''}}]), thumbnail: version ? {asset_id: asset.id, asset_version_id: version.id, view_base:`/astrophotoflow/api/v1/library/assets/${asset.id}/versions/${version.id}/previews`, hdu_index: 0} : null, import_issue: null,
  })
}

export function libraryDataset(dataset: SampleDataset, version: {id: string; version_number?: number; members: SampleMember[]}, matching = version.members.length) {
  return zLibraryItemPage.shape.items.element.parse({entry_type: 'dataset', id: dataset.id, name: dataset.name, notes: dataset.notes ?? null,
    status: dataset.status ?? 'active', revision: dataset.revision ?? 1, created_at: dataset.created_at ?? '2026-10-22T20:00:00Z',
    version_id: version.id, version_number: version.version_number ?? 1, member_count: version.members.length, matching_member_count: matching,
    input_ready: version.members.length > 0 && version.members.every(member => member.version.availability === 'available' && Boolean(member.version.content_hash) && member.version.byte_size != null),
    summary: metadataForMembers(version.members), thumbnail: version.members[0] ? {asset_id: version.members[0].asset.id, asset_version_id: version.members[0].version.id, view_base:`/astrophotoflow/api/v1/library/assets/${version.members[0].asset.id}/versions/${version.members[0].version.id}/previews`, hdu_index: 0} : null, import_issue: null,
  })
}
