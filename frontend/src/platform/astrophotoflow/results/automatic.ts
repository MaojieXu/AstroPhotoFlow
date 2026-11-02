import { onBeforeUnmount, onMounted, shallowReactive, watch } from 'vue'
import { softwareCallResultSchema } from '@astrophotoflow/ui'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { useWorkflowStore } from '@/platform/workflow/management/stores/workflowStore'
import type { ComfyApiWorkflow } from '@/platform/workflow/validation/schemas/workflowSchema'
import { api } from '@/scripts/api'
import { useApp } from '@/scripts/appInstance'
import { useExecutionStore } from '@/stores/executionStore'
import { useQueuePendingTaskCountStore } from '@/stores/queueStore'
import { tryNormalizeNodeExecutionId } from '@/types/nodeIdentification'
import { getExecutionIdByNode, getNodeByExecutionId } from '@/utils/graphTraversalUtil'

import { automaticResultPlan } from './plan'
import type { AutomaticNodePolicy } from './plan'
import { bundleCapabilities } from '../sidebar/bundleCatalog'

type ResultState = {
  signature: string
  submitted?: string
  phase: 'waiting' | 'queued' | 'running' | 'completed' | 'failed' | 'manual' | 'unavailable' | 'input' | 'cycle' | 'paused'
  error?: string
}
export const automaticResultStates = shallowReactive(new Map<string, ResultState>())
export function automaticResultState(node: LGraphNode) {
  const root = node.graph?.rootGraph
  const id = root && getExecutionIdByNode(root, node)
  return id ? automaticResultStates.get(`${root?.id}:${id}`) : undefined
}

export function setAutomaticResult(node: LGraphNode, enabled: boolean) {
  node.graph?.beforeChange()
  node.properties.apfAutomaticResult = enabled
  node.graph?.afterChange()
  if (enabled) retryAutomaticResult(node)
  else api.dispatchCustomEvent('graphChanged', null)
}

export function retryAutomaticResult(node: LGraphNode) {
  const root = node.graph?.rootGraph
  const id = root && getExecutionIdByNode(root, node)
  const key = `${root?.id}:${id}`
  const state = automaticResultStates.get(key)
  if (state) automaticResultStates.set(key, { ...state, submitted: undefined, phase: 'waiting', error: undefined })
  api.dispatchCustomEvent('graphChanged', null)
}

