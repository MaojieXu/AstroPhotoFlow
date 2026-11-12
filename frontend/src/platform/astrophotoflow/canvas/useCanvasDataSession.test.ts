import { fromPartial } from '@total-typescript/shoehorn'
import { webcrypto } from 'node:crypto'
import { render, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, reactive, shallowReactive } from 'vue'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { LGraphCanvas } from '@/lib/litegraph/src/litegraph'
import type { ComfyApp } from '@/types/comfy'

import { serializeCanvasContent, useCanvasDataSession } from './session'
import type { CanvasCommand, CanvasEvent } from '../canvasContracts'

const mocks = vi.hoisted(() => ({ send: vi.fn<(event: CanvasEvent) => boolean>(), insert: vi.fn(), edit: vi.fn() }))
vi.mock('@/i18n', () => ({ t: (key: string) => key }))
vi.mock('@/scripts/api', () => ({ api: {
  sendCanvasEvent: mocks.send,
  addEventListener: (name: string, listener: EventListener) => events.addEventListener(name, listener),
  removeEventListener: (name: string, listener: EventListener) => events.removeEventListener(name, listener)
} }))
vi.mock('@/scripts/appInstance', () => ({ useApp: () => app }))
vi.mock('@/renderer/core/canvas/canvasStore', () => ({ useCanvasStore: () => canvasStore }))
vi.mock('@/platform/workflow/management/stores/workflowStore', () => ({ useWorkflowStore: () => workflows }))
vi.mock('./dataBridge', () => ({ insertPreparedCanvasData: mocks.insert }))
vi.mock('./nodeBridge', () => ({ applyCanvasNodeEdit: mocks.edit }))

let events: EventTarget
let app: ComfyApp
let canvasStore: { canvas: LGraphCanvas | null; isReadOnly: boolean }
let workflows: { activeWorkflow: { filename: string } | null; activeSubgraph: null }
let wrapper: ReturnType<typeof render>
const ids = { operation: '00000000-0000-4000-8000-000000000001', page: '00000000-0000-4000-8000-000000000002', asset: '00000000-0000-4000-8000-000000000003', version: '00000000-0000-4000-8000-000000000004' }

function lastState() {
  const value = mocks.send.mock.calls.map(([event]) => event).filter(event => event.action === 'state' && event.state !== null).at(-1)
  if (value?.action !== 'state' || !value.state) throw new Error('No published canvas')
  return value.state
}

function command(): Extract<CanvasCommand, { data: unknown }> {
  const state = lastState()
  return {
    request: { operation_id: ids.operation, page_id: ids.page, workflow_id: state.workflow_id, graph_id: state.graph_id, content_token: state.content_token, source: { entry_type: 'asset', id: ids.asset, asset_ids: null } },
    data: { native_type: 'APF_DATA_REFERENCE', title: 'Science', reference: { kind: 'asset', asset_id: ids.asset, selection: { kind: 'whole_file', hdu_index: null } } }
  }
}

beforeEach(async () => {
  vi.clearAllMocks()
  events = new EventTarget()
  const graph = new LGraph()
  const canvas = fromPartial<LGraphCanvas>({ graph, selectOnly: false, read_only: false })
  canvasStore = shallowReactive({ canvas, isReadOnly: false })
  workflows = reactive({ activeWorkflow: { filename: 'Active workflow' }, activeSubgraph: null })
  app = fromPartial<ComfyApp>({ canvas, get graph() { return canvas.graph?.rootGraph ?? graph }, isGraphReady: true })
  mocks.send.mockReturnValue(true)
  mocks.insert.mockImplementation(() => {
    graph.add(new LGraphNode('Data'))
    events.dispatchEvent(new CustomEvent('graphChanged'))
    return 9
  })
  mocks.edit.mockReturnValue({ node_id: 11, link_id: 7 })
  vi.stubGlobal('crypto', webcrypto)
  wrapper = render(defineComponent({ setup() { useCanvasDataSession(); return {} }, template: '<div />' }))
  await waitFor(() => expect(lastState().workflow_id).toBe(graph.id))
})

afterEach(() => {
  wrapper.unmount()
  vi.unstubAllGlobals()
})

describe('native canvas editing', () => {
  it('reads the current native graph without changing it', async () => {
    const current = lastState()
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: {
      request: { operation_id: ids.operation, page_id: ids.page,
        workflow_id: current.workflow_id, graph_id: current.graph_id,
        content_token: current.content_token, edit: { action: 'inspect' } },
      definition: null
    } }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: true, graph: expect.objectContaining({ nodes: [] }) }) }))
    expect(mocks.insert).not.toHaveBeenCalled()
    expect(mocks.edit).not.toHaveBeenCalled()
    expect(app.graph.nodes).toHaveLength(0)
  })

  it('connects nodes with current target and content without a handoff', async () => {
    const current = lastState()
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: {
      request: { operation_id: ids.operation, page_id: ids.page,
        workflow_id: current.workflow_id, graph_id: current.graph_id,
        content_token: current.content_token,
        edit: { action: 'connect', source_node_id: 10, source_port: 'science', target_node_id: 11, target_port: 'image' } }, definition: null
    } }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: true, node_id: 11, link_id: 7 }) }))
    expect(mocks.edit).toHaveBeenCalledWith(expect.objectContaining({ request: expect.objectContaining({
      edit: { action: 'connect', source_node_id: 10, source_port: 'science', target_node_id: 11, target_port: 'image' }
    }) }))
  })
  it('rejects a stale request after publishing a manual change', async () => {
    const value = command()
    app.graph.add(new LGraphNode('Manual change'))
    events.dispatchEvent(new CustomEvent('graphChanged'))
    await waitFor(() => expect(lastState().content_token).not.toBe(value.request.content_token))
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false, error: expect.objectContaining({ code: 'CANVAS_TARGET_CHANGED' }) }) }))
    expect(mocks.insert).not.toHaveBeenCalled()
  })

  it('reports actual node creation without a handoff', async () => {
    const value = command()
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: true }) }))
    expect(mocks.insert).toHaveBeenCalledWith(value.data)
    expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ operation_id: ids.operation, applied: true, node_id: 9 }) })
  })

  it('rejects late commands after graph content changes even before the change event', async () => {
    const value = command()
    app.canvas.graph?.add(new LGraphNode('Manual change'))
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false }) }))
    expect(mocks.insert).not.toHaveBeenCalled()
    expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false, node_id: null }) })
  })

  it('rejects the old target when switching workflows', async () => {
    const value = command()
    const graph = new LGraph()
    app.canvas.graph = graph
    workflows.activeWorkflow = { filename: 'Another workflow' }
    await waitFor(() => expect(lastState().workflow_id).toBe(graph.id))
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false }) }))
    expect(mocks.insert).not.toHaveBeenCalled()
  })

  it('rejects a request while the canvas is offline', async () => {
    const value = command()
    canvasStore.canvas = null
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: value }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: false }) }))
    expect(mocks.insert).not.toHaveBeenCalled()
  })

  it('publishes the current target after reconnect without a handoff', async () => {
    mocks.send.mockClear()
    events.dispatchEvent(new CustomEvent('reconnected'))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'state', state: expect.objectContaining({ workflow_id: app.graph.id }) }))
    events.dispatchEvent(new CustomEvent('apf.canvas_command', { detail: command() }))
    await waitFor(() => expect(mocks.send).toHaveBeenCalledWith({ action: 'result', result: expect.objectContaining({ applied: true }) }))
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
