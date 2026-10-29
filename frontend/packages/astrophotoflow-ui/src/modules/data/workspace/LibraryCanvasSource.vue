<script setup lang="ts">
import { inject } from 'vue'

import type { CanvasDataRequest } from '../api/canvas'
import { libraryControlsKey } from './libraryControls'

const { source } = defineProps<{ source?: CanvasDataRequest }>()
const controls = inject(libraryControlsKey, undefined)
</script>

<template>
  <component :is="controls?.canvasSource ?? 'span'" :source="source">
    <slot />
  </component>
</template>
