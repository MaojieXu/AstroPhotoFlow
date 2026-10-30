import { onBeforeUnmount, onMounted, watch } from 'vue'

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
import { applyCanvasNodeEdit } from './canvasNodeBridge'

export function serializeCanvasContent(graph: LGraph | Subgraph) {
  const snapshot = graph.serialize()
  return JSON.stringify({ ...snapshot, revision: undefined, extra: { ...snapshot.extra, ds: undefined } })
}

export function useCanvasDataSession() {
  const canvasStore = useCanvasStore()
  const workflows = useWorkflowStore()
  let state: CanvasPage | null = null
  let applying = false
  let generation = 0
  let serialized = ''

  async function publish() {
    const current = ++generation
    const app = useApp()
    const canvas = canvasStore.canvas
    const graph = canvas?.graph
    if (!app.isGraphReady || !canvas || !graph || !workflows.activeWorkflow || isSelectOnly(canvas)) {
      state = null
      api.sendCanvasEvent({ action: 'state', state: null })
      return
    }
    const text = serializeCanvasContent(graph)
    const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
    if (current !== generation || canvasStore.canvas !== canvas || canvas.graph !== graph) return
    const parsed = canvasPageSchema.safeParse({
      workflow_id: app.graph.id, graph_id: graph.id,
      title: workflows.activeWorkflow.filename,
      content_token: Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('')
    })
    if (!parsed.success) {
      state = null
      api.sendCanvasEvent({ action: 'state', state: null })
      return
    }
    serialized = text
    state = parsed.data
    if (!api.sendCanvasEvent({ action: 'state', state })) state = null
  }

  function refreshState() {
    state = null
    void publish()
  }

  function changed() {
    if (!applying) refreshState()
  }

  function connectionChanged() {
    refreshState()
  }

  async function apply(event: CustomEvent<unknown>) {
    const parsed = canvasCommandSchema.safeParse(event.detail)
    if (!parsed.success) return
    const command = parsed.data
    const { request } = command
    const inspecting = 'edit' in request && request.edit.action === 'inspect'
    let nodeId: string | number | null = null
    let error = null
    let linkId: string | number | null = null
    let snapshot = null
    let applied: boolean | null = false
    try {
      const app = useApp()
      const current = state
      if (!current || request.workflow_id !== current.workflow_id || request.graph_id !== current.graph_id || request.content_token !== current.content_token || app.graph.id !== request.workflow_id || app.canvas.graph?.id !== request.graph_id || serializeCanvasContent(app.canvas.graph) !== serialized || applying) {
        throw new Error(t('astrophotoflow.canvasChanged'))
      }
      applying = true
      if ('data' in command) nodeId = insertPreparedCanvasData(command.data)
      else if (inspecting) snapshot = JSON.parse(serializeCanvasContent(app.canvas.graph))
      else {
        const result = applyCanvasNodeEdit(command)
        nodeId = result.node_id
        linkId = result.link_id
      }
      applied = true
    } catch (cause) {
      const graph = useApp().canvas.graph
      if (applying && graph && serializeCanvasContent(graph) !== serialized) applied = null
      error = { code: applied === null ? 'CANVAS_RESULT_UNKNOWN' : 'CANVAS_TARGET_CHANGED', message: cause instanceof Error ? cause.message : String(cause), fields: [] }
    } finally {
      applying = false
    }
    await publish()
    api.sendCanvasEvent({ action: 'result', result: {
      operation_id: request.operation_id, page_id: request.page_id,
      workflow_id: request.workflow_id, graph_id: request.graph_id,
      applied, node_id: nodeId, link_id: linkId, graph: snapshot,
      content_token: state?.workflow_id === request.workflow_id && state.graph_id === request.graph_id ? state.content_token : null, error
    } })
  }

  watch(() => [canvasStore.canvas, workflows.activeWorkflow, workflows.activeSubgraph, canvasStore.isReadOnly], refreshState, { flush: 'sync' })

  onMounted(() => {
    api.addEventListener('graphChanged', changed)
    api.addEventListener('reconnecting', connectionChanged)
    api.addEventListener('reconnected', connectionChanged)
    api.addEventListener('feature_flags', connectionChanged)
    api.addEventListener('apf.canvas_command', apply)
    void publish()
  })
  onBeforeUnmount(() => {
    generation++
    state = null
    api.sendCanvasEvent({ action: 'state', state: null })
    api.removeEventListener('graphChanged', changed)
    api.removeEventListener('reconnecting', connectionChanged)
    api.removeEventListener('reconnected', connectionChanged)
    api.removeEventListener('feature_flags', connectionChanged)
    api.removeEventListener('apf.canvas_command', apply)
  })
}
