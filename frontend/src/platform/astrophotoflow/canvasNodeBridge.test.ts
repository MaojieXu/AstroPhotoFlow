import { fromPartial } from '@total-typescript/shoehorn'
import type { NodeCapability, NodeParameter } from '@astrophotoflow/ui'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import { bundleCapabilities } from './bundleCatalog'
import { applyCanvasNodeEdit, validateNodeValue } from './canvasNodeBridge'
import type { CanvasGraphCommand } from './canvasContracts'

const host = vi.hoisted(() => ({ app: {} as Record<string, unknown>, add: vi.fn(), definitions: {} as Record<string, unknown> }))
vi.mock('@/scripts/appInstance', () => ({ useApp: () => host.app }))
vi.mock('@/services/litegraphService', () => ({ useLitegraphService: () => ({ addNodeOnGraph: host.add }) }))
vi.mock('@/stores/nodeDefStore', () => ({ useNodeDefStore: () => ({ nodeDefsByName: host.definitions }) }))

const type = 'APF_bundle_fixture'
const parameter: NodeParameter = { name: 'targetbg', kind: 'float', default: .25, minimum: 0, maximum: 1, step: null, choices: null, nullable: false, advanced: false }
let graph: LGraph
let source: LGraphNode
let target: LGraphNode
function command(edit: CanvasGraphCommand['request']['edit']): CanvasGraphCommand {
  return fromPartial<CanvasGraphCommand>({ request: { edit }, definition: bundleCapabilities.get(type)!.node })
}

beforeEach(() => {
  graph = new LGraph()
  source = new LGraphNode('Source')
  source.addOutput('science', 'APF_SCIENCE')
  target = new LGraphNode('Processing')
  target.comfyClass = type
  target.addInput('image', 'APF_SCIENCE')
  target.addWidget('number', 'targetbg', .25, vi.fn(() => {}))
  graph.add(source)
  graph.add(target)
  host.app = { canvas: { graph, read_only: false, selectOnly: false, emitBeforeChange: vi.fn(), emitAfterChange: vi.fn(), setDirty: vi.fn() } }
  host.definitions = { [type]: {} }
  bundleCapabilities.set(type, fromPartial<NodeCapability>({ node: { native_type: type, content_token: 'current', definition: { definition_id: '00000000-0000-4000-8000-000000000001', parameters: [parameter] } } }))
  host.add.mockImplementation(() => { const node = new LGraphNode('New'); node.addWidget('number', 'targetbg', .25, vi.fn(() => {})); graph.add(node); return node })
})

describe('bundle canvas edits', () => {
  it('adds a native node with validated parameters and reports its real ID', () => {
    const result = applyCanvasNodeEdit(command({ action: 'add_node', definition_id: '00000000-0000-4000-8000-000000000001', parameters: { targetbg: 0 } }))
    expect(graph.nodes.find(node => node.id === result.node_id)?.widgets?.[0].value).toBe(0)
    expect(host.add).toHaveBeenCalledOnce()
  })
  it('changes a widget through the native change lifecycle', () => {
    applyCanvasNodeEdit(command({ action: 'set_parameter', node_id: target.id, name: 'targetbg', value: .7 }))
    expect(target.widgets![0].value).toBe(.7)
    expect(target.widgets![0].callback).toHaveBeenCalled()
    expect(() => applyCanvasNodeEdit(command({ action: 'set_parameter', node_id: target.id, name: 'targetbg', value: 2 }))).toThrow()
    expect(target.widgets![0].value).toBe(.7)
  })
  it('connects compatible ports without silently replacing an existing connection', () => {
    const edit = command({ action: 'connect', source_node_id: source.id, source_port: 'science', target_node_id: target.id, target_port: 'image' })
    expect(applyCanvasNodeEdit(edit).link_id).toBe(target.inputs[0].link)
    expect(() => applyCanvasNodeEdit(edit)).toThrow('already connected')
  })
  it('accepts unrestricted negative clipping and rejects non-finite values', () => {
    expect(() => validateNodeValue({ ...parameter, minimum: null, maximum: null }, -100)).not.toThrow()
    expect(() => validateNodeValue(parameter, NaN)).toThrow()
    expect(() => validateNodeValue(undefined, 1)).toThrow()
  })

  it('deletes only the requested node and its links through the native change lifecycle', () => {
    source.connect(0, target, 0)
    const before = vi.fn()
    const after = vi.fn()
    host.app = { canvas: { graph, read_only: false, selectOnly: false, emitBeforeChange: before, emitAfterChange: after, setDirty: vi.fn() } }
    const result = applyCanvasNodeEdit(command({ action: 'delete_node', node_id: target.id }))
    expect(result.node_id).toBe(target.id)
    expect(graph.getNodeById(target.id)).toBeFalsy()
    expect(graph.getNodeById(source.id)).toBe(source)
    expect(source.outputs[0].links ?? []).toHaveLength(0)
    expect(graph.links.size).toBe(0)
    expect(before).toHaveBeenCalledOnce()
    expect(after).toHaveBeenCalledOnce()
  })

  it.each(['block_delete', 'ignore_remove'] as const)('respects native %s without changing the graph', (flag) => {
    target[flag] = true
    const before = graph.serialize()
    expect(() => applyCanvasNodeEdit(command({ action: 'delete_node', node_id: target.id }))).toThrow('cannot be deleted')
    expect(graph.serialize()).toEqual(before)
  })

  it('rejects a missing node without changing the graph', () => {
    const before = graph.serialize()
    expect(() => applyCanvasNodeEdit(command({ action: 'delete_node', node_id: 'missing' }))).toThrow('unavailable')
    expect(graph.serialize()).toEqual(before)
  })
})
