import { fromPartial } from '@total-typescript/shoehorn'
import { describe, expect, it, vi } from 'vitest'

import { LGraph, LGraphNode, LiteGraph } from '@/lib/litegraph/src/litegraph'
import { isComponentWidget } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'

import { attachDataReferenceDisplay, registerDataReferenceDisplay } from './dataReferenceDisplay'

const value = JSON.stringify({ kind: 'asset_version', asset_version_id: '00000000-0000-4000-8000-000000000001', selection: { kind: 'whole_file' } })

function dataNode() {
  const node = new LGraphNode('Scientific image')
  node.comfyClass = 'APF_DATA_REFERENCE'
  node.serialize_widgets = true
  node.addWidget('text', 'reference', value, () => {})
  return node
}

describe('Nodes 2.0 data reference display', () => {
  it('keeps one serialized reference and hides it on every visible surface', () => {
    const node = dataNode()
    attachDataReferenceDisplay(node)
    attachDataReferenceDisplay(node)
    const reference = node.widgets?.find(widget => widget.name === 'reference')
    expect(reference?.options.surfaces).toEqual({ canvas: 'never', vueNode: 'never', panel: 'never' })
    const display = node.widgets?.find(widget => widget.name === 'apf_data_display')
    expect(display && isComponentWidget(display)).toBe(true)
    expect(display?.serialize).toBe(false)
    expect(display?.options.serialize).toBe(false)
    expect(node.serialize().widgets_values).toEqual([value])
    expect(node.widgets?.filter(widget => widget.name === 'apf_data_display')).toHaveLength(1)
  })

  it('recreates the display for pasted or restored serialized nodes without persisting preview state', () => {
    class DataNode extends LGraphNode {
      constructor() {
        super('Scientific image')
        this.comfyClass = 'APF_DATA_REFERENCE'
        this.serialize_widgets = true
        this.addWidget('text', 'reference', '', () => {})
        attachDataReferenceDisplay(this)
      }
    }
    LiteGraph.registerNodeType('APF_DATA_REFERENCE', DataNode)
    const original = LiteGraph.createNode('APF_DATA_REFERENCE')
    if (!original) throw new Error('Data node not registered')
    original.widgets![0].value = value
    const restored = original.clone()
    expect(restored?.serialize().widgets_values).toEqual([value])
    const display = restored?.widgets?.find(widget => widget.name === 'apf_data_display')
    expect(display && isComponentWidget(display) && display.node === restored).toBe(true)
  })

  it('registers once and hydrates existing graphs through the native lifecycle hook', () => {
    const graph = new LGraph()
    const node = dataNode()
    graph.add(node)
    const registerExtension = vi.fn<ComfyApp['registerExtension']>()
    const app = fromPartial<ComfyApp>({ rootGraph: graph, registerExtension })
    registerDataReferenceDisplay(app)
    registerDataReferenceDisplay(app)
    expect(registerExtension).toHaveBeenCalledTimes(1)
    const extension = registerExtension.mock.calls[0][0]
    extension.afterConfigureGraph?.([], app)
    expect(node.widgets?.some(widget => widget.name === 'apf_data_display')).toBe(true)
  })
})
