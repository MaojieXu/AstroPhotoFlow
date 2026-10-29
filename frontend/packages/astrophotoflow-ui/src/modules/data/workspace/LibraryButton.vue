<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from './libraryControls'

const controls = inject(libraryControlsKey, undefined)
const { tooltip, type = 'button', variant = 'secondary' } = defineProps<{ tooltip?: string; type?: 'button' | 'submit' | 'reset'; variant?: 'secondary' | 'primary' | 'textonly' }>()
</script>

<template>
  <component :is="controls?.button ?? 'button'" :type="type" :variant="variant" :tooltip="tooltip" :title="controls ? undefined : tooltip">
    <slot />
    <template v-if="tooltip" #tooltip><span class="apf-hint-content">{{ tooltip }}</span></template>
  </component>
</template>
