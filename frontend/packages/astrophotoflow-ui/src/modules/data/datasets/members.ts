import { libraryApi } from '../api'
import type { ListDatasetMembersData } from '../../../generated/api/types.gen'
import { ApiClientError } from '../api/client'
import { uiT } from '../../../core/i18n'

export type FixedDataset = { id: string; versionId: string }
type MemberQuery = NonNullable<ListDatasetMembersData['query']>

export function readMemberPage(reference: FixedDataset, query: MemberQuery, signal?: AbortSignal) {
  return libraryApi.members(reference.id, reference.versionId, query, signal)
}

export async function fixedMemberAt(reference: FixedDataset, index: number, signal?: AbortSignal) {
  if (!Number.isInteger(index) || index < 0) throw new ApiClientError(uiT('apfUi.fixed_member_is_out_of_range'), 'contract')
  const page = await readMemberPage(reference, { limit: 1, offset: index, sort_by: 'position', order: 'asc' }, signal)
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  const member = page.items[0]
  if (!member) throw new ApiClientError(uiT('apfUi.fixed_member_is_out_of_range'), 'contract')
  return member
}
