import { zDatasetOut, zLibraryItemPage, zLibraryMetadataSummary } from '@ui/generated/api/zod.gen'

type SampleAsset = { id: string; name: string; parameters?: Record<string, unknown> | null; classification?: Record<string, unknown> | null; equipment_snapshot?: Record<string, { name?: string } | null>; scope?: string; status?: string; revision?: number; notes?: string | null; created_at?: string; storage_mode?: string; availability?: string; content_hash?: string | null; byte_size?: number | null; scientific_metadata?: Record<string, unknown> | null; view_base?: string } & Record<string, unknown>

type SampleMember = { asset: SampleAsset }
type SampleDataset = { id: string; name: string; notes?: string | null; status?: string; revision?: number; created_at?: string }

function values(items: unknown[]) {
  const known = items.filter(value => value !== undefined && value !== null)
  if (!known.length) return {state: 'unknown', value: null}
  if (known.length !== items.length || new Set(known.map(value => JSON.stringify(value))).size !== 1) return {state: 'mixed', value: null}
  return {state: 'consistent', value: known[0]}
}

export function exposureForMembers(members: SampleMember[]) {
  const subframes = members.filter(member => member.asset.classification?.frame_class === 'subframe')
  const known = subframes.flatMap(member => typeof member.asset.parameters?.exposure_seconds === 'number' ? [member.asset.parameters.exposure_seconds] : [])
  return {subframe_count:subframes.length,known_count:known.length,unknown_count:subframes.length-known.length,
    total_seconds:known.length ? known.reduce((sum,value)=>sum+value,0) : null,complete:known.length===subframes.length}
}

export function calibrationForMembers(members: SampleMember[]) {
  const counts = {UnCalibrated: 0, Calibrated: 0, Unknown: 0}
  for (const {asset} of members) {
    const status = asset.calibration_status
    if (status === 'UnCalibrated' || status === 'Calibrated') counts[status]++
    else counts.Unknown++
  }
  const present = (['UnCalibrated', 'Calibrated', 'Unknown'] as const).filter(status => counts[status] > 0)
  return {calibration_status: present.length === 1 ? present[0] : 'Unknown', calibration_counts: counts}
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
    ...equipment, storage_mode: values(members.map(member => member.asset.storage_mode)), availability: values(members.map(member => member.asset.availability)),
  })
}

function thumbnail(asset: SampleAsset) {
  return {asset_id: asset.id, view_base: asset.view_base ?? `/astrophotoflow/api/v1/library/assets/${asset.id}/previews`, hdu_index: 0}
}

export function libraryAsset(asset: SampleAsset) {
  return zLibraryItemPage.shape.items.element.parse({...calibrationForMembers([{asset}]), view_base: thumbnail(asset).view_base, entry_type: 'asset', id: asset.id, name: asset.name, notes: asset.notes ?? null,
    status: asset.status ?? 'active', revision: asset.revision ?? 1, created_at: asset.created_at ?? '2026-10-22T20:00:00Z',
    member_count: 1, matching_member_count: 1, input_ready: Boolean(asset.availability === 'available' && asset.content_hash && asset.byte_size != null),
    exposure_summary: exposureForMembers([{asset}]), summary: metadataForMembers([{asset}]), thumbnail: thumbnail(asset), import_issue: null,
  })
}

export function libraryDataset(dataset: SampleDataset, contents: {members: SampleMember[]}, matching = contents.members.length) {
  return zLibraryItemPage.shape.items.element.parse({...calibrationForMembers(contents.members), entry_type: 'dataset', id: dataset.id, name: dataset.name, notes: dataset.notes ?? null,
    status: dataset.status ?? 'active', revision: dataset.revision ?? 1, created_at: dataset.created_at ?? '2026-10-22T20:00:00Z',
    member_count: contents.members.length, matching_member_count: matching,
    input_ready: contents.members.length > 0 && contents.members.every(member => member.asset.availability === 'available' && Boolean(member.asset.content_hash) && member.asset.byte_size != null),
    exposure_summary: exposureForMembers(contents.members), summary: metadataForMembers(contents.members), thumbnail: contents.members[0] ? thumbnail(contents.members[0].asset) : null, import_issue: null,
  })
}


export function datasetFixture(dataset: SampleDataset & Record<string, unknown> & {member_count?: number}, members: SampleMember[] = []) {
  return zDatasetOut.parse({
    notes: null, status: 'active', revision: 1,
    created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:00Z',
    member_count: members.length, summary: metadataForMembers(members), exposure_summary: exposureForMembers(members),
    ...calibrationForMembers(members),
    ...(members.length ? {} : {calibration_counts:{UnCalibrated:0,Calibrated:0,Unknown:dataset.member_count ?? 0}}),
    input_ready: members.length > 0 && members.every(member => member.asset.availability === 'available'),
    ...dataset,
  })
}
