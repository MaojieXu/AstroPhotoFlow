<script setup lang="ts">
import { whenever } from '@vueuse/core'
import { onMounted, ref, shallowRef } from 'vue'

import { useCanvasStore } from '@/renderer/core/canvas/canvasStore'
import type { ComponentWidget, DOMWidget } from '@/scripts/domWidget'
import { isComponentWidget, isDOMWidget } from '@/scripts/domWidget'
import { resolveWidgetFromHostNode } from '@/renderer/extensions/vueNodes/widgets/utils/resolvePromotedWidget'
import type { NodeId } from '@/types/nodeId'
import type { SimplifiedWidget } from '@/types/simplifiedWidget'

// Button widgets don't have a v-model value, they trigger actions
const props = defineProps<{
  widget: SimplifiedWidget<undefined>
  nodeId: NodeId
}>()

const domEl = ref<HTMLElement>()
const componentWidget = shallowRef<ComponentWidget<string | object>>()

const canvasStore = useCanvasStore()
const { canvas } = canvasStore

function findDOMWidget(): DOMWidget<HTMLElement, object | string> | ComponentWidget<string | object> | undefined {
  const hostNode = canvas?.graph?.getNodeById(props.nodeId) ?? undefined
  const resolved = resolveWidgetFromHostNode(hostNode, props.widget.name)
  if (resolved && (isDOMWidget(resolved.widget) || (isComponentWidget(resolved.widget) && resolved.widget.options.surfaces?.canvas === 'never'))) return resolved.widget

  return undefined
}

function mountWidgetElement() {
  if (!domEl.value) return
  const widget = findDOMWidget()
  if (!widget) return
  if (isComponentWidget(widget)) {
    componentWidget.value = widget
    return
  }
  if (domEl.value.contains(widget.element)) return
  domEl.value.replaceChildren(widget.element)
}

onMounted(() => {
  mountWidgetElement()
})

whenever(() => !canvasStore.linearMode, mountWidgetElement)
</script>
<template>
  <div
    ref="domEl"
    class="flex flex-col *:flex-1"
    @pointerdown.stop
    @pointermove.stop
    @pointerup.stop
  >
    <component
      :is="componentWidget.component"
      v-if="componentWidget"
      :widget="componentWidget"
      :model-value="componentWidget.value"
      v-bind="componentWidget.props"
      :style="{ minHeight: `${componentWidget.computeLayoutSize?.(componentWidget.node).minHeight ?? 50}px` }"
      @update:model-value="componentWidget.value = $event"
    />
  </div>
</template>
