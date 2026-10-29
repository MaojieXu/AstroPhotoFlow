import { createNodeClient } from '@astrophotoflow/ui'
import { markRaw } from 'vue'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { api } from '@/scripts/api'
import { ComponentWidgetImpl } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'

import SirilPreviewWidget from './SirilPreviewWidget.vue'

import { bundleCapabilities } from './bundleCatalog'

const registered = new WeakSet<ComfyApp>()

export function attachSirilPreview(node: LGraphNode) {
  if (!node.comfyClass || !bundleCapabilities.get(node.comfyClass)?.preview || node.widgets?.some(widget => widget.name === 'apf_siril_preview')) return
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
  async function refreshCatalog() {
    const capabilities = await createNodeClient(fetch).list()
    bundleCapabilities.clear()
    for (const capability of capabilities) bundleCapabilities.set(capability.node.native_type, capability)
    hydrate()
  }
  api.addEventListener('reconnected', () => {
    void app.reloadNodeDefs().then(refreshCatalog)
  })
  app.registerExtension({
    name: 'AstroPhotoFlow.BundlePreview',
    setup: refreshCatalog,
    nodeCreated: attachSirilPreview,
    afterConfigureGraph: hydrate
  })
  if (app.isGraphReady) hydrate()
}
