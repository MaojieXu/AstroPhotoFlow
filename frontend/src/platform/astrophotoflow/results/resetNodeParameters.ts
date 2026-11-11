import { isEqual } from 'es-toolkit'

import type { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { useApp } from '@/scripts/appInstance'
import { getWidgetDefaultValue } from '@/utils/widgetUtil'
import { isSelectOnly } from '@/utils/litegraphUtil'
import { bundleCapabilities, bundleNodeIssue } from '../sidebar/bundleCatalog'

export function nodeParameterDefaults(node: LGraphNode) {
  const capability = bundleCapabilities.get(node.comfyClass ?? '')
  if (!capability?.available || bundleNodeIssue(node)) return []
  return capability.node.definition.parameters.flatMap((parameter) => {
    const widget = node.widgets?.find((item) => item.name === parameter.name)
    const spec = node.constructor.nodeData?.inputs?.[parameter.name]
    const value = getWidgetDefaultValue(spec)
    return widget && value !== undefined ? [{ widget, value }] : []
  })
}

export function resetNodeParameters(node: LGraphNode) {
  const app = useApp()
  const graph = node.graph
  if (!graph || graph !== app.canvas.graph || isSelectOnly(app.canvas)) return
  const changes = nodeParameterDefaults(node).filter(
    ({ widget, value }) => !isEqual(widget.value, value)
  )
  if (!changes.length) return
  app.canvas.emitBeforeChange()
  graph.beforeChange()
  try {
    for (const { widget, value } of changes) {
      const previous = widget.value
      widget.value = structuredClone(value)
      widget.callback?.(widget.value, app.canvas, node)
      // Reset restores the declared value, even if a callback applies edit-time rounding.
      widget.value = structuredClone(value)
      node.onWidgetChanged?.(widget.name, widget.value, previous, widget)
    }
    graph.incrementVersion()
  } finally {
    graph.afterChange()
    app.canvas.emitAfterChange()
    app.canvas.setDirty(true, true)
  }
}
