import { resolveNodeCategoryLabel, resolveNodeDefText, setActiveLocale } from '@/i18n'
import { fromPartial } from '@total-typescript/shoehorn'
import { bundleCapabilities } from '../sidebar/bundleCatalog'
import type { NodeCapability } from '@astrophotoflow/ui'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { waitFor } from '@testing-library/vue'
import { LGraph, LGraphNode, LiteGraph } from '@/lib/litegraph/src/litegraph'
import { isComponentWidget } from '@/scripts/domWidget'
import { api } from '@/scripts/api'
import { useExtensionStore } from '@/stores/extensionStore'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import type { ComfyNodeDefImpl } from '@/stores/nodeDefStore'
import type { ComfyApp, ComfyExtension } from '@/types/comfy'
import { attachBundlePreview, configureBundleNode, registerBundlePreviewDisplay } from './bundlePreviewDisplay'

describe('Siril preview display', () => {
  it('uses native default-title resolution and preserves authored titles', () => {
    const type = 'APF_title_fixture'
    bundleCapabilities.set(type, fromPartial<NodeCapability>({ node: { definition: { name: 'Auto Stretch (autostretch)' } },
      display: { en: { name: 'Auto Stretch (autostretch)' }, zh: { name: '自动拉伸（autostretch）' } } }))
    onTestFinished(() => { bundleCapabilities.delete(type) })
    const defaultNode = new LGraphNode('自动拉伸（autostretch）')
    defaultNode.comfyClass = type
    configureBundleNode(defaultNode)
    expect(defaultNode.title).toBe('')
    const custom = new LGraphNode('My processing plan')
    custom.comfyClass = type
    configureBundleNode(custom)
    expect(custom.title).toBe('My processing plan')
  })
  it('refreshes the open catalog on a bundle event and keeps missing graph nodes', async () => {
    setActivePinia(createPinia())
    const type = 'APF_00000000000040008000000000000002'
    const capability: NodeCapability = {
      automatic_result_preview: false,
      node: { native_type: type, content_token: 'current', definition: {
        definition_id: '00000000-0000-4000-8000-000000000002', name: 'Reloadable bundle',
        description: '', source: 'package', inputs: [], outputs: [], parameters: [],
        category: ['stretch-color', 'automatic-stretch'],
        execution: { package_id: 'siril', operation_id: 'autostretch', inputs: {}, parameters: {}, outputs: {} }
      } },
      display: {
        en: { name: 'Translated Bundle', category: ['Stretch and Color', 'Automatic Stretch'], description: 'English description', help: '', inputs: {}, outputs: {}, parameters: {} },
        zh: { name: '中文节点', category: ['拉伸与色彩', '自动拉伸'], description: '中文说明', help: '', inputs: {}, outputs: {}, parameters: {} }
      }, available: true, reason: null, preview: null, help: '', examples: [],
      operation: { package_id: 'siril', version: '1.4.4', operation_id: 'autostretch', name: 'Auto Stretch', description: '', syntax: 'autostretch', scriptable: true, parameters: [], inputs: [], outputs: [], content_token: 'current', ready: true, cancel_supported: true }
    }
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([capability])))
    class ReloadableBundleNode extends LGraphNode {}
    class NativeFixtureNode extends LGraphNode {}
    LiteGraph.registerNodeType(type, ReloadableBundleNode)
    LiteGraph.registerNodeType('NativeFixtureNode', NativeFixtureNode)
    const definitions = useNodeDefStore()
    definitions.nodeDefsByName[type] = fromPartial<ComfyNodeDefImpl>({ name: type })
    definitions.nodeDefsByName.NativeFixtureNode = fromPartial<ComfyNodeDefImpl>({ name: 'NativeFixtureNode' })
    const graph = new LGraph()
    const node = LiteGraph.createNode(type)!
    node.title = 'My custom processing title'
    graph.add(node)
    const app = fromPartial<ComfyApp>({
      rootGraph: graph, isGraphReady: true,
      reloadNodeDefs: vi.fn().mockResolvedValue(undefined),
      registerExtension: (extension: ComfyExtension) => useExtensionStore().registerExtension(extension)
    })
    const dispose = registerBundlePreviewDisplay(app)
    onTestFinished(() => {
      dispose?.()
      bundleCapabilities.clear()
    })
    await waitFor(() => expect(bundleCapabilities.get(type)?.available).toBe(true))
    expect(definitions.visibleNodeDefs.map(definition => definition.name)).toEqual([type])
    expect(NativeFixtureNode.skip_list).toBe(true)
    const persisted = JSON.stringify(graph.serialize())
    await setActiveLocale('en')
    expect(resolveNodeDefText('display_name', type, 'Backend name')).toBe('Translated Bundle')
    expect(resolveNodeCategoryLabel('siril/stretch-color/automatic-stretch', '')).toBe('Automatic Stretch')
    await setActiveLocale('zh')
    expect(resolveNodeDefText('display_name', type, 'Backend name')).toBe('中文节点')
    expect(resolveNodeCategoryLabel('siril/stretch-color/automatic-stretch', '')).toBe('自动拉伸')
    await setActiveLocale('en')
    expect(JSON.stringify(graph.serialize())).toBe(persisted)
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([{ ...capability, display: {}, available: false, reason: 'Removed' }])))
    api.dispatchCustomEvent('apf.bundles_changed', {})
    await waitFor(() => expect(bundleCapabilities.get(type)?.available).toBe(false))
    expect(LiteGraph.registered_node_types[type]).toBeUndefined()
    expect(definitions.visibleNodeDefs).toEqual([])
    expect(graph.nodes).toContain(node)
    expect(resolveNodeDefText('display_name', type, 'Backend name')).toBe('Backend name')
    expect(resolveNodeCategoryLabel('siril/stretch-color/automatic-stretch', 'automatic-stretch')).toBe('automatic-stretch')
    await setActiveLocale('zh')
    expect(resolveNodeDefText('display_name', type, 'Backend name')).toBe('Backend name')
    expect(JSON.stringify(graph.serialize())).toBe(persisted)
    await setActiveLocale('en')
  })

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
    attachBundlePreview(node)
    attachBundlePreview(node)
    const preview = node.widgets?.find(widget => widget.name === 'apf_bundle_preview')
    expect(preview && isComponentWidget(preview)).toBe(true)
    expect(preview?.serialize).toBe(false)
    expect(node.serialize().widgets_values).toEqual([false, -2.8, 0.25])
    expect(node.widgets?.filter(widget => widget.name === 'apf_bundle_preview')).toHaveLength(1)
  })
})
