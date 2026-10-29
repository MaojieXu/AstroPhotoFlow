import { fromPartial } from '@total-typescript/shoehorn'
import { render, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive, shallowReactive } from 'vue'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { LGraphCanvas } from '@/lib/litegraph/src/litegraph'
import type { ComfyApp } from '@/types/comfy'

import { canvasDataAgentAllowed, serializeCanvasContent, toggleCanvasDataControl, useCanvasDataSession } from './useCanvasDataSession'
import type { CanvasCommand, CanvasEvent } from './canvasContracts'

const mocks = vi.hoisted(() => ({ send: vi.fn<(event: CanvasEvent) => boolean>(), insert: vi.fn(), error: vi.fn() }))
vi.mock('@/components/ui/toast/toastStore', () => ({ useToast: () => ({ error: mocks.error }) }))
vi.mock('@/i18n', () => ({ t: (key: string) => key }))
vi.mock('@/scripts/api', () => ({ api: {
  sendCanvasEvent: mocks.send,
  addEventListener: (name: string, listener: EventListener) => events.addEventListener(name, listener),
  removeEventListener: (name: string, listener: EventListener) => events.removeEventListener(name, listener)
} }))
vi.mock('@/scripts/appInstance', () => ({ useApp: () => app }))
vi.mock('@/renderer/core/canvas/canvasStore', () => ({ useCanvasStore: () => canvasStore }))
vi.mock('@/platform/workflow/management/stores/workflowStore', () => ({ useWorkflowStore: () => workflows }))
vi.mock('./canvasDataBridge', () => ({ insertPreparedCanvasData: mocks.insert }))

let events: EventTarget
let app: ComfyApp
let canvasStore: { canvas: LGraphCanvas | null; isReadOnly: boolean }
let workflows: { activeWorkflow: { filename: string } | null; activeSubgraph: null }
let wrapper: ReturnType<typeof render>
const ids = { operation: '00000000-0000-4000-8000-000000000001', page: '00000000-0000-4000-8000-000000000002', asset: '00000000-0000-4000-8000-000000000003', version: '00000000-0000-4000-8000-000000000004', control: '00000000-0000-4000-8000-000000000005' }

function lastState() {
  const value = mocks.send.mock.calls.map(([event]) => event).filter(event => event.action === 'state' && event.state !== null).at(-1)
  if (value?.action !== 'state' || !value.state) throw new Error('No published canvas')
  return value.state
}

function command(): Extract<CanvasCommand, { data: unknown }> {
  const state = lastState()
  return {
    request: { operation_id: ids.operation, page_id: ids.page, workflow_id: state.workflow_id, graph_id: state.graph_id, content_token: state.content_token, control_token: state.control_token ?? '', source: { entry_type: 'asset', id: ids.asset, version_id: ids.version, member_indexes: null } },
    data: { native_type: 'APF_DATA_REFERENCE', title: 'Fixed science', reference: { kind: 'asset_version', asset_version_id: ids.version, selection: { kind: 'whole_file', hdu_index: null } } }
  }
}

beforeEach(async () => {
  vi.clearAllMocks()
  events = new EventTarget()
  const graph = new LGraph()
  const canvas = fromPartial<LGraphCanvas>({ graph, selectOnly: false, read_only: false })
  canvasStore = shallowReactive({ canvas, isReadOnly: false })
  workflows = reactive({ activeWorkflow: { filename: 'Active workflow' }, activeSubgraph: null })
  app = fromPartial<ComfyApp>({ canvas, graph, isGraphReady: true })
  mocks.send.mockReturnValue(true)
  mocks.insert.mockImplementation(() => {
    graph.add(new LGraphNode('Data'))
    events.dispatchEvent(new CustomEvent('graphChanged'))
    return 9
  })
  vi.stubGlobal('crypto', { randomUUID: () => ids.control, subtle: { digest: async () => new ArrayBuffer(32) } })
  wrapper = render(defineComponent({ setup() { useCanvasDataSession(); return {} }, template: '<div />' }))
  await waitFor(() => expect(lastState().control_token).toBeNull())
})

afterEach(() => {
  wrapper.unmount()
  vi.unstubAllGlobals()
})

describe('native data canvas control', () => {
  it('reads the current native graph without taking control', async () => {
    const current = lastState()
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: {
      request: { operation_id: ids.operation, page_id: ids.page,
        workflow_id: current.workflow_id, graph_id: current.graph_id,
        content_token: current.content_token, control_token: null, edit: { action: 'inspect' } },
      definition: null
    } }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: true, graph: expect.objectContaining({ nodes: [] }) }) }))
    expect(canvasDataAgentAllowed.value).toBe(false)
    expect(mocks.insert).not.toHaveBeenCalled()
  })

  it('rejects node editing without explicit user handoff', async () => {
    const current = lastState()
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: {
      request: { operation_id: ids.operation, page_id: ids.page,
        workflow_id: current.workflow_id, graph_id: current.graph_id,
        content_token: current.content_token, control_token: null,
        edit: { action: 'set_parameter', node_id: 9, name: 'targetbg', value: .4 } }, definition: null
    } }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false }) }))
    expect(canvasDataAgentAllowed.value).toBe(false)
  })
  it('requires explicit handoff and revokes on manual changes or reconnect', async () => {
    expect(lastState().control_token).toBeNull()
    toggleCanvasDataControl()
    await waitFor(() => expect(lastState().control_token).toBe(ids.control))
    expect(lastState().control_token).toBe(ids.control)
    events.dispatchEvent(new CustomEvent('graphChanged'))
    await waitFor(() => expect(lastState().control_token).toBeNull())
    expect(canvasDataAgentAllowed.value).toBe(false)
    toggleCanvasDataControl()
    await waitFor(() => expect(lastState().control_token).toBe(ids.control))
    events.dispatchEvent(new CustomEvent('reconnected'))
    await waitFor(() => expect(lastState().control_token).toBeNull())
    expect(lastState().control_token).toBeNull()
  })

  it('reports actual node creation and keeps control for its own graph change', async () => {
    toggleCanvasDataControl()
    await waitFor(() => expect(lastState().control_token).toBe(ids.control))
    const value = command()
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: true }) }))
    expect(mocks.insert).toHaveBeenCalledWith(value.data)
    expect(canvasDataAgentAllowed.value).toBe(true)
    expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ operation_id: ids.operation, applied: true, node_id: 9 }) })
  })

  it('rejects late commands after graph content changes even before the change event', async () => {
    toggleCanvasDataControl()
    await waitFor(() => expect(lastState().control_token).toBe(ids.control))
    const value = command()
    app.canvas.graph?.add(new LGraphNode('Manual change'))
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false }) }))
    expect(mocks.insert).not.toHaveBeenCalled()
    expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false, node_id: null }) })
  })

  it('revokes control when switching workflows', async () => {
    toggleCanvasDataControl()
    await waitFor(() => expect(lastState().control_token).toBe(ids.control))
    workflows.activeWorkflow = { filename: 'Another workflow' }
    expect(canvasDataAgentAllowed.value).toBe(false)
    await waitFor(() => expect(lastState().control_token).toBeNull())
    expect(lastState().control_token).toBeNull()
  })

  it('excludes viewport transforms from the content token but keeps node layout', () => {
    const graph = new LGraph()
    const node = new LGraphNode('Frame')
    graph.add(node)
    const before = serializeCanvasContent(graph)
    graph.extra.ds = { scale: 2, offset: [10, 20] }
    expect(serializeCanvasContent(graph)).toBe(before)
    node.pos = [100, 200]
    expect(serializeCanvasContent(graph)).not.toBe(before)
  })
})
