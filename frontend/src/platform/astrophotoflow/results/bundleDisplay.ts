import { markRaw } from 'vue'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { ComponentWidgetImpl } from '@/scripts/domWidget'
import { useExtensionStore } from '@/stores/extensionStore'
import type { ComfyApp } from '@/types/comfy'

import BundleResultWidget from './BundleResultWidget.vue'

const registered = new WeakSet<ComfyApp>()

export function attachBundleResult(node: LGraphNode) {
  if (
    !node.comfyClass ||
    !/^APF_[a-f0-9]{32}$/.test(node.comfyClass)
  )
    return
  node.hideOutputImages = true
  if (node.widgets?.some((widget) => widget.name === 'apf_result_view')) return
  const widget = new ComponentWidgetImpl({
    node,
    name: 'apf_result_view',
    component: markRaw(BundleResultWidget),
    inputSpec: { name: 'apf_result_view', type: 'STRING' },
    options: {
      serialize: false,
      surfaces: { canvas: 'never', vueNode: 'shown', panel: 'never' },
      getMinHeight: () => 150,
      getMaxHeight: () => 420
    }
  })
  widget.serialize = false
  node.addCustomWidget(widget)
}

export function registerBundleResultDisplay(app: ComfyApp) {
  if (registered.has(app)) return
  registered.add(app)
  function hydrate() {
    for (const graph of [app.rootGraph, ...app.rootGraph.subgraphs.values()]) {
      for (const node of graph.nodes) attachBundleResult(node)
    }
  }
  const extension = {
    name: 'AstroPhotoFlow.BundleResults',
    nodeCreated: attachBundleResult,
    afterConfigureGraph: hydrate
  }
  const existing = useExtensionStore().extensions.find(value => value.name === extension.name)
  if (existing) Object.assign(existing, extension)
  else app.registerExtension(extension)
  if (app.isGraphReady) hydrate()
}
