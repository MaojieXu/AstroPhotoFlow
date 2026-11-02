import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useStableQueryInput } from '../../../core/query/viewInput'
import type { ListViewInput } from '../../../core/query/viewInput'
import {
  zListEquipmentApiV1EquipmentGetQuery,
  zListSetupsApiV1EquipmentSetupsGetQuery
} from '../../../generated/api/zod.gen'
import { nonEmptyQuery } from '../api/catalog'
import { useEquipmentManagementQuery } from './queries'
import type { EquipmentManagementRequest } from './queries'

export interface EquipmentManagementViewInput extends ListViewInput {
  kind: 'equipment' | 'setups'
  status: 'active' | 'archived' | 'all'
  equipmentKind: string
  sort: { by: string; order: 'asc' | 'desc' }
}
export function useEquipmentManagementView(
  input: MaybeRefOrGetter<EquipmentManagementViewInput>,
  paused: MaybeRefOrGetter<boolean>
) {
  const desired = computed<EquipmentManagementRequest | undefined>(() => {
    const state = toValue(input)
    if (!state.active || !state.workspaceId) return
    const common = {
      limit: 50,
      offset: state.offset,
      q: state.search || undefined,
      status: state.status
    }
    return state.kind === 'equipment'
      ? {
          workspaceId: state.workspaceId,
          kind: 'equipment',
          query: zListEquipmentApiV1EquipmentGetQuery.parse(
            nonEmptyQuery({ ...common, kind: state.equipmentKind })
          )
        }
      : {
          workspaceId: state.workspaceId,
          kind: 'setups',
          query: zListSetupsApiV1EquipmentSetupsGetQuery.parse({
            ...common,
            sort_by: state.sort.by,
            order: state.sort.order
          })
        }
  })
  const request = useStableQueryInput(desired, paused, (state) =>
    JSON.stringify([state.workspaceId, state.kind])
  )
  return { request, query: useEquipmentManagementQuery(request, paused) }
}
