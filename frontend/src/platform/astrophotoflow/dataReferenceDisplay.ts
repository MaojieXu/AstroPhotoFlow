import { markRaw } from 'vue'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { ComponentWidgetImpl } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'

import CanvasDataWidget from './CanvasDataWidget.vue'

const registered = new WeakSet<ComfyApp>()

export function attachDataReferenceDisplay(node: LGraphNode) {
  if (node.comfyClass !== 'APF_DATA_REFERENCE') return
  const reference = node.widgets?.find(widget => widget.name === 'reference')
  if (!reference) return
  reference.options.surfaces = { canvas: 'never', vueNode: 'never', panel: 'never' }
  if (node.widgets?.some(widget => widget.name === 'apf_data_display')) return
  const widget = new ComponentWidgetImpl({
    node,
    name: 'apf_data_display',
    component: markRaw(CanvasDataWidget),
    inputSpec: { name: 'apf_data_display', type: 'STRING' },
    options: {
      serialize: false,
      surfaces: { canvas: 'never', vueNode: 'shown', panel: 'never' },
      getMinHeight: () => 440,
      getMaxHeight: () => 440
    }
  })
  widget.serialize = false
  node.addCustomWidget(widget)
}

export function registerDataReferenceDisplay(app: ComfyApp) {
  if (registered.has(app)) return
  registered.add(app)
  function hydrate() {
    for (const graph of [app.rootGraph, ...app.rootGraph.subgraphs.values()]) {
      for (const node of graph.nodes) attachDataReferenceDisplay(node)
    }
  }
  app.registerExtension({
    name: 'AstroPhotoFlow.DataReferenceDisplay',
    nodeCreated: attachDataReferenceDisplay,
    afterConfigureGraph: hydrate
  })
  if (app.isGraphReady) hydrate()
}
