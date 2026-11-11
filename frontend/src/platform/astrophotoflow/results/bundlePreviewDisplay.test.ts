import { resolveNodeCategoryLabel, resolveNodeDefText, resolveNodeDefSlotText, setActiveLocale } from '@/i18n'
import { computed } from 'vue'
import { fromPartial } from '@total-typescript/shoehorn'
import { bundleCapabilities, bundleNodeIssue, bundlePromptIssue, rememberBundleSchema } from '../sidebar/bundleCatalog'
import type { NodeCapability } from '@astrophotoflow/ui'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { waitFor } from '@testing-library/vue'
import { LGraph, LGraphNode, LiteGraph } from '@/lib/litegraph/src/litegraph'
import type { NodeInputSlot } from '@/lib/litegraph/src/node/NodeInputSlot'
import { api } from '@/scripts/api'
import { useExtensionStore } from '@/stores/extensionStore'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import { ComfyNodeDefImpl, buildNodeDefTree } from '@/stores/nodeDefStore'
import type { ComfyApp, ComfyExtension } from '@/types/comfy'
import type { ComfyNodeDef } from '@/schemas/nodeDefSchema'
import { useToast } from '@/components/ui/toast/toastStore'
import * as errorReporter from '@/platform/telemetry/reportError'
import { configureBundleNode, registerBundlePreviewDisplay } from './bundlePreviewDisplay'

