import { useQuery } from '@tanstack/vue-query'
import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'

import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { importApi } from '../api'
import { ApiClientError } from '../../../core/api/errors'

export const importTasksKey = (workspaceId: string) =>
  [...workspaceQueryKey(workspaceId), 'imports', 'tasks'] as const

const processingStatuses = new Set(['queued', 'running', 'cancelling'])

export function useImportTasks(workspace: MaybeRefOrGetter<string>) {
  const connectionReady = useQueryAvailability()
  return useQuery({
    queryKey: computed(() => importTasksKey(toValue(workspace))),
    enabled: computed(() => connectionReady.value && Boolean(toValue(workspace))),
    queryFn: ({ signal }) => importApi.list({ limit: 50, offset: 0, status: 'all' }, signal),
    // The visible directory discovers external tasks; only active work polls fast.
    refetchInterval: query =>
      query.state.data?.items.some(task => processingStatuses.has(task.status) || task.report.destination?.project_link.state === 'pending') ? 1_500 : 30_000
  })
}

export function useImportIssueReport(request: MaybeRefOrGetter<{workspaceId: string; taskId: string} | undefined>) {
  const connectionReady = useQueryAvailability()
  return useQuery({
    queryKey: computed(() => {
      const current = toValue(request)
      return current ? [...importTasksKey(current.workspaceId), 'report', current.taskId] as const : ['import-report-idle'] as const
    }),
    enabled: computed(() => connectionReady.value && Boolean(toValue(request)?.workspaceId)),
    queryFn: async ({ signal }) => {
      const current = toValue(request)
      if (!current?.workspaceId) throw new Error('Import report requires a workspace identity')
      const {items:firstItems,...task} = await importApi.get(current.taskId,{items_limit:200,items_offset:0},signal)
      const items = [...firstItems]
      while (items.length < task.items_total) {
        signal.throwIfAborted()
        const page = await importApi.get(current.taskId,{items_limit:200,items_offset:items.length},signal)
        if (!page.items.length) throw new ApiClientError('Import report page ended before its declared total','contract')
        items.push(...page.items)
      }
      signal.throwIfAborted()
      return {task,items}
    },
    refetchInterval: query => query.state.data && processingStatuses.has(query.state.data.task.status) ? 1_500 : false
  })
}
