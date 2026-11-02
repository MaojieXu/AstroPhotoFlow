import {
  computed,
  nextTick,
  onScopeDispose,
  shallowRef,
  toRaw,
  toValue,
  watch
} from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { ApiClientError } from '../../../core/api/errors'
import { exportRequestSchema } from '../api/exports'
import type { DataResult, ExportRequest } from '../api/exports'
import { useDataResult, useExportReceipt } from './queries'
import type { ExportClient } from './queries'
import {
  useSubmitResultExport,
  useCancelResultExport,
  useChooseExportDestination
} from './mutations'

export interface ResultExportScope {
  workspaceId: string
  client: ExportClient
  source: DataResult
  target: 'library' | 'local'
}
type Session = { key: string; body?: ExportRequest; observing: boolean }
export function useResultExport(
  scope: MaybeRefOrGetter<ResultExportScope | undefined>
) {
  const session = shallowRef<Session>(),
    diagnostic = shallowRef<unknown>()
  const intent = shallowRef<{
    key: string
    scope: ResultExportScope
    controller: AbortController
  }>()
  const result = useDataResult(scope)
  const submitMutation = useSubmitResultExport(),
    cancelMutation = useCancelResultExport(),
    chooseMutation = useChooseExportDestination()
  let alive = true
  const key = computed(() => {
    const current = toValue(scope)
    return current
      ? JSON.stringify([
          'apf-export',
          current.workspaceId,
          current.source.run_id,
          current.source.execution_id,
          current.target
        ])
      : undefined
  })
  const pendingBody = computed(() => session.value?.body)
  const currentSession = () =>
    toValue(scope) && session.value?.key === key.value
      ? session.value
      : undefined
  function observe(observing: boolean) {
    const current = currentSession()
    if (current) session.value = { ...current, observing }
  }
  const query = useExportReceipt(() => {
    const current = toValue(scope),
      saved = currentSession()
    return current && saved?.body && saved.observing
      ? {
          workspaceId: current.workspaceId,
          client: current.client,
          body: saved.body
        }
      : undefined
  })
  const receipt = computed(() =>
    currentSession()?.observing ? query.data.value : undefined
  )
  const active = computed(() =>
    Boolean(
      receipt.value &&
      ['queued', 'running', 'cancelling'].includes(receipt.value.state)
    )
  )
  const busy = computed(
    () =>
      Boolean(intent.value) ||
      submitMutation.isPending.value ||
      cancelMutation.isPending.value
  )
  const error = computed(
    () =>
      diagnostic.value ??
      result.error.value ??
      (result.data.value?.state !== 'completed'
        ? result.data.value?.error
        : undefined) ??
      query.error.value ?? receipt.value?.error
  )
  const sourceReady = computed(
    () => result.isSuccess.value && result.data.value?.state === 'completed'
  )
  watch(
    key,
    (current) => {
      if (!current) {
        intent.value?.controller.abort()
        intent.value = undefined
        return
      }
      if (current === session.value?.key) {
        observe(Boolean(session.value.body))
        return
      }
      intent.value?.controller.abort()
      intent.value = undefined
      diagnostic.value = undefined
      submitMutation.reset()
      cancelMutation.reset()
      chooseMutation.reset()
      const saved = sessionStorage.getItem(current)
      let body: ExportRequest | undefined
      if (saved)
        try {
          body = exportRequestSchema.parse(JSON.parse(saved))
          const expected = toValue(scope)!
          if (
            body.source.run_id !== expected.source.run_id ||
            body.source.execution_id !== expected.source.execution_id ||
            body.target !== expected.target
          )
            throw new ApiClientError(
              'Saved export does not match this source',
              'contract'
            )
        } catch (cause) {
          diagnostic.value = cause
          body = undefined
        }
      session.value = { key: current, body, observing: Boolean(body) }
    },
    { immediate: true }
  )
  const stillCurrent = (current: NonNullable<typeof intent.value>) =>
    alive &&
    intent.value === current &&
    key.value === current.key &&
    !current.controller.signal.aborted
  async function choose(body: Parameters<ExportClient['choose']>[0]) {
    const current = intent.value
    if (!current) return
    return chooseMutation.mutateAsync({
      client: current.scope.client,
      body,
      signal: current.controller.signal
    })
  }
  async function refresh() {
    if (currentSession()?.body) {
      observe(true)
      await nextTick()
      await query.refetch({ cancelRefetch: false })
    }
  }
  async function submit(
    build: (
      id: string,
      source: DataResult
    ) => Promise<ExportRequest | undefined>
  ) {
    const currentScope = toValue(scope),
      saved = currentSession()
    if (!currentScope || !saved || busy.value || active.value || receipt.value)
      return
    const current = {
      key: saved.key,
      scope: currentScope,
      controller: new AbortController()
    }
    intent.value = current
    diagnostic.value = undefined
    try {
      if (saved.body) {
        observe(true)
        await nextTick()
        const status = await query.refetch({ cancelRefetch: false })
        if (!stillCurrent(current) || status.isSuccess) return
        if (
          !(
            status.error instanceof ApiClientError &&
            status.error.kind === 'service' &&
            status.error.status === 404 &&
            status.error.code === 'RESOURCE_NOT_FOUND'
          )
        )
          throw status.error
      } else {
        const source = result.data.value
        if (!source || source.state !== 'completed') return
        const value = await build(crypto.randomUUID(), source)
        if (!stillCurrent(current) || !value) return
        const body = exportRequestSchema.parse(value)
        sessionStorage.setItem(current.key, JSON.stringify(body))
        session.value = { key: current.key, body, observing: false }
      }
      if (!sourceReady.value) return
      observe(false)
      await submitMutation.mutateAsync({
        workspaceId: currentScope.workspaceId,
        client: currentScope.client,
        body: structuredClone(toRaw(pendingBody.value!))
      })
    } catch (cause) {
      if (stillCurrent(current)) diagnostic.value = cause
    } finally {
      if (stillCurrent(current)) {
        observe(Boolean(pendingBody.value))
        intent.value = undefined
      }
    }
  }
  async function cancel() {
    const current = toValue(scope),
      saved = currentSession(),
      origin = key.value
    if (!current || !saved?.body || cancelMutation.isPending.value) return
    diagnostic.value = undefined
    try {
      await cancelMutation.mutateAsync({
        workspaceId: current.workspaceId,
        client: current.client,
        body: saved.body
      })
    } catch (cause) {
      if (key.value === origin) diagnostic.value = cause
    } finally {
      if (alive && key.value === origin) await refresh()
    }
  }
  function newExport() {
    const current = currentSession()
    if (!current || busy.value || active.value) return
    sessionStorage.removeItem(current.key)
    session.value = { key: current.key, observing: false }
    diagnostic.value = undefined
  }
  onScopeDispose(() => {
    alive = false
    intent.value?.controller.abort()
  })
  return {
    pendingBody,
    receipt,
    active,
    busy,
    error,
    source: result.data,
    sourceReady,
    requestId: computed(() => pendingBody.value?.request_id ?? ''),
    submit,
    cancel,
    refresh,
    newExport,
    choose
  }
}
