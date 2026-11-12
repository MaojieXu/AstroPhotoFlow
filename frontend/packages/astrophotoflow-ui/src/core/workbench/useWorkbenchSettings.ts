import {
  computed,
  onScopeDispose,
  ref,
  shallowRef,
  toRaw,
  toValue,
  watch
} from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { ApiClientError } from '../client'
import type { WorkbenchClient } from '../client'
import type {
  ConfigSave,
  ConfigState,
  ConfigValues,
  WorkbenchResult
} from '../contracts'
import {
  useWorkbenchConfiguration,
  useRestartObservation,
  transientRestartError,
  RestartObservationExpired
} from './queries'
import type { RestartObservation } from './queries'
import {
  useSaveWorkbenchConfiguration,
  useSelectWorkbenchDirectory,
  useRestartWorkbench
} from './mutations'

type Intent = {
  client: WorkbenchClient
  kind: 'saving' | 'selecting' | 'restarting'
  directory?: AbortController
}
export function useWorkbenchSettings(
  client: MaybeRefOrGetter<WorkbenchClient>,
  translate: (key: string) => string
) {
  const configurationQuery = useWorkbenchConfiguration(client)
  const saveMutation = useSaveWorkbenchConfiguration(),
    selectMutation = useSelectWorkbenchDirectory(),
    restartMutation = useRestartWorkbench()
  // Immutable edit basis: Query may receive a new state while this draft is dirty.
  const configuration = shallowRef<ConfigState>()
  const form = ref<ConfigValues>()
  const defaultWorkspace = ref(''),
    saved = ref(false),
    restartMessage = ref('')
  const actionError = shallowRef<unknown>()
  const intent = shallowRef<Intent>()
  const observation = shallowRef<RestartObservation>()
  const restartQuery = useRestartObservation(observation)
  let alive = true
  const hasUnsavedChanges = computed(() =>
    Boolean(
      configuration.value &&
      form.value &&
      (JSON.stringify(form.value) !==
        JSON.stringify(configuration.value.saved) ||
        defaultWorkspace.value !==
          (configuration.value.default_workspace ?? ''))
    )
  )
  const phase = computed(
    () =>
      intent.value?.kind ??
      (configurationQuery.isFetching.value ? 'loading' : 'ready')
  )
  const error = computed(
    () => actionError.value ?? configurationQuery.error.value
  )
  function adopt(current: ConfigState) {
    configuration.value = current
    form.value = structuredClone(toRaw(current.saved))
    defaultWorkspace.value = current.default_workspace ?? ''
  }
  const currentIntent = (value: Intent) =>
    alive && intent.value === value && toValue(client) === value.client
  function begin(kind: Intent['kind']) {
    if (!alive || intent.value || configurationQuery.isFetching.value) return
    const value: Intent = { client: toValue(client), kind }
    intent.value = value
    actionError.value = undefined
    return value
  }
  function end(value: Intent) {
    if (intent.value === value) intent.value = undefined
  }
  watch(hasUnsavedChanges, (changed) => {
    if (changed) saved.value = false
  })
  watch(
    [
      configurationQuery.data,
      configurationQuery.isFetching,
      configurationQuery.isFetchedAfterMount,
      configurationQuery.isSuccess
    ],
    ([state, fetching, verified, successful]) => {
      if (
        state &&
        !fetching &&
        verified &&
        successful &&
        !intent.value &&
        !hasUnsavedChanges.value
      )
        adopt(state)
    },
    { immediate: true }
  )
  watch(
    () => toValue(client),
    () => {
      intent.value?.directory?.abort()
      intent.value = undefined
      observation.value = undefined
      configuration.value = undefined
      form.value = undefined
      defaultWorkspace.value = ''
      actionError.value = undefined
      saved.value = false
      restartMessage.value = ''
      saveMutation.reset()
      selectMutation.reset()
      restartMutation.reset()
    },
    { flush: 'sync' }
  )
  onScopeDispose(() => {
    alive = false
    intent.value?.directory?.abort()
    observation.value = undefined
  })

  async function reload() {
    if (intent.value) return
    const original = toValue(client)
    actionError.value = undefined
    saved.value = false
    const result = await configurationQuery.refetch({ cancelRefetch: false })
    if (alive && toValue(client) === original && result.isSuccess)
      adopt(result.data)
  }
  async function save() {
    if (!configuration.value || !form.value) return
    const body: ConfigSave = {
      config_token: configuration.value.config_token,
      values: structuredClone(toRaw(form.value))
    }
    if (
      defaultWorkspace.value !== (configuration.value.default_workspace ?? '')
    ) {
      if (!defaultWorkspace.value.trim()) {
        actionError.value = new Error(translate('apfWorkbench.defaultRequired'))
        return
      }
      body.default_workspace = defaultWorkspace.value
    }
    const current = begin('saving')
    if (!current) return
    saved.value = false
    try {
      const state = await saveMutation.mutateAsync({
        client: current.client,
        body
      })
      if (currentIntent(current)) {
        adopt(state)
        saved.value = true
      }
    } catch (cause) {
      if (currentIntent(current)) actionError.value = cause
    } finally {
      end(current)
    }
  }
  async function chooseDirectory(target: 'default_workspace' | 'data_dir') {
    if (!form.value) return
    const current = begin('selecting')
    if (!current) return
    current.directory = new AbortController()
    try {
      const path =
        target === 'default_workspace'
          ? defaultWorkspace.value
          : form.value.data_dir
      const selected = await selectMutation.mutateAsync({
        client: current.client,
        path,
        signal: current.directory.signal
      })
      if (currentIntent(current) && selected !== null) {
        if (target === 'default_workspace') defaultWorkspace.value = selected
        else if (form.value) form.value.data_dir = selected
        saved.value = false
      }
    } catch (cause) {
      if (currentIntent(current)) actionError.value = cause
    } finally {
      end(current)
    }
  }
  async function terminal(current: Intent, result: WorkbenchResult) {
    if (!currentIntent(current)) return
    observation.value = undefined
    if (result.state !== 'completed') {
      actionError.value = new Error(
        [result.detail, ...result.blockers].filter(Boolean).join(' · ') ||
          translate('apfWorkbench.restartUnknown')
      )
      restartMessage.value = ''
      end(current)
      return
    }
    restartMessage.value = translate('apfWorkbench.restarted')
    const refreshed = await configurationQuery.refetch({ cancelRefetch: false })
    if (currentIntent(current) && refreshed.isSuccess) adopt(refreshed.data)
    end(current)
  }
  watch([restartQuery.data, restartQuery.error], ([result, cause]) => {
    const current = intent.value,
      target = observation.value
    if (
      !current ||
      current.kind !== 'restarting' ||
      !target ||
      !currentIntent(current)
    )
      return
    if (cause) {
      if (transientRestartError(cause)) return
      actionError.value =
        cause instanceof RestartObservationExpired
          ? new Error(translate('apfWorkbench.restartUnknown'))
          : cause
      restartMessage.value = ''
      observation.value = undefined
      end(current)
    } else if (result && result.state !== 'in_progress')
      void terminal(current, result)
  })
  async function restartWorkbench() {
    if (!configuration.value || hasUnsavedChanges.value) return
    const current = begin('restarting')
    if (!current) return
    const operationId = crypto.randomUUID()
    restartMessage.value = translate('apfWorkbench.restarting')
    try {
      let result: WorkbenchResult
      try {
        result = await restartMutation.mutateAsync({
          client: current.client,
          operationId
        })
      } catch (cause) {
        if (!transientRestartError(cause)) throw cause
        if (currentIntent(current))
          observation.value = {
            client: current.client,
            operationId,
            deadline: Date.now() + 300_000
          }
        return
      }
      if (!currentIntent(current)) return
      if (result.operation_id !== operationId)
        throw new ApiClientError(
          'Restart receipt does not match the requested operation',
          'contract'
        )
      if (result.state === 'in_progress')
        observation.value = {
          client: current.client,
          operationId,
          deadline: Date.now() + 300_000
        }
      else await terminal(current, result)
    } catch (cause) {
      if (currentIntent(current)) {
        actionError.value = cause
        restartMessage.value = ''
        end(current)
      }
    }
  }
  return {
    configuration,
    form,
    defaultWorkspace,
    saved,
    hasUnsavedChanges,
    phase,
    error,
    restartMessage,
    reload,
    save,
    chooseDirectory,
    restartWorkbench
  }
}
