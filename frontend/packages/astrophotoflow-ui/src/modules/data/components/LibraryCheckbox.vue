<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from '../workspace/libraryControls'

const controls = inject(libraryControlsKey, undefined)
const model = defineModel<boolean>({required:true})
const { label, disabled = false, indeterminate = false } = defineProps<{label:string;disabled?:boolean;indeterminate?:boolean}>()
</script>

<template>
  <component :is="controls.checkbox" v-if="controls?.checkbox" :model-value="indeterminate?'indeterminate':model" :aria-label="label" :disabled="disabled" @update:model-value="model=$event===true" />
  <input v-else type="checkbox" :aria-label="label" :checked="model" :indeterminate="indeterminate" :aria-checked="indeterminate?'mixed':model" :disabled="disabled" @change="model=($event.target as HTMLInputElement).checked" />
</template>
