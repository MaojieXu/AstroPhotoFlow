import { markRaw } from 'vue'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { ComponentWidgetImpl, addWidget } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'

import CanvasDataWidget from './CanvasDataWidget.vue'

const registered = new WeakSet<ComfyApp>()

export function attachDataReferenceDisplay(node: LGraphNode) {
  if (node.comfyClass !== 'APF_DATA_REFERENCE' && node.comfyClass !== 'APF_FILE_REFERENCE') return
  // Restored graphs may carry the old empty input array. Add ports through native APIs,
  // retaining node IDs, existing links, reference widgets and graph serialization.
  if (node.comfyClass === 'APF_DATA_REFERENCE') {
    for (const [name, type] of [['science', 'APF_SCIENCE'], ['images', 'IMAGE']]) {
      if (!node.inputs?.some(input => input.name === name)) node.addInput(name!, type!)
    }
  }
  const reference = node.widgets?.find(widget => widget.name === 'reference')
  if (!reference) return
  reference.options = {
    ...reference.options,
    surfaces: { canvas: 'never', vueNode: 'never', panel: 'never' }
  }
  if (node.widgets?.some(widget => widget.name === 'apf_data_display')) return
  const widget = new ComponentWidgetImpl({
    node,
    name: 'apf_data_display',
    component: markRaw(CanvasDataWidget),
    inputSpec: { name: 'apf_data_display', type: 'STRING' },
    options: {
      serialize: false,
      surfaces: { canvas: 'shown', vueNode: 'shown', panel: 'never' },
      getMinHeight: () => 80
    }
  })
  widget.serialize = false
  addWidget(node, widget)
  node.expandToFitContent()
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
