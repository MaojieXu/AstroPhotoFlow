import { fromPartial } from '@total-typescript/shoehorn'
import { bundleCapabilities } from './bundleCatalog'
import type { NodeCapability } from '@astrophotoflow/ui'
import { describe, expect, it } from 'vitest'
import { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { isComponentWidget } from '@/scripts/domWidget'
import { attachSirilPreview } from './sirilPreviewDisplay'

describe('Siril preview display', () => {
  it('adds one display-only component without changing persisted tool parameters', () => {
    bundleCapabilities.set('APF_169de0837f814cdea3295541ecacf463', fromPartial<NodeCapability>({
      node: { native_type: 'APF_169de0837f814cdea3295541ecacf463', definition: { parameters: [
        { name: 'linked', default: false }, { name: 'shadowsclip', default: -2.8 }, { name: 'targetbg', default: 0.25 }
      ] } }, operation: { package_id: 'siril', operation_id: 'autostretch' }, preview: { kind: 'science-image', input: 'image', max_edge: 1024 }
    }))
    const node = new LGraphNode('Siril Auto Stretch')
    node.comfyClass = 'APF_169de0837f814cdea3295541ecacf463'
    node.comfyClass = 'APF_169de0837f814cdea3295541ecacf463'
    node.serialize_widgets = true
    node.addWidget('toggle', 'linked', false, () => {})
    node.addWidget('number', 'shadowsclip', -2.8, () => {})
    node.addWidget('number', 'targetbg', 0.25, () => {})
    attachSirilPreview(node)
    attachSirilPreview(node)
    const preview = node.widgets?.find(widget => widget.name === 'apf_siril_preview')
    expect(preview && isComponentWidget(preview)).toBe(true)
    expect(preview?.serialize).toBe(false)
    expect(node.serialize().widgets_values).toEqual([false, -2.8, 0.25])
    expect(node.widgets?.filter(widget => widget.name === 'apf_siril_preview')).toHaveLength(1)
  })
})
