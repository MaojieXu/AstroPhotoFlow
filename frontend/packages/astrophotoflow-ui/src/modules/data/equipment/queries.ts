import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { catalogApi } from '../api'
import { readPages } from '../library/pagination'
import { zEquipmentPage, zEquipmentSetupPage } from '../../../generated/api/zod.gen'
import type { EquipmentSetupPage, ListEquipmentApiV1EquipmentGetData, ListSetupsApiV1EquipmentSetupsGetData, EquipmentPage } from '../../../generated/api/types.gen'

export const equipmentChoicesKey = (workspaceId: string) =>
  [...workspaceQueryKey(workspaceId), 'equipment', 'choices'] as const

export function useImportEquipmentChoices(workspace: MaybeRefOrGetter<string>) {
  const connectionReady = useQueryAvailability()
  return useQuery({
    queryKey: computed(() => [...workspaceQueryKey(toValue(workspace)), 'equipment', 'import-choices'] as const),
    enabled: computed(() => connectionReady.value && Boolean(toValue(workspace))),
    queryFn: async ({ signal }) => {
      const [setups, equipment] = await Promise.all([
        readPages(offset => catalogApi.setups({limit:200,offset:offset??0,sort_by:'name',order:'asc',status:'active'},signal),true,signal),
        readPages(offset => catalogApi.equipment({limit:200,offset:offset??0,sort_by:'name',order:'asc',status:'active'},signal),true,signal)
      ])
      return {setups:setups.items, equipment:equipment.items}
    }
  })
}

export function useEquipmentChoices(workspace: MaybeRefOrGetter<string>) {
  const client = useQueryClient()
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey: computed(() => equipmentChoicesKey(toValue(workspace))),
    enabled: computed(() => connectionReady.value && Boolean(toValue(workspace))),
    queryFn: async ({ signal }) => {
      const items: EquipmentPage['items'] = []
      for (let offset = 0, total = 1; offset < total;) {
        signal.throwIfAborted()
        const page = await catalogApi.equipment({ limit: 200, offset, sort_by: 'name', order: 'asc', status: 'all' }, signal)
        items.push(...page.items)
        offset += page.limit
        total = page.total
      }
      return items
    },
    refetchInterval: 10_000
  })

  async function refresh(force = false) {
    const workspaceId = toValue(workspace)
    if (!connectionReady.value || !workspaceId) return
    if (force) {
      const filters = { queryKey: equipmentChoicesKey(workspaceId) }
      await client.cancelQueries(filters)
      await client.invalidateQueries(filters)
    } else if (!query.isSuccess.value) {
      await query.refetch()
    }
  }

  return { ...query, refresh }
}

export type EquipmentManagementRequest = { workspaceId: string } & (
  | { kind: 'equipment'; query: NonNullable<ListEquipmentApiV1EquipmentGetData['query']> }
  | { kind: 'setups'; query: NonNullable<ListSetupsApiV1EquipmentSetupsGetData['query']> }
)
type ManagementPage = Pick<EquipmentPage, 'total' | 'limit' | 'offset'> & {
  items: EquipmentPage['items'] | EquipmentSetupPage['items']
}

export function useEquipmentManagementQuery(
  request: MaybeRefOrGetter<EquipmentManagementRequest | undefined>,
  paused: MaybeRefOrGetter<boolean>
) {
  const client = useQueryClient()
  const queryKey = computed(() => {
    const current = toValue(request)
    return current ? [...workspaceQueryKey(current.workspaceId), 'equipment', current.kind, current.query] as const : ['equipment-management-idle'] as const
  })
  const connectionReady = useQueryAvailability()
  const query = useQuery({
    queryKey,
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId) && !toValue(paused)),
    queryFn: async ({ signal }): Promise<ManagementPage> => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('Equipment management requires a workspace identity')
      return current.kind === 'equipment'
        ? catalogApi.equipment(current.query, signal)
        : catalogApi.setups(current.query, signal)
    },
    refetchInterval: 10_000
  })
  watch(() => toValue(paused), value => {
    if (value) void client.cancelQueries({ queryKey: queryKey.value })
  }, { flush: 'sync' })

  function updateItems(items: unknown[]) {
    const current = toValue(request)
    if (!current) return
    const validated = (current.kind === 'equipment' ? zEquipmentPage.shape.items : zEquipmentSetupPage.shape.items).parse(items)
    client.setQueryData<ManagementPage>(queryKey.value, previous => previous && ({ ...previous, items: validated }))
    void client.invalidateQueries({queryKey:queryKey.value})
    if (current.kind === 'equipment') void client.invalidateQueries({ queryKey: equipmentChoicesKey(current.workspaceId) })
  }
  async function refresh() {
    const current=toValue(request)
    if(!current)return
    await client.invalidateQueries({queryKey:[...workspaceQueryKey(current.workspaceId),'equipment',current.kind],refetchType:'none'})
    return query.refetch({cancelRefetch:false})
  }
  return { ...query, refresh, updateItems }
}
