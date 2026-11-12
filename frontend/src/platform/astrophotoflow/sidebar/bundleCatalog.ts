import type { NodeCapability } from '@astrophotoflow/ui'
import { isEqual } from 'es-toolkit'
import { shallowReactive } from 'vue'

import { LiteGraph } from '@/lib/litegraph/src/litegraph'
import type { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import type { ComfyApiWorkflow } from '@/platform/workflow/validation/schemas/workflowSchema'
import type { ComfyNodeDef } from '@/schemas/nodeDefSchema'
import { getNodeByExecutionId } from '@/utils/graphTraversalUtil'

export const bundleCapabilities = shallowReactive(new Map<string, NodeCapability>())

// Each native constructor keeps the schema its instances were created with.
const bundleSchemas = new WeakMap<object, unknown>()

export function rememberBundleSchema(nodeType: typeof LGraphNode, def: ComfyNodeDef) {
  if (!/^APF_[a-f0-9]{32}$/.test(def.name)) return
  bundleSchemas.set(nodeType, structuredClone([
    def.input, def.input_order, def.output, def.output_name, def.output_is_list, def.output_node
  ]))
}

export function bundleNodeIssue(node: LGraphNode | null) {
  if (!node?.comfyClass) return
  const schema = bundleSchemas.get(node.constructor)
  const capability = bundleCapabilities.get(node.comfyClass)
  if (!schema && !capability) return
  const current = LiteGraph.registered_node_types[node.comfyClass]
  if (!current) return schema || capability?.available === false ? 'apfSoftware.unavailable' : undefined
  const latest = bundleSchemas.get(current)
  if (schema && latest && !isEqual(schema, latest)) return 'apfSoftware.nodeDefinitionChanged'
}

export function bundlePromptIssue(graph: LGraph, prompt: ComfyApiWorkflow, targets?: readonly string[]) {
  const pending = [...(targets?.length ? targets : Object.keys(prompt))]
  const checked = new Set<string>()
  while (pending.length) {
    const id = pending.pop()!
    const entry = prompt[id]
    if (!entry || checked.has(id)) continue
    checked.add(id)
    const issue = bundleNodeIssue(getNodeByExecutionId(graph, id))
    if (issue) return issue
    for (const input of Object.values(entry.inputs)) {
      if (Array.isArray(input) && typeof input[0] === 'string') pending.push(input[0])
    }
  }
}
