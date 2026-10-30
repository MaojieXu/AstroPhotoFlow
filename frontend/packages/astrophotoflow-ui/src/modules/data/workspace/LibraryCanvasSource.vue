<script setup lang="ts">
import { inject } from 'vue'

import type { CanvasDataRequest } from '../api/canvas'
import { libraryControlsKey } from './libraryControls'

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
const controls = inject(libraryControlsKey, undefined)
</script>

<template>
  <component
    :is="controls?.canvasSource ?? as"
    :source="controls?.canvasSource ? source : undefined"
    :as="controls?.canvasSource ? as : undefined"
    :click-target="controls?.canvasSource ? clickTarget : undefined"
    @click="emit('click', $event)"
  >
    <slot />
  </component>
</template>
