import type { WidgetValue } from '@/types/simplifiedWidget'
import type { NodeParameter } from '@astrophotoflow/ui'
import { toNodeId } from '@/types/nodeId'
import { LiteGraph } from '@/lib/litegraph/src/litegraph'
import { useApp } from '@/scripts/appInstance'
import { useLitegraphService } from '@/services/litegraphService'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import { isSelectOnly } from '@/utils/litegraphUtil'
import { bundleCapabilities } from '../sidebar/bundleCatalog'
import type { CanvasGraphCommand } from '../canvasContracts'

export function validateNodeValue(parameter: NodeParameter | undefined, value: unknown): asserts value is WidgetValue {
  if (!parameter) throw new Error('Unknown node parameter')
  if (value === null) {
    if (parameter.nullable) return
    throw new Error('Parameter is not nullable')
  }
  if (!['string','number','boolean','object'].includes(typeof value)) throw new Error('Invalid parameter type')
  if (parameter.kind === 'boolean' && typeof value !== 'boolean' || parameter.kind === 'string' && typeof value !== 'string') throw new Error('Invalid parameter type')
  if (parameter.kind === 'int' || parameter.kind === 'float') {
    if (typeof value !== 'number' || !Number.isFinite(value) || parameter.kind === 'int' && !Number.isInteger(value)) throw new Error('Invalid number')
    if (typeof parameter.minimum === 'number' && value < parameter.minimum || typeof parameter.maximum === 'number' && value > parameter.maximum) throw new Error('Parameter outside operation range')
  }
  if (parameter.kind === 'choice' && !parameter.choices?.some(choice=>choice===value)) throw new Error('Invalid choice')
}

export function applyCanvasNodeEdit(command: CanvasGraphCommand) {
  const { edit } = command.request
  const app = useApp()
  const graph = app.canvas.graph
  if (!graph || isSelectOnly(app.canvas)) throw new Error('Canvas is not editable')
  if (edit.action === 'inspect') return { node_id: null, link_id: null }
  let mutate: () => { node_id: string | number | null; link_id: string | number | null }
  if (edit.action === 'add_node') {
    const saved = command.definition
    if (!saved || saved.definition.definition_id !== edit.definition_id) throw new Error('Node definition mismatch')
    const loaded = bundleCapabilities.get(saved.native_type)
    if (!loaded || loaded.node.content_token !== saved.content_token) throw new Error('Node definition changed; reload the workbench')
    const native = useNodeDefStore().nodeDefsByName[saved.native_type]
    if (!native) throw new Error('Node is not loaded')
    const parameters = Object.entries(edit.parameters ?? {}).map(([name,value])=>{
      validateNodeValue(saved.definition.parameters.find(item=>item.name===name),value)
      return [name,value] as const
    })
    mutate = () => {
      const node = useLitegraphService().addNodeOnGraph(native)
      if (!node) throw new Error('Native node creation failed')
      for (const [name, value] of parameters) {
        const widget = node.widgets?.find(item => item.name === name)
        if (widget) widget.value = value
      }
      return { node_id: node.id, link_id: null }
    }
  } else if (edit.action === 'set_parameter') {
    const node = graph.getNodeById(toNodeId(edit.node_id))
    const capability = node?.comfyClass ? bundleCapabilities.get(node.comfyClass) : undefined
    const widget = node?.widgets?.find(item => item.name === edit.name)
    if (!node || !widget || !capability) throw new Error('Node or parameter is unavailable')
    const value=edit.value
    validateNodeValue(capability.node.definition.parameters.find(item => item.name === edit.name), value)
    mutate = () => {
      const previous = widget.value
      widget.value = value
      widget.callback?.(widget.value, app.canvas, node)
      node.onWidgetChanged?.(widget.name, widget.value, previous, widget)
      graph.incrementVersion()
      return { node_id: node.id, link_id: null }
    }
  } else if (edit.action === 'delete_node') {
    const node = graph.getNodeById(toNodeId(edit.node_id))
    if (!node) throw new Error('Node is unavailable')
    if (node.block_delete || node.ignore_remove) throw new Error('Node cannot be deleted')
    mutate = () => {
      graph.remove(node)
      return { node_id: node.id, link_id: null }
    }
  } else {
    const source = graph.getNodeById(toNodeId(edit.source_node_id))
    const target = graph.getNodeById(toNodeId(edit.target_node_id))
    const output = source?.outputs.findIndex(item => item.name === edit.source_port) ?? -1
    const input = target?.inputs.findIndex(item => item.name === edit.target_port) ?? -1
    if (!source || !target || output < 0 || input < 0 || !LiteGraph.isValidConnection(source.outputs[output].type, target.inputs[input].type)) throw new Error('Ports are missing or incompatible')
    if (target.inputs[input].link !== null) throw new Error('Target input is already connected')
    mutate = () => {
      const link = source.connect(output, target, input)
      if (!link) throw new Error('Native connection was refused')
      return { node_id: target.id, link_id: link.id }
    }
  }
  app.canvas.emitBeforeChange()
  graph.beforeChange()
  try { return mutate() }
  finally { graph.afterChange(); app.canvas.emitAfterChange(); app.canvas.setDirty(true, true) }
}
