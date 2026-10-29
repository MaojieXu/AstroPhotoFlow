import type { Ref } from 'vue'
import { canvasDataRequestSchema } from '@astrophotoflow/ui'

import { useSharedCanvasPositionConversion } from '@/composables/element/useCanvasPositionConversion'
import { usePragmaticDroppable } from '@/composables/usePragmaticDragAndDrop'
import type { LGraphNode, Point } from '@/lib/litegraph/src/litegraph'
import { LiteGraph } from '@/lib/litegraph/src/litegraph'
import { withNodeAddSource } from '@/platform/telemetry/nodeAdded/nodeAddSource'
import { useWorkflowService } from '@/platform/workflow/core/services/workflowService'
import { ComfyWorkflow } from '@/platform/workflow/management/stores/workflowStore'
import { app as comfyApp } from '@/scripts/app'
import { useLitegraphService } from '@/services/litegraphService'
import { ComfyModelDef } from '@/stores/modelStore'
import type { ModelNodeProvider } from '@/stores/modelToNodeStore'
import { useModelToNodeStore } from '@/stores/modelToNodeStore'
import { ComfyNodeDefImpl } from '@/stores/nodeDefStore'
import type { RenderedTreeExplorerNode } from '@/types/treeExplorerTypes'
import { isSelectOnly } from '@/utils/litegraphUtil'
import { matchesWidgetName } from '@/utils/widgetBinding'
import { addLibraryDataToCanvas } from '@/platform/astrophotoflow/canvasDataBridge'

export const useCanvasDrop = (dropTargetRef: Ref<HTMLElement | null>) => {
  const modelToNodeStore = useModelToNodeStore()
  const litegraphService = useLitegraphService()
  const workflowService = useWorkflowService()

  usePragmaticDroppable(() => dropTargetRef.value, {
    getDropEffect: (args): Exclude<DataTransfer['dropEffect'], 'none'> =>
      args.source.data.type === 'tree-explorer-node' || args.source.data.type === 'apf-canvas-data' ? 'copy' : 'move',
    onDrop: async (event) => {
      if (isSelectOnly(comfyApp.canvas)) return
      const loc = event.location.current.input
      const dndData = event.source.data

      if (dndData.type === 'apf-canvas-data') {
        const source = canvasDataRequestSchema.safeParse(dndData.source)
        if (source.success) {
          const position = useSharedCanvasPositionConversion().clientPosToCanvasPos([loc.clientX, loc.clientY])
          await addLibraryDataToCanvas(source.data, position)
        }
        return
      }

      if (dndData.type === 'tree-explorer-node') {
        const node = dndData.data as RenderedTreeExplorerNode
        const conv = useSharedCanvasPositionConversion()
        const basePos = conv.clientPosToCanvasPos([loc.clientX, loc.clientY])

        if (node.data instanceof ComfyNodeDefImpl) {
          const nodeDef = node.data
          const pos: Point = [...basePos]
          pos[1] += LiteGraph.NODE_TITLE_HEIGHT
          withNodeAddSource('sidebar_drag', () =>
            litegraphService.addNodeOnGraph(nodeDef, { pos })
          )
        } else if (node.data instanceof ComfyModelDef) {
          const model = node.data
          const pos = basePos
          const nodeAtPos = comfyApp.canvas.graph?.getNodeOnPos(pos[0], pos[1])
          let targetProvider: ModelNodeProvider | null = null
          let targetGraphNode: LGraphNode | null = null
          if (nodeAtPos) {
            const providers = modelToNodeStore.getAllNodeProviders(
              model.directory
            )
            for (const provider of providers) {
              if (provider.nodeDef.name === nodeAtPos.comfyClass) {
                targetGraphNode = nodeAtPos
                targetProvider = provider
              }
            }
          }
          if (!targetGraphNode) {
            const provider = modelToNodeStore.getNodeProvider(model.directory)
            if (provider) {
              targetGraphNode = withNodeAddSource('sidebar_drag', () =>
                litegraphService.addNodeOnGraph(provider.nodeDef, { pos })
              )
              targetProvider = provider
            }
          }
          if (targetGraphNode && targetProvider) {
            const { key } = targetProvider
            const widget = targetGraphNode.widgets?.find((widget) =>
              matchesWidgetName(widget.name, key)
            )
            if (widget) {
              widget.value = model.file_name
            }
          }
        } else if (node.data instanceof ComfyWorkflow) {
          const workflow = node.data
          await workflowService.insertWorkflow(workflow, { position: basePos })
        }
      }
    }
  })
}
