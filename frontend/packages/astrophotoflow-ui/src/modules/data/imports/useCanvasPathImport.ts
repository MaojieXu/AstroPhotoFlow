import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, onScopeDispose, shallowRef, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { uiT } from '../../../core/i18n'
import { workspaceQueryKey } from '../../../core/query/keys'
import type { CanvasData, createCanvasDataClient } from '../api/canvas'
import type { createImportClient } from '../api/imports'
import { importTasksKey } from './queries'
import { libraryQueryKey } from '../library/queries'

type Intent = { workspaceId: string; path: string; controller: AbortController }
type Session = {
  intent: Intent
  phase: 'submitting' | 'accepted' | 'unknown' | 'failed'
  taskId?: string
  resolve?: (result: CanvasData | undefined) => void
}
const active = new Set(['queued', 'running', 'cancelling'])

/** One explicit path import; polling only observes its accepted task. */
export function useCanvasPathImport(
  workspace: MaybeRefOrGetter<string | undefined>,
  imports: Pick<ReturnType<typeof createImportClient>, 'submit' | 'get'>,
  canvas: Pick<ReturnType<typeof createCanvasDataClient>, 'prepare'>
) {
  const cache = useQueryClient()
  const session = shallowRef<Session>()
  const failure = shallowRef<unknown>()
  const key = (current: Session) =>
    [
      ...workspaceQueryKey(current.intent.workspaceId),
      'canvas-import',
      current.taskId
    ] as const
  const submit = useMutation({
    mutationFn: (intent: Intent) =>
      imports.submit(
        { sources: [{ path: intent.path }], storage_mode: 'managed' },
        intent.controller.signal
      ),
    retry: false,
    onSettled: (_data, _error, intent) =>
      Promise.all([
        cache.invalidateQueries({
          queryKey: importTasksKey(intent.workspaceId)
        }),
        cache.invalidateQueries({
          queryKey: libraryQueryKey(intent.workspaceId)
        })
      ])
  })
  const query = useQuery({
    queryKey: computed(() =>
      session.value?.taskId ? key(session.value) : ['canvas-import-idle']
    ),
    enabled: computed(() =>
      Boolean(
        session.value?.taskId &&
        toValue(workspace) === session.value.intent.workspaceId
      )
    ),
    queryFn: async ({ signal }) => {
      const current = session.value
      if (!current?.taskId)
        throw new Error('Import observation requires an accepted task')
      const task = await imports.get(
        current.taskId,
        { items_limit: 1, items_offset: 0 },
        signal
      )
      signal.throwIfAborted()
      if (task.id !== current.taskId)
        throw new ApiClientError(
          'Import receipt does not match its original task',
          'contract'
        )
      const item = task.items[0]
      const prepared =
        task.items_total === 1 &&
        item?.content_status === 'available' &&
        item.asset_id
          ? await canvas.prepare(
              {
                entry_type: 'asset',
                id: item.asset_id
              },
              signal
            )
          : undefined
      return { task, prepared }
    },
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data &&
      !query.state.data.prepared &&
      active.has(query.state.data.task.status)
        ? 1500
        : false
  })

  function finish(result?: CanvasData) {
    const current = session.value
    if (!current?.resolve) return
    current.resolve(result)
    session.value = { ...current, resolve: undefined }
  }
  watch(
    [query.data, query.error, query.isFetching],
    ([result, error, fetching]) => {
      if (fetching || toValue(workspace) !== session.value?.intent.workspaceId)
        return
      if (error) {
        finish()
        return
      }
      if (!result) return
      if (result.prepared) {
        finish(result.prepared)
        return
      }
      if (!active.has(result.task.status)) {
        const detail = result.task.items[0]?.error ?? result.task.error
        failure.value =
          typeof detail?.message === 'string'
            ? detail.message
            : uiT(
                'apfUi.image_import_is_incomplete_check_the_library_import_records'
              )
        finish()
      }
    }
  )

  async function start(path: string): Promise<CanvasData | undefined> {
    const workspaceId = toValue(workspace)
    if (!workspaceId || session.value?.resolve) return
    const previous = session.value
    if (
      previous?.intent.workspaceId === workspaceId &&
      previous.intent.path === path &&
      previous.phase === 'unknown'
    )
      return
    failure.value = undefined
    submit.reset()
    let resolve!: (value: CanvasData | undefined) => void
    const completion = new Promise<CanvasData | undefined>((done) => {
      resolve = done
    })
    if (
      previous?.intent.workspaceId === workspaceId &&
      previous.intent.path === path &&
      previous.taskId
    ) {
      session.value = { ...previous, resolve }
      void query.refetch()
      return completion
    }
    previous?.intent.controller.abort()
    const intent: Intent = {
      workspaceId,
      path,
      controller: new AbortController()
    }
    session.value = { intent, phase: 'submitting', resolve }
    void accept(intent)
    return completion
  }
  async function accept(intent: Intent) {
    try {
      const accepted = await submit.mutateAsync(intent)
      if (session.value?.intent === intent)
        session.value = {
          ...session.value,
          phase: 'accepted',
          taskId: accepted.task_id
        }
    } catch (cause) {
      if (session.value?.intent === intent) {
        const knownRejection =
          cause instanceof ApiClientError &&
          cause.kind === 'service' &&
          cause.status !== undefined &&
          cause.status >= 400 &&
          cause.status < 500
        session.value = {
          ...session.value,
          phase: knownRejection ? 'failed' : 'unknown'
        }
        failure.value = cause
        finish()
      }
    }
  }
  watch(
    () => toValue(workspace),
    (value) => {
      const current = session.value
      if (current && value !== current.intent.workspaceId) {
        if (current.phase === 'submitting')
          session.value = { ...current, phase: 'unknown' }
        current.intent.controller.abort()
        if (current.taskId) void cache.cancelQueries({ queryKey: key(current) })
        finish()
      }
    },
    { flush: 'sync' }
  )
  onScopeDispose(() => {
    session.value?.intent.controller.abort()
    finish()
    session.value = undefined
  })
  return {
    start,
    busy: computed(() => Boolean(session.value?.resolve)),
    error: computed(() => {
      const current = session.value
      if (!current || toValue(workspace) !== current.intent.workspaceId)
        return undefined
      const cause = failure.value ?? submit.error.value ?? query.error.value
      return current.phase === 'unknown'
        ? `${cause instanceof Error ? cause.message : cause ? String(cause) : ''} ${uiT('apfUi.image_import_is_incomplete_check_the_library_import_records')}`.trim()
        : cause
    }),
    taskId: computed(() => session.value?.taskId),
    unknown: computed(() => session.value?.phase === 'unknown')
  }
}
