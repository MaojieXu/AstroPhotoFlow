import { describe, expect, it } from 'vitest'
import { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { isComponentWidget } from '@/scripts/domWidget'
import { attachSirilPreview } from './sirilPreviewDisplay'

describe('Siril preview display', () => {
  it('adds one display-only component without changing persisted tool parameters', () => {
    const node = new LGraphNode('Siril Auto Stretch')
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
