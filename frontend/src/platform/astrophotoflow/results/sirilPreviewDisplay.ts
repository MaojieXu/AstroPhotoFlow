import { createNodeClient } from '@astrophotoflow/ui'
import { markRaw } from 'vue'

import { LiteGraph } from '@/lib/litegraph/src/litegraph'
import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { reportError } from '@/platform/telemetry/reportError'
import { api } from '@/scripts/api'
import { ComponentWidgetImpl } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'
import { useExtensionStore } from '@/stores/extensionStore'
import { useNodeDefStore } from '@/stores/nodeDefStore'

import SirilPreviewWidget from './SirilPreviewWidget.vue'

import { bundleCapabilities } from '../sidebar/bundleCatalog'
import { mergeBundleNodeI18n } from '@/i18n'
import { escapeI18nMessage, normalizeI18nKey } from '@/utils/formatUtil'

const registered = new WeakSet<ComfyApp>()
const disposers = new Set<() => void>()

import.meta.hot?.dispose(() => {
  for (const dispose of disposers) dispose()
})

export function attachSirilPreview(node: LGraphNode) {
  if (!node.comfyClass || !bundleCapabilities.get(node.comfyClass)?.preview || node.widgets?.some(widget => widget.name === 'apf_siril_preview')) return
  const widget = new ComponentWidgetImpl({
    node, name: 'apf_siril_preview', component: markRaw(SirilPreviewWidget),
    inputSpec: { name: 'apf_siril_preview', type: 'STRING' },
    options: {
      serialize: false, surfaces: { canvas: 'never', vueNode: 'shown', panel: 'never' },
      getMinHeight: () => 40, getMaxHeight: () => 330
    }
  })
  widget.serialize = false
  node.addCustomWidget(widget)
}

export function configureBundleNode(node: LGraphNode) {
  const capability = node.comfyClass ? bundleCapabilities.get(node.comfyClass) : undefined
  if (capability) {
    const defaults = [capability.node.definition.name, ...Object.values(capability.display ?? {}).map(display => display?.name)]
    if (defaults.includes(node.title)) node.title = ''
  }
  attachSirilPreview(node)
}

export function registerSirilPreviewDisplay(app: ComfyApp) {
  if (registered.has(app)) return
  registered.add(app)
  const nodeDefs = useNodeDefStore()
  nodeDefs.registerNodeDefFilter({
    id: 'astrophotoflow.nodes', name: 'Data', description: 'Data',
    predicate: definition => definition.name.startsWith('APF_')
  })
  function hydrate() {
    for (const graph of [app.rootGraph, ...app.rootGraph.subgraphs.values()]) {
      for (const node of graph.nodes) configureBundleNode(node)
    }
  }
  async function refreshCatalog() {
    const capabilities = await createNodeClient(fetch).list()
    const translations: Partial<Record<'en' | 'zh', Record<string, unknown>>> = {}
    const categoryTranslations: Partial<Record<'en' | 'zh', Record<string, string>>> = {}
    for (const locale of ['en', 'zh'] as const) {
      const definitions: Record<string, unknown> = {}
      const categories: Record<string, string> = {}
      for (const capability of capabilities) {
        const display = capability.display?.[locale]
        if (!display) continue
        const packageId = capability.node.definition.execution.package_id
        const category = capability.node.definition.category ?? []
        if (category.length) {
          categories[normalizeI18nKey(packageId)] = packageId === 'siril' ? 'Siril' : packageId
          category.forEach((part, index) => {
            const path = [packageId, ...category.slice(0, index + 1)].join('/')
            categories[normalizeI18nKey(path)] = escapeI18nMessage(display.category?.[index] ?? part)
          })
        }
        definitions[normalizeI18nKey(capability.node.native_type)] = {
          display_name: escapeI18nMessage(display.name),
          description: escapeI18nMessage(display.description),
          inputs: Object.fromEntries(Object.entries({ ...display.inputs, ...display.parameters }).map(([name, label]) =>
            [normalizeI18nKey(name), { name: escapeI18nMessage(label.label), tooltip: label.description }])),
          outputs: Object.fromEntries(capability.node.definition.outputs.map((port, index) =>
            [String(index), { name: escapeI18nMessage(display.outputs?.[port.name]?.label ?? port.name), tooltip: display.outputs?.[port.name]?.description ?? '' }]))
        }
      }
      translations[locale] = definitions
      categoryTranslations[locale] = categories
    }
    mergeBundleNodeI18n(translations, categoryTranslations)
    const previous = [...bundleCapabilities.keys()]
    bundleCapabilities.clear()
    for (const capability of capabilities) bundleCapabilities.set(capability.node.native_type, capability)
    for (const type of new Set([...previous, ...bundleCapabilities.keys()])) {
      if (!bundleCapabilities.get(type)?.available) {
        if (LiteGraph.registered_node_types[type]) LiteGraph.unregisterNodeType(type)
        nodeDefs.removeNodeDef(type)
      }
    }
    for (const [name, type] of Object.entries(LiteGraph.registered_node_types)) type.skip_list = !name.startsWith('APF_')
    hydrate()
  }
  let refreshing = Promise.resolve()
  function refresh() {
    refreshing = refreshing.then(() => app.reloadNodeDefs()).then(refreshCatalog).catch(error => {
      reportError(error, { errorType: 'error_loading_bundle_catalog', surface: 'platform' })
    })
  }
  api.addEventListener('reconnected', refresh)
  api.addEventListener('apf.bundles_changed', refresh)
  function dispose() {
    nodeDefs.unregisterNodeDefFilter('astrophotoflow.nodes')
    api.removeEventListener('reconnected', refresh)
    api.removeEventListener('apf.bundles_changed', refresh)
    disposers.delete(dispose)
    registered.delete(app)
  }
  disposers.add(dispose)
  const extension = {
    name: 'AstroPhotoFlow.BundlePreview',
    setup: refreshCatalog,
    nodeCreated: configureBundleNode,
    afterConfigureGraph: hydrate
  }
  const existing = useExtensionStore().extensions.find(value => value.name === extension.name)
  if (existing) Object.assign(existing, extension)
  else app.registerExtension(extension)
  if (app.isGraphReady) refresh()
  return dispose
}
