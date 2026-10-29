import { markRaw } from 'vue'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { ComponentWidgetImpl } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'

import SirilPreviewWidget from './SirilPreviewWidget.vue'

const registered = new WeakSet<ComfyApp>()

export function attachSirilPreview(node: LGraphNode) {
  if (node.comfyClass !== 'APF_169de0837f814cdea3295541ecacf463' || node.widgets?.some(widget => widget.name === 'apf_siril_preview')) return
  const widget = new ComponentWidgetImpl({
    node, name: 'apf_siril_preview', component: markRaw(SirilPreviewWidget),
    inputSpec: { name: 'apf_siril_preview', type: 'STRING' },
    options: {
      serialize: false, surfaces: { canvas: 'never', vueNode: 'shown', panel: 'never' },
      getMinHeight: () => 270, getMaxHeight: () => 270
    }
  })
  widget.serialize = false
  node.addCustomWidget(widget)
}

export function registerSirilPreviewDisplay(app: ComfyApp) {
  if (registered.has(app)) return
  registered.add(app)
  function hydrate() {
    for (const graph of [app.rootGraph, ...app.rootGraph.subgraphs.values()]) {
      for (const node of graph.nodes) attachSirilPreview(node)
    }
  }
  app.registerExtension({
    name: 'AstroPhotoFlow.SirilPreview', nodeCreated: attachSirilPreview,
    afterConfigureGraph: hydrate
  })
  if (app.isGraphReady) hydrate()
}
