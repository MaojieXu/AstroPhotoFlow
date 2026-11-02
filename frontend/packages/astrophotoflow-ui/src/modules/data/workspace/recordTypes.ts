import type { AssetOut, DatasetOut, EquipmentPage, EquipmentSetupOut, LibraryItemPage, ProjectAssetReferenceOut, ProjectDatasetReferenceOut, ProjectOut } from '../../../generated/api/types.gen'
import type { useDatasetMembersQuery } from '../datasets/queries'
import type { useProjectRecordsQuery } from '../projects/queries'
import type { useLibrarySelectionQuery } from '../library/selectionQueries'
import { datasetChoiceToRecord } from '../library/materialRecords'

export type MemberRecord = ReturnType<typeof useDatasetMembersQuery>['rows']['value'][number]
type LibraryRecord = LibraryItemPage['items'][number]
type EquipmentRecord = EquipmentPage['items'][number]
export type DatasetRecord = Extract<LibraryRecord, { entry_type: 'dataset' }> | DatasetOut | ProjectDatasetReferenceOut
export type AssetRecord = Extract<LibraryRecord, { entry_type: 'asset' }> | AssetOut | ProjectAssetReferenceOut | MemberRecord
export type WorkspaceRecord = LibraryRecord | AssetOut | DatasetOut | ProjectOut | EquipmentRecord | EquipmentSetupOut
  | MemberRecord | ReturnType<typeof useProjectRecordsQuery>['rows']['value'][number]
  | ReturnType<typeof useLibrarySelectionQuery>['rows']['value'][number]

export function isMemberRecord(row: WorkspaceRecord): row is MemberRecord { return 'member_position' in row }
export function isAssetRecord(row: WorkspaceRecord): row is AssetRecord {
  return ('entry_type' in row && row.entry_type === 'asset') || 'asset' in row || 'scope' in row
}
export function isDatasetRecord(row: WorkspaceRecord): row is DatasetRecord {
  if ('entry_type' in row) return row.entry_type === 'dataset'
  return 'dataset' in row || ('summary' in row && 'current_version_id' in row)
}
export function isProjectAssetReference(row: WorkspaceRecord): row is ProjectAssetReferenceOut { return 'project_id' in row && 'asset_version_id' in row }
export function isProjectDatasetReference(row: WorkspaceRecord): row is ProjectDatasetReferenceOut { return 'project_id' in row && 'dataset_version_id' in row }
export function isEquipmentRecord(row: WorkspaceRecord): row is EquipmentRecord { return 'kind' in row }
export function isSetupRecord(row: WorkspaceRecord): row is EquipmentSetupOut { return 'components' in row }
export function isProjectRecord(row: WorkspaceRecord): row is ProjectOut { return 'target_name' in row }

export function assetRecord(row: WorkspaceRecord): AssetOut | undefined {
  if ('asset' in row) return row.asset
  if ('scope' in row) return row
}
export function datasetRecord(row: DatasetRecord) {
  if ('dataset' in row) return row.dataset
  if ('entry_type' in row && 'current_version_id' in row) return datasetChoiceToRecord.parse(row)
  return row
}
export function recordEntity(row: WorkspaceRecord) {
  if ('asset' in row) return row.asset
  if ('dataset' in row) return row.dataset
  return row
}
export function recordIssue(row: WorkspaceRecord): string | null {
  return 'import_issue' in row ? row.import_issue : null
}
export function recordVersion(row: WorkspaceRecord) {
  if ('version' in row) return { id: row.version.id, number: row.version.version_number }
  if ('version_id' in row) return { id: row.version_id, number: row.version_number }
  if ('current_version' in row) return {id:row.current_version_id,number:row.current_version?.version_number??null}
  if ('current_version_id' in row) return { id: row.current_version_id, number: row.current_version_number }
}

export function acknowledgeAsset(row: AssetRecord, updated: AssetOut): WorkspaceRecord {
  if (isMemberRecord(row)) return {...row,...updated,asset:updated,version:row.version}
  if ('asset' in row) return {...row,asset:updated}
  if ('version_id' in row) return {...row,name:updated.name,notes:updated.notes,status:updated.status,revision:updated.revision}
  return updated
}
export function acknowledgeDataset(row: DatasetRecord, updated: DatasetOut): WorkspaceRecord {
  if ('dataset' in row) return {...row,dataset:updated}
  if ('version_id' in row) return {...row,name:updated.name,notes:updated.notes,status:updated.status,revision:updated.revision}
  return 'entry_type' in row ? {...updated,entry_type:'dataset'} : updated
}
