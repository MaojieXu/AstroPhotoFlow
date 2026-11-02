<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from '../workspace/libraryControls'

const controls = inject(libraryControlsKey, undefined)
const model = defineModel<string | number | null | undefined>()
</script>

<template>
  <component :is="controls.input" v-if="controls" :model-value="model ?? ''" @update:model-value="model = $event" />
  <input v-else v-model="model" />
</template>
