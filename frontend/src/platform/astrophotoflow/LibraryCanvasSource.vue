<script setup lang="ts">
import type { CanvasDataRequest } from '@astrophotoflow/ui'
import { useTemplateRef } from 'vue'

import { usePragmaticDraggable } from '@/composables/usePragmaticDragAndDrop'

const { source } = defineProps<{ source?: CanvasDataRequest }>()
const element = useTemplateRef<HTMLElement>('element')

usePragmaticDraggable(element, {
  canDrag: () => Boolean(source),
  getInitialData: () => ({ type: 'apf-canvas-data', source })
})
</script>

<template>
  <span ref="element" :class="source ? 'inline-flex cursor-grab' : 'inline-flex'">
    <slot />
  </span>
</template>
