import { z } from 'zod'
import type { AssetOut, CanvasDataRequest, DatasetMemberOut, DatasetMemberSummary, DatasetOut, LibraryItemPage, ProjectAssetReferenceOut, ProjectDatasetReferenceOut } from '../../../generated/api/types.gen'
import { zAssetOut, zDatasetMemberOut, zDatasetMemberSummary, zDatasetOut, zLibraryItemPage, zProjectAssetReferenceOut, zProjectDatasetReferenceOut } from '../../../generated/api/zod.gen'

type MemberView = Pick<DatasetMemberOut, 'asset'> & { member_position: DatasetMemberOut['position'] }
export type MaterialRecord = LibraryItemPage['items'][number] | AssetOut | DatasetOut | ProjectAssetReferenceOut | ProjectDatasetReferenceOut | MemberView | DatasetMemberSummary
export type PreviewMember = Pick<AssetOut, 'id' | 'name' | 'view_base'>
type DatasetRecord = Extract<LibraryItemPage['items'][number], { entry_type: 'dataset' }> | DatasetOut | ProjectDatasetReferenceOut

export const datasetChoiceToRecord = zDatasetOut.extend({ entry_type: z.literal('dataset') }).transform(({ entry_type: _entryType, ...record }) => record)
const memberViewSchema = zDatasetMemberOut.pick({ asset: true }).extend({ member_position: zDatasetMemberOut.shape.position })

export function resolveMaterialRecord(value: unknown): MaterialRecord | undefined {
  if (typeof value !== 'object' || value === null) return
  if ('project_id' in value) {
    if ('asset_id' in value) return zProjectAssetReferenceOut.parse(value)
    if ('dataset_id' in value) return zProjectDatasetReferenceOut.parse(value)
    return
  }
  if ('member_position' in value && 'summary' in value) return zDatasetMemberSummary.parse(value)
  if ('member_position' in value) return memberViewSchema.parse(value)
  if ('entry_type' in value) return zLibraryItemPage.shape.items.element.parse(value)
  if ('member_count' in value) return zDatasetOut.parse(value)
  if ('storage_location' in value) return zAssetOut.parse(value)
}

function isDataset(record: MaterialRecord): record is DatasetRecord {
  if ('entry_type' in record) return record.entry_type === 'dataset'
  return 'dataset' in record || 'member_count' in record
}

export function datasetReference(record: MaterialRecord): { id: string } | undefined {
  if (!isDataset(record)) return
  return { id: 'dataset' in record ? record.dataset_id : record.id }
}

export function assetContent(record: MaterialRecord): AssetOut | undefined {
  if ('asset' in record) return record.asset
  if ('storage_location' in record) return record
}

export function assetPreview(record: MaterialRecord): PreviewMember | undefined {
  if ('entry_type' in record) {
    if (record.entry_type === 'asset' && record.view_base) return { id: record.id, name: record.name, view_base: record.view_base }
    return
  }
  return assetContent(record)
}

export function materialCanvasSource(record: MaterialRecord): CanvasDataRequest | undefined {
  if (isDataset(record)) {
    const reference = datasetReference(record)
    return reference && record.input_ready ? { entry_type: 'dataset', id: reference.id } : undefined
  }
  if ('entry_type' in record) return record.input_ready ? { entry_type: 'asset', id: record.id } : undefined
  const asset = assetContent(record)
  return asset?.availability === 'available' ? { entry_type: 'asset', id: asset.id } : undefined
}

export function materialPreviewBase(record: MaterialRecord, member: PreviewMember): string {
  if ('project_id' in record && 'asset_id' in record) return record.view_base
  return member.view_base
}

export function materialThumbnailKey(record: MaterialRecord): string {
  if ('member_position' in record && 'dataset_id' in record) return `member:${record.dataset_id}:${record.id}`
  if ('member_position' in record) return `member:${record.asset.id}`
  if ('project_id' in record) return `project:${record.project_id}:${record.id}`
  return `${isDataset(record) ? 'dataset' : 'asset'}:${record.id}`
}