export function useAutomaticResults() {
  const app = useApp()
  const workflows = useWorkflowStore()
  const execution = useExecutionStore()
  const queue = useQueuePendingTaskCountStore()
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0
  let submitting = false
  let obsolete = false
  let active: { promptId: string; owner: string; signatures: Record<string, string>; completed: Set<string> } | undefined
  let mounted = false
  let reconciling = false

  function policies(prompt: ComfyApiWorkflow): Record<string, AutomaticNodePolicy> {
    return Object.fromEntries(Object.entries(prompt).map(([id, value]) => {
      const node = getNodeByExecutionId(app.rootGraph, id)
      const capability = bundleCapabilities.get(value.class_type)
      const source = ['APF_DATA_REFERENCE', 'APF_FILE_REFERENCE'].includes(value.class_type)
      const enabled = node?.properties.apfAutomaticResult !== false
      return [id, { allowed: source || !!capability?.automatic_result_preview && enabled,
        enabled: !!capability?.automatic_result_preview && enabled,
        available: source || !!capability?.available,
        identity: capability ? [capability.node.content_token, capability.operation?.content_token, capability.implementation_token, capability.development_source?.fingerprint] : null,
        required: source ? (['science', 'images'].some(name => value.inputs[name] !== undefined) ? [] : ['reference']) : capability?.operation?.inputs.filter(input => input.required).map(input => capability.node.definition.execution.inputs[input.name] ?? input.name) ?? [] }]
    }))
  }

  function changed() {
    if (!mounted) return
    generation++
    clearTimeout(timer)
    timer = setTimeout(() => void refresh(), 500)
  }

  async function refresh() {
    if (!mounted || !app.isGraphReady) return
    const current = generation
    const owner = app.rootGraph.id
    let ownsSubmission = false
    try {
      const data = await app.graphToPrompt(app.rootGraph)
      const rules = policies(data.output)
      const plan = await automaticResultPlan(data.output, rules)
      if (current !== generation || owner !== app.rootGraph.id || !mounted) return
      for (const id of Object.keys(data.output)) {
        if (!bundleCapabilities.get(data.output[id].class_type)) continue
        const key = `${owner}:${id}`
        const old = automaticResultStates.get(key)
        const capability = bundleCapabilities.get(data.output[id].class_type)
        const node = getNodeByExecutionId(app.rootGraph, id)
        const paused = capability?.automatic_result_preview && node?.properties.apfAutomaticResult === false
        const phase = paused ? 'paused' : plan.blocked[id] ?? (old?.signature === plan.signatures[id] ? old.phase : 'waiting')
        automaticResultStates.set(key, { ...old, signature: plan.signatures[id], phase })
      }
      if (active) {
        await reconcileActive()
        return
      }
      if (submitting || !execution.isIdle || queue.count > 0) return
      const changedIds = plan.eligible.filter(id => automaticResultStates.get(`${owner}:${id}`)?.submitted !== plan.signatures[id])
      const targets = changedIds.filter(id => !changedIds.some(other => other !== id && plan.ancestors[other].has(id)))
      if (!targets.length) return
      const required = new Set(targets.flatMap(id => [id, ...plan.ancestors[id]]))
      const signatures = Object.fromEntries([...required].map(id => [id, plan.signatures[id]]))
      submitting = true
      ownsSubmission = true
      obsolete = false
      for (const id of required) {
        const key = `${owner}:${id}`
        const old = automaticResultStates.get(key)
        if (old) automaticResultStates.set(key, { ...old, submitted: signatures[id], phase: 'queued', error: undefined })
      }
      let receivedReceipt = false
      await app.queuePrompt(0, 1, {
        queueNodeIds: targets.flatMap(id => { const value = tryNormalizeNodeExecutionId(id); return value ? [value] : [] }),
        intent: { trigger_source: 'auto_queue' },
        automaticResult: { targets, signatures,
          isCurrent: async prompt => {
            if (!mounted || owner !== app.rootGraph.id) { obsolete = true; return false }
            const latestData = await app.graphToPrompt(app.rootGraph)
            const latest = await automaticResultPlan(latestData.output, policies(latestData.output))
            const queued = await automaticResultPlan(prompt, policies(prompt))
            const matches = owner === app.rootGraph.id && targets.every(id => latest.eligible.includes(id)) && Object.entries(signatures).every(([id, value]) => latest.signatures[id] === value && queued.signatures[id] === value)
            obsolete = !matches
            return matches
          },
          queued: promptId => { receivedReceipt = true; active = { promptId, owner, signatures, completed: new Set() } }
        }
      })
      if (!receivedReceipt) {
        for (const id of required) {
          const key = `${owner}:${id}`
          const old = automaticResultStates.get(key)
          if (old) automaticResultStates.set(key, { ...old, submitted: obsolete ? undefined : old.submitted, phase: obsolete ? 'waiting' : 'failed' })
        }
      }
    } catch (cause) {
      for (const [key, value] of automaticResultStates) {
        if (key.startsWith(`${owner}:`) && value.phase === 'queued') automaticResultStates.set(key, { ...value, phase: 'failed', error: cause instanceof Error ? cause.message : String(cause) })
      }
    } finally {
      if (ownsSubmission) {
        submitting = false
        if (obsolete) { obsolete = false; changed() }
      }
    }
  }

  async function reconcileActive() {
    if (!active || reconciling || !execution.isIdle) return
    const pending = active
    reconciling = true
    try {
      const items = await api.getQueue({ throwOnError: true })
      if (active !== pending || [...items.Running, ...items.Pending].some(item => item.id === pending.promptId)) return
      const response = await api.fetchApi(`/history/${encodeURIComponent(pending.promptId)}`)
      if (!response.ok || active !== pending) return
      const history = await response.json()
      if (active !== pending) return
      const completed = history[pending.promptId]?.status?.status_str === 'success'
      finished(new CustomEvent(completed ? 'execution_success' : 'execution_interrupted', { detail: { prompt_id: pending.promptId } }))
    } catch {
      // Unknown queue state retains ownership until a later native status update.
    } finally {
      reconciling = false
    }
  }

  function started(event: CustomEvent<{ prompt_id: string }>) {
    if (event.detail.prompt_id !== active?.promptId) return
    for (const id of Object.keys(active.signatures)) {
      const key = `${active.owner}:${id}`
      const state = automaticResultStates.get(key)
      if (state) automaticResultStates.set(key, { ...state, phase: 'running' })
    }
  }
  function finished(event: CustomEvent<{ prompt_id: string; exception_message?: string }>) {
    if (event.detail.prompt_id !== active?.promptId) return
    for (const [id, signature] of Object.entries(active.signatures)) {
      const key = `${active.owner}:${id}`
      const state = automaticResultStates.get(key)
      if (state) {
        const completed = event.type === 'execution_success' || active.completed.has(id)
        automaticResultStates.set(key, { ...state, phase: signature !== state.signature ? 'waiting' : completed ? 'completed' : 'failed', error: completed ? undefined : event.detail.exception_message })
      }
    }
    active = undefined
    changed()
  }
  function executed(event: CustomEvent<{ output: Record<string, unknown> }>) {
    const values = event.detail.output.apf_result
    if (!Array.isArray(values) || !active) return
    const parsed = softwareCallResultSchema.safeParse(values.at(-1))
    if (!parsed.success || parsed.data.prompt_id !== active.promptId || parsed.data.workflow_id !== active.owner || parsed.data.calculation_signature !== active.signatures[parsed.data.node_id]) return
    active.completed.add(parsed.data.node_id)
    const key = `${active.owner}:${parsed.data.node_id}`
    const state = automaticResultStates.get(key)
    if (state) automaticResultStates.set(key, { ...state, phase: state.signature === parsed.data.calculation_signature ? 'completed' : 'waiting', error: undefined })
  }

  watch(() => [workflows.activeWorkflow, ...bundleCapabilities.values()], changed)
  watch(() => [execution.isIdle, queue.count], changed)
  onMounted(() => {
    mounted = true
    api.addEventListener('status', changed)
    api.addEventListener('graphChanged', changed)
    api.addEventListener('execution_start', started)
    api.addEventListener('execution_success', finished)
    api.addEventListener('execution_error', finished)
    api.addEventListener('execution_interrupted', finished)
    api.addEventListener('executed', executed)
    changed()
  })
  onBeforeUnmount(() => {
    mounted = false
    generation++
    clearTimeout(timer)
    api.removeEventListener('status', changed)
    api.removeEventListener('graphChanged', changed)
    api.removeEventListener('execution_start', started)
    api.removeEventListener('execution_success', finished)
    api.removeEventListener('execution_error', finished)
    api.removeEventListener('execution_interrupted', finished)
    api.removeEventListener('executed', executed)
  })
}
