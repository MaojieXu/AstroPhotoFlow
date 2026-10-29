import { createCanvasDataClient } from '@astrophotoflow/ui'
import type { CanvasData, CanvasDataRequest } from '@astrophotoflow/ui'

import { useToast } from '@/components/ui/toast/toastStore'
import { t } from '@/i18n'
import type { Point } from '@/lib/litegraph/src/litegraph'
import { useWorkflowStore } from '@/platform/workflow/management/stores/workflowStore'
import { useApp } from '@/scripts/appInstance'
import { useLitegraphService } from '@/services/litegraphService'
import { useNodeDefStore } from '@/stores/nodeDefStore'
import { isSelectOnly } from '@/utils/litegraphUtil'

export async function addLibraryDataToCanvas(source: CanvasDataRequest, pos?: Point) {
  const app = useApp()
  const canvas = app.canvas
  const graph = canvas.graph
  const workflow = useWorkflowStore().activeWorkflow
  try {
    if (!app.isGraphReady || !graph || isSelectOnly(canvas)) {
      throw new Error(t('astrophotoflow.canvasUnavailable'))
    }
    const definition = useNodeDefStore().nodeDefsByName.APF_DATA_REFERENCE
    if (!definition) throw new Error(t('astrophotoflow.dataNodeUnavailable'))
    const prepared = await createCanvasDataClient(fetch).prepare(source)
    if (app.canvas !== canvas || canvas.graph !== graph || useWorkflowStore().activeWorkflow !== workflow || isSelectOnly(canvas)) {
      throw new Error(t('astrophotoflow.canvasChanged'))
    }
    return insertPreparedCanvasData(prepared, pos)
  } catch (error) {
    useToast().error(t('astrophotoflow.addToCanvasFailed'), {
      description: error instanceof Error ? error.message : String(error)
    })
    return null
  }
}

export function insertPreparedCanvasData(prepared: CanvasData, pos?: Point) {
  const app = useApp()
  const canvas = app.canvas
  const graph = canvas.graph
  const definition = useNodeDefStore().nodeDefsByName.APF_DATA_REFERENCE
  if (!app.isGraphReady || !graph || isSelectOnly(canvas)) throw new Error(t('astrophotoflow.canvasUnavailable'))
  if ((useWorkflowStore().activeSubgraph ?? app.graph) !== graph) throw new Error(t('astrophotoflow.canvasChanged'))
  if (!definition) throw new Error(t('astrophotoflow.dataNodeUnavailable'))
  canvas.emitBeforeChange()
  graph.beforeChange()
  try {
    const node = useLitegraphService().addNodeOnGraph(definition, { pos, title: prepared.title })
    if (!node) throw new Error(t('astrophotoflow.dataNodeUnavailable'))
    const widget = node.widgets?.find(item => item.name === 'reference')
    if (!widget) {
      graph.remove(node)
      throw new Error(t('astrophotoflow.dataNodeUnavailable'))
    }
    widget.value = JSON.stringify(prepared.reference)
    canvas.selectNodes([node])
    canvas.setDirty(true, true)
    return node.id
  } finally {
    graph.afterChange()
    canvas.emitAfterChange()
  }
}
