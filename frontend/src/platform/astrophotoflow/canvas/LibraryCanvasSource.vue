<script setup lang="ts">
import type { CanvasDataRequest } from '@astrophotoflow/ui'
import { computed, useTemplateRef } from 'vue'

import NodePreviewCard from '@/components/node/NodePreviewCard.vue'
import { useNodeDragToCanvas } from '@/composables/node/useNodeDragToCanvas'
import { useNodePreviewAndDrag } from '@/composables/node/useNodePreviewAndDrag'
import { useNodeDefStore } from '@/stores/nodeDefStore'

import { addLibraryDataToCanvas } from './dataBridge'

defineOptions({ inheritAttrs: false })
const {
  source,
  as = 'span',
  clickTarget
} = defineProps<{
  source?: CanvasDataRequest
  as?: 'span' | 'tr'
  clickTarget?: string
}>()
const emit = defineEmits<{ click: [event: MouseEvent] }>()
const definitions = useNodeDefStore()
const nodeDef = computed(() =>
  source ? definitions.nodeDefsByName.APF_DATA_REFERENCE : undefined
)
const preview = useTemplateRef<HTMLElement>('preview')
const { startDrag, cancelDrag } = useNodeDragToCanvas()
function options() {
  const selected = source
  return {
    onPlace: (pos: [number, number]) => {
      if (selected) void addLibraryDataToCanvas(selected, pos)
    }
  }
}
const {
  showPreview,
  nodePreviewStyle,
  handleMouseEnter,
  handleMouseLeave,
  handleDragStart: startNativeDrag,
  handleDragEnd
} = useNodePreviewAndDrag(nodeDef, preview, undefined, options)

function isEditor(target: EventTarget | null) {
  return (
    target instanceof Element &&
    Boolean(target.closest('input, textarea, select, [contenteditable="true"]'))
  )
}

function place(event: MouseEvent) {
  if (
    !nodeDef.value ||
    event.detail > 1 ||
    isEditor(event.target) ||
    (clickTarget &&
      !(event.target instanceof Element && event.target.closest(clickTarget)))
  ) {
    emit('click', event)
    return
  }
  event.stopPropagation()
  startDrag(nodeDef.value, options())
}

function handleDragStart(event: DragEvent) {
  if (isEditor(event.target)) return
  startNativeDrag(event)
}
</script>

<template>
  <component
    :is="as"
    v-bind="$attrs"
    :class="[
      as === 'span' ? 'inline-flex' : undefined,
      nodeDef ? 'cursor-grab select-none active:cursor-grabbing' : undefined
    ]"
    :draggable="Boolean(nodeDef)"
    @mousedown.capture="cancelDrag"
    @click="place"
    @dblclick.capture="cancelDrag"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
  >
    <slot />
  </component>
  <Teleport v-if="showPreview && nodeDef" to="body">
    <div ref="preview" :style="nodePreviewStyle">
      <NodePreviewCard :node-def="nodeDef" :show-inputs-and-outputs="false" />
    </div>
  </Teleport>
</template>
