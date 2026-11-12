import { createPinia, setActivePinia } from 'pinia'
import { fromPartial } from '@total-typescript/shoehorn'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { NodeCapability } from '@astrophotoflow/ui'
import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { ComfyNodeDefImpl } from '@/stores/nodeDefStore'
import { bundleCapabilities } from '../sidebar/bundleCatalog'
import {
  nodeParameterDefaults,
  resetNodeParameters
} from './resetNodeParameters'

const runtime = vi.hoisted(() => ({ app: undefined as unknown }))
vi.mock('@/scripts/appInstance', () => ({ useApp: () => runtime.app }))
vi.mock('@/utils/litegraphUtil', async (original) => ({
  ...(await original<object>()),
  isSelectOnly: () => false
}))
afterEach(() => bundleCapabilities.clear())

describe('restore node parameters', () => {
  it('uses the instance definition, resets advanced values in one transaction and preserves graph structure', () => {
    setActivePinia(createPinia())
    class ProcessingNode extends LGraphNode {}
    ProcessingNode.nodeData = fromPartial<ComfyNodeDefImpl>({
      inputs: {
        target: { name: 'target', type: 'FLOAT', default: 0.25 },
        linked: { name: 'linked', type: 'BOOLEAN', default: false },
        runtime: { name: 'runtime', type: 'STRING', default: '{}' }
      }
    })
    const graph = new LGraph()
    const node = new ProcessingNode('Authored title')
    node.comfyClass = 'APF_reset_fixture'
    node.pos = [100, 200]
    const changed = vi.fn()
    const field = node.addWidget('number', 'target', 0.7, changed)
    field.callback = (value: unknown) => {
      field.value = Math.round(Number(value) * 10) / 10
      changed()
    }
    node.addWidget('toggle', 'linked', true, changed)
    node.addWidget('text', 'runtime', '{"threads":2}', changed)
    const reference = node.addWidget(
      'text',
      'reference',
      'fixed asset',
      changed
    )
    graph.add(node)
    node.addInput('image', 'APF_SCIENCE')
    const upstream = new LGraphNode('Source')
    upstream.addOutput('image', 'APF_SCIENCE')
    graph.add(upstream)
    upstream.connect(0, node, 0)
    const links = graph.serialize().links
    bundleCapabilities.set(
      node.comfyClass,
      fromPartial<NodeCapability>({
        available: true,
        node: {
          definition: {
            parameters: [
              { name: 'target', default: 0.99 },
              { name: 'linked', default: true },
              { name: 'runtime', default: 'newer default' }
            ]
          }
        }
      })
    )
    const canvas = {
      graph,
      emitBeforeChange: vi.fn(),
      emitAfterChange: vi.fn(),
      setDirty: vi.fn()
    }
    runtime.app = { canvas }
    resetNodeParameters(node)
    expect(node.widgets?.slice(0, 3).map((widget) => widget.value)).toEqual([
      0.25,
      false,
      '{}'
    ])
    expect(reference.value).toBe('fixed asset')
    expect(node.title).toBe('Authored title')
    expect([...node.pos]).toEqual([100, 200])
    expect(graph.serialize().links).toEqual(links)
    expect(canvas.emitBeforeChange).toHaveBeenCalledTimes(1)
    expect(canvas.emitAfterChange).toHaveBeenCalledTimes(1)
    expect(changed).toHaveBeenCalledTimes(3)
    resetNodeParameters(node)
    expect(canvas.emitBeforeChange).toHaveBeenCalledTimes(1)
    expect(nodeParameterDefaults(node)).toHaveLength(3)
  })
})
