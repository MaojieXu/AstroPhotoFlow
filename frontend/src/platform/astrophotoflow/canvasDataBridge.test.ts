import { fromPartial } from '@total-typescript/shoehorn'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CanvasData, CanvasDataRequest } from '@astrophotoflow/ui'
import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { LGraphCanvas } from '@/lib/litegraph/src/litegraph'
import type { ComfyNodeDefImpl } from '@/stores/nodeDefStore'
import type { ComfyApp } from '@/types/comfy'

import { addLibraryDataToCanvas } from './canvasDataBridge'

const mocks = vi.hoisted(() => ({ prepare: vi.fn(), add: vi.fn(), toast: vi.fn() }))
vi.mock('@astrophotoflow/ui', () => ({ createCanvasDataClient: () => ({ prepare: mocks.prepare }) }))
vi.mock('@/components/ui/toast/toastStore', () => ({ useToast: () => ({ error: mocks.toast }) }))
vi.mock('@/i18n', () => ({ t: (key: string) => key }))
vi.mock('@/scripts/appInstance', () => ({ useApp: () => app }))
vi.mock('@/platform/workflow/management/stores/workflowStore', () => ({ useWorkflowStore: () => workflows }))
vi.mock('@/stores/nodeDefStore', () => ({ useNodeDefStore: () => definitions }))
vi.mock('@/services/litegraphService', () => ({ useLitegraphService: () => ({ addNodeOnGraph: mocks.add }) }))

let app: ComfyApp
let graph: LGraph
const workflows = { activeWorkflow: { filename: 'Test workflow' } }
const definitions = { nodeDefsByName: { APF_DATA_REFERENCE: fromPartial<ComfyNodeDefImpl>({ name: 'APF_DATA_REFERENCE' }) } }
const source: CanvasDataRequest = { entry_type: 'asset', id: '00000000-0000-4000-8000-000000000001', version_id: '00000000-0000-4000-8000-000000000002' }
const prepared: CanvasData = { native_type: 'APF_DATA_REFERENCE', title: 'Science', reference: { kind: 'asset_version', asset_version_id: source.version_id, selection: { kind: 'whole_file' } } }

beforeEach(() => {
  vi.clearAllMocks()
  graph = new LGraph()
  const canvas = fromPartial<LGraphCanvas>({ graph, selectOnly: false, read_only: false, selectNodes: vi.fn(), setDirty: vi.fn(), emitBeforeChange: vi.fn(), emitAfterChange: vi.fn() })
  app = fromPartial<ComfyApp>({ canvas, graph, isGraphReady: true })
  mocks.prepare.mockResolvedValue(prepared)
  mocks.add.mockImplementation((_definition, options) => {
    const node = new LGraphNode(options.title)
    node.addWidget('text', 'reference', '', () => {})
    graph.add(node)
    return node
  })
})

describe('library canvas insertion', () => {
  it('uses the native node service and one undo transaction at the requested drop position', async () => {
    const before = vi.spyOn(graph, 'beforeChange')
    const after = vi.spyOn(graph, 'afterChange')
    const id = await addLibraryDataToCanvas(source, [120, 80])
    expect(id).not.toBeNull()
    expect(mocks.add).toHaveBeenCalledWith(definitions.nodeDefsByName.APF_DATA_REFERENCE, { pos: [120, 80], title: 'Science' })
    expect(graph.nodes[0]?.widgets?.[0]?.value).toBe(JSON.stringify(prepared.reference))
    expect(before).toHaveBeenCalledTimes(1)
    expect(after).toHaveBeenCalledTimes(1)
    expect(app.canvas.emitBeforeChange).toHaveBeenCalledTimes(1)
    expect(app.canvas.emitAfterChange).toHaveBeenCalledTimes(1)
  })

  it('does not insert into a replacement graph after asynchronous preparation', async () => {
    mocks.prepare.mockImplementation(async () => {
      app.canvas.graph = new LGraph()
      return prepared
    })
    expect(await addLibraryDataToCanvas(source)).toBeNull()
    expect(mocks.add).not.toHaveBeenCalled()
    expect(mocks.toast).toHaveBeenCalled()
  })

  it('keeps the graph unchanged when the original is unavailable', async () => {
    mocks.prepare.mockRejectedValue(new Error('SOURCE_UNAVAILABLE'))
    expect(await addLibraryDataToCanvas(source)).toBeNull()
    expect(graph.nodes).toHaveLength(0)
    expect(mocks.add).not.toHaveBeenCalled()
  })

  it('refuses read-only canvases before preparing data', async () => {
    app.canvas.selectOnly = true
    expect(await addLibraryDataToCanvas(source)).toBeNull()
    expect(mocks.prepare).not.toHaveBeenCalled()
  })
})
