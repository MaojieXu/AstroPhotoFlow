<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from '../workspace/libraryControls'
const controls = inject(libraryControlsKey, undefined)
const model = defineModel<string | null | undefined>()
</script>

<template>
  <component :is="controls?.textarea??'textarea'" :model-value="controls?model??'':undefined" :value="controls?undefined:model??''" rows="2" @update:model-value="model=$event" @input="!controls&&(model=($event.target as HTMLTextAreaElement).value)" />
</template>
