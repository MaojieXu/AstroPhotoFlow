import type { DatasetOut, LibraryDatasetSummary } from '../../../generated/api/types.gen'

/** The resolved view identity distinguishes current browsing from pinned history. */
export type DatasetViewIdentity = Pick<DatasetOut, 'id' | 'name' | 'revision' | 'member_count'> & {
  current_version_id: string
  followsCurrent?: boolean
}

export function datasetViewFromSummary(dataset: LibraryDatasetSummary): DatasetViewIdentity | undefined {
  if (!dataset.version_id) return undefined
  return { id: dataset.id, name: dataset.name, revision: dataset.revision, member_count: dataset.member_count, current_version_id: dataset.version_id, followsCurrent: true }
}

export function datasetViewFromAcknowledgement(dataset: DatasetOut): DatasetViewIdentity | undefined {
  if (!dataset.current_version_id) return undefined
  return { id: dataset.id, name: dataset.name, revision: dataset.revision, member_count: dataset.member_count, current_version_id: dataset.current_version_id, followsCurrent: true }
}
