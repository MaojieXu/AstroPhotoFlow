import { z } from 'zod'
import type { AssetOut, AssetVersionOut, CanvasDataRequest, DatasetMemberOut, DatasetOut, LibraryItemPage, ProjectAssetReferenceOut, ProjectDatasetReferenceOut } from '../../../generated/api/types.gen'
import { zAssetOut, zDatasetMemberOut, zDatasetOut, zLibraryItemPage, zProjectAssetReferenceOut, zProjectDatasetReferenceOut } from '../../../generated/api/zod.gen'

type MemberView = Pick<DatasetMemberOut, 'asset' | 'version'> & { member_position: DatasetMemberOut['position'] }
export type MaterialRecord = LibraryItemPage['items'][number] | AssetOut | DatasetOut | ProjectAssetReferenceOut | ProjectDatasetReferenceOut | MemberView
export type FixedPreviewMember = { asset: Pick<AssetOut, 'id' | 'name'>; version: Pick<AssetVersionOut, 'id' | 'view_base'> }
type DatasetRecord = Extract<LibraryItemPage['items'][number], { entry_type: 'dataset' }> | DatasetOut | ProjectDatasetReferenceOut

// The member UI projects the generated position field under this display name.
export const datasetChoiceToRecord = zDatasetOut.extend({entry_type:z.literal('dataset')}).transform(({entry_type:_entryType,...record})=>record)

const memberViewSchema = zDatasetMemberOut.pick({ asset: true, version: true }).extend({ member_position: zDatasetMemberOut.shape.position })

/** Resolve only the actual material DTOs consumed by the library and fixed references. */
export function resolveMaterialRecord(value: unknown): MaterialRecord | undefined {
  if (typeof value !== 'object' || value === null) return
  if ('project_id' in value) {
    if ('asset_version_id' in value) return zProjectAssetReferenceOut.parse(value)
    if ('dataset_version_id' in value) return zProjectDatasetReferenceOut.parse(value)
    return
  }
  if ('member_position' in value) return memberViewSchema.parse({asset:'asset' in value?value.asset:undefined,version:'version' in value?value.version:undefined,member_position:value.member_position})
  if ('version_id' in value && 'entry_type' in value) return zLibraryItemPage.shape.items.element.parse(value)
  if ('member_count' in value) return 'entry_type' in value?datasetChoiceToRecord.parse(value):zDatasetOut.parse(value)
  if ('current_version' in value) return zAssetOut.parse(value)
}

function isDataset(record: MaterialRecord): record is DatasetRecord {
  if ('version_id' in record) return record.entry_type === 'dataset'
  return 'member_count' in record
}

export function fixedDatasetReference(record: MaterialRecord): { id: string; versionId: string } | undefined {
  if (!isDataset(record)) return
  if ('dataset_version_id' in record) return { id: record.dataset_id, versionId: record.dataset_version_id }
  const versionId = 'version_id' in record ? record.version_id : record.current_version_id
  return versionId ? { id: record.id, versionId } : undefined
}

export function fixedAssetContent(record: MaterialRecord): {asset: AssetOut; version: AssetVersionOut} | undefined {
  if ('asset' in record) return {asset:record.asset,version:record.version}
  if ('current_version' in record && record.current_version) return {asset:record,version:record.current_version}
}

export function fixedAssetPreview(record: MaterialRecord): FixedPreviewMember | undefined {
  if ('version_id' in record) {
    if (record.entry_type === 'asset' && record.version_id && record.view_base) return { asset: { id: record.id, name: record.name }, version: { id: record.version_id, view_base: record.view_base } }
    return
  }
  return fixedAssetContent(record)
}

export function materialCanvasSource(record: MaterialRecord): CanvasDataRequest | undefined {
  // Project-reference editing remains separate from library drag sources.
  if ('project_id' in record) return
  if (isDataset(record)) {
    const reference = fixedDatasetReference(record)
    return reference && record.input_ready ? { entry_type: 'dataset', id: reference.id, version_id: reference.versionId } : undefined
  }
  if ('version_id' in record) {
    return record.input_ready && record.version_id ? { entry_type: 'asset', id: record.id, version_id: record.version_id } : undefined
  }
  const fixed = fixedAssetContent(record)
  return fixed?.version.availability === 'available' ? { entry_type: 'asset', id: fixed.asset.id, version_id: fixed.version.id } : undefined
}

export function materialPreviewBase(record: MaterialRecord, member: FixedPreviewMember): string {
  if ('project_id' in record && 'asset_version_id' in record) return record.view_base
  return member.version.view_base
}

export function materialThumbnailKey(record: MaterialRecord): string {
  if ('member_position' in record) return `member:${record.asset.id}:${record.version.id}:${record.member_position}`
  if ('project_id' in record) return `project:${record.project_id}:${record.id}:${'asset_version_id' in record?record.asset_version_id:record.dataset_version_id}`
  if (isDataset(record)) return `dataset:${record.id}:${fixedDatasetReference(record)?.versionId ?? 'none'}`
  return `asset:${record.id}:${fixedAssetPreview(record)?.version.id ?? 'none'}`
}
