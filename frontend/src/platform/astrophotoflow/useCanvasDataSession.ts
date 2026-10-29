import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { useToast } from '@/components/ui/toast/toastStore'
import { t } from '@/i18n'
import type { LGraph, Subgraph } from '@/lib/litegraph/src/litegraph'
import { useWorkflowStore } from '@/platform/workflow/management/stores/workflowStore'
import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import { api } from '@/scripts/api'
import { useApp } from '@/scripts/appInstance'
import { isSelectOnly } from '@/utils/litegraphUtil'

import { canvasCommandSchema, canvasPageSchema } from './canvasContracts'
import type { CanvasPage } from './canvasContracts'
import { insertPreparedCanvasData } from './canvasDataBridge'

export const canvasDataAgentAllowed = ref(false)
let toggleControl: (() => void) | undefined

export function toggleCanvasDataControl() {
  toggleControl?.()
}

export function serializeCanvasContent(graph: LGraph | Subgraph) {
  const snapshot = graph.serialize()
  return JSON.stringify({ ...snapshot, revision: undefined, extra: { ...snapshot.extra, ds: undefined } })
}

export function useCanvasDataSession() {
  const canvasStore = useCanvasStore()
  const workflows = useWorkflowStore()
  let state: CanvasPage | null = null
  let controlToken: string | null = null
  let applying = false
  let generation = 0
  let serialized = ''

  function clearControl() {
    controlToken = null
    canvasDataAgentAllowed.value = false
    state = null
  }

  async function publish() {
    const current = ++generation
    const app = useApp()
    const canvas = canvasStore.canvas
    const graph = canvas?.graph
    if (!app.isGraphReady || !canvas || !graph || !workflows.activeWorkflow || isSelectOnly(canvas)) {
      clearControl()
      api.sendCanvasEvent({ action: 'state', state: null })
      return
    }
    const text = serializeCanvasContent(graph)
    const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
    if (current !== generation || canvasStore.canvas !== canvas || canvas.graph !== graph) return
    const parsed = canvasPageSchema.safeParse({
      workflow_id: app.graph.id, graph_id: graph.id,
      title: workflows.activeWorkflow.filename,
      content_token: Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join(''),
      control_token: controlToken
    })
    if (!parsed.success) {
      clearControl()
      api.sendCanvasEvent({ action: 'state', state: null })
      return
    }
    serialized = text
    state = parsed.data
    if (!api.sendCanvasEvent({ action: 'state', state })) clearControl()
  }

  function revoke() {
    clearControl()
    void publish()
  }

  function changed() {
    if (!applying) revoke()
  }

  function connectionChanged() {
    revoke()
  }

  async function apply(event: CustomEvent<unknown>) {
    const parsed = canvasCommandSchema.safeParse(event.detail)
    if (!parsed.success) return
    const { request, data } = parsed.data
    let nodeId: string | number | null = null
    let error = null
    try {
      const app = useApp()
      const current = state
      if (!current || !controlToken || request.control_token !== controlToken || request.workflow_id !== current.workflow_id || request.graph_id !== current.graph_id || request.content_token !== current.content_token || app.graph.id !== request.workflow_id || app.canvas.graph?.id !== request.graph_id || serializeCanvasContent(app.canvas.graph) !== serialized || applying) {
        throw new Error(t('astrophotoflow.canvasChanged'))
      }
      applying = true
      nodeId = insertPreparedCanvasData(data)
    } catch (cause) {
      error = { code: 'CANVAS_TARGET_CHANGED', message: cause instanceof Error ? cause.message : String(cause), fields: [] }
    } finally {
      applying = false
    }
    await publish()
    api.sendCanvasEvent({ action: 'result', result: {
      operation_id: request.operation_id, page_id: request.page_id,
      workflow_id: request.workflow_id, graph_id: request.graph_id,
      applied: nodeId !== null, node_id: nodeId, error
    } })
  }

  watch(() => [canvasStore.canvas, workflows.activeWorkflow, workflows.activeSubgraph, canvasStore.isReadOnly], revoke, { flush: 'sync' })

  onMounted(() => {
    toggleControl = () => {
      if (canvasDataAgentAllowed.value) revoke()
      else {
        const canvas = canvasStore.canvas
        if (!canvas?.graph || !workflows.activeWorkflow || isSelectOnly(canvas)) {
          useToast().error(t('astrophotoflow.canvasUnavailable'))
          return
        }
        controlToken = crypto.randomUUID()
        canvasDataAgentAllowed.value = true
        void publish()
      }
    }
    api.addEventListener('graphChanged', changed)
    api.addEventListener('reconnecting', connectionChanged)
    api.addEventListener('reconnected', connectionChanged)
    api.addEventListener('feature_flags', connectionChanged)
    api.addEventListener('apf.canvas_command', apply)
    void publish()
  })
  onBeforeUnmount(() => {
    generation++
    clearControl()
    api.sendCanvasEvent({ action: 'state', state: null })
    toggleControl = undefined
    api.removeEventListener('graphChanged', changed)
    api.removeEventListener('reconnecting', connectionChanged)
    api.removeEventListener('reconnected', connectionChanged)
    api.removeEventListener('feature_flags', connectionChanged)
    api.removeEventListener('apf.canvas_command', apply)
  })
}