describe('Siril preview display', () => {
  it('uses native default-title resolution and preserves authored titles', () => {
    const type = 'APF_title_fixture'
    bundleCapabilities.set(type, fromPartial<NodeCapability>({ node: { definition: { name: 'Auto Stretch (autostretch)', parameters: [] } },
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
    const previous = bundleCapabilities.get(type)!
    bundleCapabilities.set(type, fromPartial<NodeCapability>({ node: { definition: { name: 'New default', parameters: [] } },
      display: { en: { name: 'New default' }, zh: { name: '新译名' } } }))
    const staleDefault = new LGraphNode('自动拉伸（autostretch）')
    staleDefault.comfyClass = type
    configureBundleNode(staleDefault, previous)
    expect(staleDefault.title).toBe('')
    configureBundleNode(custom, previous)
    expect(custom.title).toBe('My processing plan')
  })
  it('refreshes the open catalog on a bundle event and keeps missing graph nodes', async () => {
    setActivePinia(createPinia())
    await setActiveLocale('zh')
    const type = 'APF_00000000000040008000000000000002'
    const capability: NodeCapability = {
      automatic_result_preview: false,
      node: { native_type: type, content_token: 'current', definition: {
        definition_id: '00000000-0000-4000-8000-000000000002', name: 'Reloadable bundle',
        description: '', source: 'custom', inputs: [{ name: 'source', type: 'APF_SCIENCE' }], outputs: [], parameters: [],
        category: ['stretch-color', 'automatic-stretch'],
        execution: { package_id: 'siril', operation_id: 'autostretch', inputs: { image: 'source' }, parameters: {}, outputs: {} }
      } },
      display: {
        en: { name: 'Translated Bundle', category: ['Stretch and Color', 'Automatic Stretch'], description: 'English description', help: '', inputs: {}, outputs: {}, parameters: {} },
        zh: { name: '中文节点', category: ['拉伸与色彩', '自动拉伸'], description: '中文说明', help: '帮助 @ 50%', inputs: { source: { label: '科学图像 @ 50%', description: '原始说明 @ 50%' } }, outputs: {}, parameters: {} }
      }, available: true, reason: null, preview: null, help: '', examples: [],
      operation: { package_id: 'siril', version: '1.4.4', operation_id: 'autostretch', name: 'Auto Stretch', description: '', syntax: 'autostretch', scriptable: true, parameters: [], inputs: [], outputs: [], content_token: 'current', ready: true, cancel_supported: true }
    }
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([capability])))
    class ReloadableBundleNode extends LGraphNode {}
    class NativeFixtureNode extends LGraphNode {}
    LiteGraph.registerNodeType(type, ReloadableBundleNode)
    LiteGraph.registerNodeType('NativeFixtureNode', NativeFixtureNode)
    const definitions = useNodeDefStore()
    const nativeDefinition = new ComfyNodeDefImpl(fromPartial<ComfyNodeDef>({ name: type,
      display_name: 'Backend name', category: 'siril/stretch-color/automatic-stretch',
      python_module: 'custom_nodes.siril', input: {}, output: [] }))
    definitions.nodeDefsByName[type] = nativeDefinition
    const translatedName = computed(() => nativeDefinition.display_name)
    const tree = computed(() => buildNodeDefTree([nativeDefinition]))
    expect(translatedName.value).toBe('Backend name')
    expect(tree.value.children?.[0].children?.[0].label).toBe('stretch-color')
    definitions.nodeDefsByName.NativeFixtureNode = fromPartial<ComfyNodeDefImpl>({ name: 'NativeFixtureNode' })
    const graph = new LGraph()
    const node = LiteGraph.createNode(type)!
    node.comfyClass = type
    const field = node.addWidget('text', 'source', 'payload', () => {})
    node.addInput('source', 'APF_SCIENCE')
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
    expect(translatedName.value).toBe('中文节点')
    expect(tree.value.children?.[0].children?.[0].label).toBe('拉伸与色彩')
    expect(resolveNodeDefSlotText('name', type, 'source')).toBe('科学图像 @ 50%')
    expect(resolveNodeDefSlotText('tooltip', type, 'source')).toContain('原始说明 @ 50%')
    expect(resolveNodeDefText('help', type)).toBe('帮助 @ 50%')
    expect(field.label).toBe('科学图像 @ 50%')
    expect((node.inputs[0] as NodeInputSlot).renderingLabel).toBe('科学图像 @ 50%')
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
    await setActiveLocale('zh')
    const updated = structuredClone(capability)
    updated.display!.zh!.name = '热更新名称'
    updated.display!.zh!.category = ['热更新分类', '自动拉伸']
    updated.display!.zh!.inputs!.source.label = '热更新输入'
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([updated])))
    api.dispatchCustomEvent('apf.bundles_changed', {})
    await waitFor(() => expect(translatedName.value).toBe('热更新名称'))
    expect(tree.value.children?.[0].children?.[0].label).toBe('热更新分类')
    expect(field.label).toBe('热更新输入')
    expect((node.inputs[0] as NodeInputSlot).renderingLabel).toBe('热更新输入')
    expect(JSON.stringify(graph.serialize())).toBe(persisted)
    const toast = vi.spyOn(useToast(), 'error')
    const report = vi.spyOn(errorReporter, 'reportError').mockImplementation(() => {})
    vi.mocked(fetch).mockResolvedValueOnce(new Response('invalid response'))
    api.dispatchCustomEvent('apf.bundles_changed', {})
    await waitFor(() => expect(toast).toHaveBeenCalled())
    expect(report).toHaveBeenCalled()
    expect(translatedName.value).toBe('热更新名称')
    expect(bundleCapabilities.get(type)?.available).toBe(true)
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

  it('keeps the native parameters and leaves results to the shared result card', () => {
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
    configureBundleNode(node)
    configureBundleNode(node)
    expect(node.serialize().widgets_values).toEqual([false, -2.8, 0.25])
    expect(node.widgets?.some(widget => widget.name === 'apf_bundle_preview')).toBe(false)
  })

  it('keeps placed nodes usable across code updates and blocks instances of a changed schema', async () => {
    setActivePinia(createPinia())
    const type = 'APF_00000000000040008000000000000003'
    const graph = new LGraph()
    const install = (value: number) => {
      class Node extends LGraphNode {}
      rememberBundleSchema(Node, fromPartial<ComfyNodeDef>({
        name: type, input: { required: { amount: ['INT', { default: value }] } }
      }))
      LiteGraph.registerNodeType(type, Node)
    }
    install(1)
    const node = LiteGraph.createNode(type)!
    node.comfyClass = type
    graph.add(node)
    const capability: NodeCapability = {
      node: { native_type: type, content_token: 'fixture', definition: {
        definition_id: '00000000-0000-4000-8000-000000000003',
        name: 'Editable Bundle', description: '', source: 'package', category: [],
        inputs: [], outputs: [], parameters: [],
        execution: { package_id: 'sample', operation_id: 'sample', inputs: {}, outputs: {}, parameters: {} }
      } },
      available: true, reason: null, operation: null, preview: null, help: '', examples: [], display: {},
      automatic_result_preview: false
    }
    const response = (implementation_token: string) =>
      new Response(JSON.stringify([{ ...capability, implementation_token }]))
    vi.mocked(fetch).mockResolvedValue(response('first'))
    const reloadNodeDefs = vi.fn().mockImplementation(() => install(1))
    const app = fromPartial<ComfyApp>({
      rootGraph: graph, isGraphReady: true, reloadNodeDefs,
      registerExtension: (extension: ComfyExtension) => useExtensionStore().registerExtension(extension)
    })
    const dispose = registerBundlePreviewDisplay(app)
    onTestFinished(() => {
      dispose?.()
      bundleCapabilities.delete(type)
      if (LiteGraph.registered_node_types[type]) LiteGraph.unregisterNodeType(type)
    })
    await waitFor(() => expect(bundleCapabilities.get(type)?.implementation_token).toBe('first'))
    const before = JSON.stringify(graph.serialize())
    const prompt = { [node.id]: { class_type: type, inputs: {} } }
    vi.mocked(fetch).mockResolvedValue(response('second'))
    api.dispatchCustomEvent('apf.bundles_changed', {})
    await waitFor(() => expect(bundleCapabilities.get(type)?.implementation_token).toBe('second'))
    expect(bundlePromptIssue(graph, prompt)).toBeUndefined()

    reloadNodeDefs.mockImplementation(() => install(2))
    vi.mocked(fetch).mockResolvedValue(response('third'))
    api.dispatchCustomEvent('apf.bundles_changed', {})
    await waitFor(() => expect(node.widgets?.some(widget => widget.name === 'apf_bundle_availability')).toBe(true))
    expect(bundleNodeIssue(node)).toBe('apfSoftware.nodeDefinitionChanged')
    expect(bundlePromptIssue(graph, prompt)).toBe('apfSoftware.nodeDefinitionChanged')
    expect(reloadNodeDefs).toHaveBeenLastCalledWith({ refreshWidgets: false })
    expect(JSON.stringify(graph.serialize())).toBe(before)
    const fresh = LiteGraph.createNode(type)!
    fresh.comfyClass = type
    expect(bundleNodeIssue(fresh)).toBeUndefined()
  })
})
