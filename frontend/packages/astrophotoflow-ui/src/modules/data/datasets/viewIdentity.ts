import type { DatasetOut, LibraryDatasetSummary } from '../../../generated/api/types.gen'

export type DatasetViewIdentity = Pick<DatasetOut, 'id' | 'name' | 'revision' | 'member_count'>

export function datasetViewFromSummary(dataset: LibraryDatasetSummary): DatasetViewIdentity {
  return { id: dataset.id, name: dataset.name, revision: dataset.revision, member_count: dataset.member_count }
}

export function datasetViewFromAcknowledgement(dataset: DatasetOut): DatasetViewIdentity {
  return { id: dataset.id, name: dataset.name, revision: dataset.revision, member_count: dataset.member_count }
}
