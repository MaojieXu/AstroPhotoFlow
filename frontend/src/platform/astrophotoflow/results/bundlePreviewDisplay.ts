import { createNodeClient } from '@astrophotoflow/ui'
import type { NodeCapability } from '@astrophotoflow/ui'
import { markRaw } from 'vue'

import { LiteGraph } from '@/lib/litegraph/src/litegraph'
import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { reportError } from '@/platform/telemetry/reportError'
import { api } from '@/scripts/api'
import { ComponentWidgetImpl } from '@/scripts/domWidget'
import type { ComfyApp } from '@/types/comfy'
import { useExtensionStore } from '@/stores/extensionStore'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import { useToast } from '@/components/ui/toast/toastStore'

import BundleAvailabilityWidget from './BundleAvailabilityWidget.vue'
import NodeParameterActions from './NodeParameterActions.vue'

import { bundleCapabilities, bundleNodeIssue, rememberBundleSchema } from '../sidebar/bundleCatalog'
import { mergeBundleNodeI18n, t } from '@/i18n'
import { escapeI18nMessage, normalizeI18nKey } from '@/utils/formatUtil'

const registered = new WeakSet<ComfyApp>()
const disposers = new Set<() => void>()

import.meta.hot?.dispose(() => {
  for (const dispose of disposers) dispose()
})

export function configureBundleNode(node: LGraphNode, previous?: NodeCapability) {
  const capability = node.comfyClass ? bundleCapabilities.get(node.comfyClass) : undefined
  if (capability) {
    const defaults = [capability.node.definition.name, ...Object.values(capability.display ?? {}).map(display => display?.name)]
    if (previous) defaults.push(previous.node.definition.name, ...Object.values(previous.display ?? {}).map(display => display?.name))
    if (defaults.includes(node.title)) node.title = ''
    for (const parameter of capability.node.definition.parameters) {
      const widget = node.widgets?.find(item => item.name === parameter.name)
      if (widget) widget.advanced = parameter.advanced
    }
    if (capability.node.definition.parameters.length && !node.widgets?.some(item => item.name === 'apf_parameter_actions')) {
      const actions = new ComponentWidgetImpl({
        node, name: 'apf_parameter_actions', component: markRaw(NodeParameterActions),
        inputSpec: { name: 'apf_parameter_actions', type: 'STRING' },
        options: { serialize: false, surfaces: { canvas: 'shown', vueNode: 'shown', panel: 'never' },
          getMinHeight: () => 28, getMaxHeight: () => 28 }
      })
      actions.serialize = false
      node.addCustomWidget(actions)
      node.widgets?.splice(node.widgets.indexOf(actions), 1)
      node.widgets?.unshift(actions)
    }
    for (const parameter of capability.operation?.parameters ?? []) {
      if (!parameter.editor) continue
      const binding = capability.node.definition.execution.parameters[parameter.name]
      if (binding?.kind !== 'parameter') continue
      const field = node.widgets?.find(widget => widget.name === binding.name)
      if (field) field.hidden = true
    }
  }
}

function syncAvailabilityWidget(node: LGraphNode) {
  const name = 'apf_bundle_availability'
  const existing = node.widgets?.find(widget => widget.name === name)
  if (!bundleNodeIssue(node)) {
    if (existing) node.removeWidget(existing)
    return
  }
  if (existing) return
  const widget = new ComponentWidgetImpl({
    node, name, component: markRaw(BundleAvailabilityWidget),
    inputSpec: { name, type: 'STRING' },
    options: {
      serialize: false, surfaces: { canvas: 'shown', vueNode: 'shown', panel: 'never' },
      getMinHeight: () => 36, getMaxHeight: () => 36
    }
  })
  widget.serialize = false
  node.addCustomWidget(widget)
}

