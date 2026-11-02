import type { LibraryEntryRemove, LibraryItemPage } from '../../../generated/api/types.gen'

export type LibraryRemovalReview =
  | { kind: 'asset'; request: LibraryEntryRemove & { entry_type: 'asset' }; title: string }
  | { kind: 'dataset'; request: LibraryEntryRemove & { entry_type: 'dataset' }; title: string; memberCount: number }

export function reviewLibraryRemoval(row: LibraryItemPage['items'][number]): LibraryRemovalReview {
  const reference = { id: row.id, revision: row.revision, current_version_id: row.version_id }
  if (row.entry_type === 'dataset') {
    return { kind: 'dataset', request: { ...reference, entry_type: 'dataset' }, title: row.name, memberCount: row.member_count }
  }
  return { kind: 'asset', request: { ...reference, entry_type: 'asset' }, title: row.name }
}