export function registerBundlePreviewDisplay(app: ComfyApp) {
  if (registered.has(app)) return
  registered.add(app)
  const nodeDefs = useNodeDefStore()
  nodeDefs.registerNodeDefFilter({
    id: 'astrophotoflow.nodes', name: 'Data', description: 'Data',
    predicate: definition => definition.name.startsWith('APF_')
  })
  function hydrate(previous?: ReadonlyMap<string, NodeCapability>) {
    for (const graph of [app.rootGraph, ...app.rootGraph.subgraphs.values()]) {
      for (const node of graph.nodes) {
        configureBundleNode(node, previous?.get(node.comfyClass ?? ''))
        syncAvailabilityWidget(node)
      }
    }
    app.canvas?.setDirty(true, true)
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
        if (!capability.available && !display) continue
        const definition = capability.node.definition
        const operation = capability.operation
        const packageId = definition.execution.package_id
        const category = definition.category ?? []
        if (category.length) {
          categories[normalizeI18nKey(packageId)] = packageId
          category.forEach((part, index) => {
            const path = [packageId, ...category.slice(0, index + 1)].join('/')
            categories[normalizeI18nKey(path)] = escapeI18nMessage(display?.category?.[index] ?? part)
          })
        }
        const ports = (direction: 'inputs' | 'outputs') => definition[direction].map((port, index) => {
          const declared = operation?.[direction].find(item => direction === 'outputs'
            ? definition.execution.outputs[port.name] === item.name
            : definition.execution.inputs[item.name] === port.name)
          const kind = declared?.data_kind === 'sequence' ? 'sequence'
            : port.type === 'APF_FILE' ? 'file'
            : port.type === 'APF_ANALYSIS' ? 'analysis'
            : declared?.data_kind === 'video' || declared?.formats.every(format => format === 'video') ? 'video'
            : declared?.data_kind ?? 'image'
          const label = display?.[direction]?.[port.name]
          const type = t('astrophotoflow.bundle.kinds.' + kind, {}, { locale })
          const name = label?.label ?? port.name
          return [direction === 'inputs' ? normalizeI18nKey(port.name) : String(index),
            { name: escapeI18nMessage(name), tooltip: [type, label?.description].filter(Boolean).join(' · ') }] as const
        })
        const parameters = definition.parameters.map(parameter => {
          const declared = operation?.parameters.find(item => {
            const binding = definition.execution.parameters[item.name]
            return binding?.kind === 'parameter' && binding.name === parameter.name
          })
          const label = display?.parameters?.[parameter.name]
          const unit = parameter.unit ?? declared?.unit
          const name = label?.label ?? parameter.name
          const range = parameter.minimum != null || parameter.maximum != null
            ? `${parameter.minimum ?? '−∞'} … ${parameter.maximum ?? '∞'}` : ''
          return [normalizeI18nKey(parameter.name), {
            name: escapeI18nMessage(unit ? name + ' (' + unit + ')' : name),
            tooltip: [label?.description, range].filter(Boolean).join(' · ')
          }] as const
        })
        definitions[normalizeI18nKey(capability.node.native_type)] = {
          display_name: escapeI18nMessage(display?.name ?? definition.name),
          description: escapeI18nMessage(display?.description ?? definition.description),
          help: escapeI18nMessage(display?.help ?? capability.help),
          inputs: Object.fromEntries([...ports('inputs'), ...parameters]),
          outputs: Object.fromEntries(ports('outputs'))
        }
      }
      translations[locale] = definitions
      categoryTranslations[locale] = categories
    }
    mergeBundleNodeI18n(translations, categoryTranslations)
    const previous = new Map(bundleCapabilities)
    bundleCapabilities.clear()
    for (const capability of capabilities) bundleCapabilities.set(capability.node.native_type, capability)
    for (const type of new Set([...previous.keys(), ...bundleCapabilities.keys()])) {
      if (!bundleCapabilities.get(type)?.available) {
        if (LiteGraph.registered_node_types[type]) LiteGraph.unregisterNodeType(type)
        nodeDefs.removeNodeDef(type)
      }
    }
    for (const [name, type] of Object.entries(LiteGraph.registered_node_types)) type.skip_list = !name.startsWith('APF_')
    hydrate(previous)
  }
  let refreshing = Promise.resolve()
  function reportCatalogError(error: unknown) {
    reportError(error, { errorType: 'error_loading_bundle_catalog', surface: 'platform' })
    useToast().error(t('astrophotoflow.bundle.catalogError'), {
      description: error instanceof Error ? error.message : String(error)
    })
  }
  function refresh() {
    refreshing = refreshing.then(() => app.reloadNodeDefs({ refreshWidgets: false })).then(refreshCatalog).catch(reportCatalogError)
    return refreshing
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
    setup: () => {
      refreshing = refreshing.then(refreshCatalog).catch(reportCatalogError)
      return refreshing
    },
    beforeRegisterNodeDef: rememberBundleSchema,
    nodeCreated: (node: LGraphNode) => configureBundleNode(node),
    afterConfigureGraph: () => hydrate()
  }
  const existing = useExtensionStore().extensions.find(value => value.name === extension.name)
  if (existing) Object.assign(existing, extension)
  else app.registerExtension(extension)
  if (app.isGraphReady) refresh()
  return dispose
}
