<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from './libraryControls'

const controls = inject(libraryControlsKey, undefined)
const model = defineModel<string | number | null | undefined>()
const { label, options, disabled = false } = defineProps<{label:string;options:Array<{value:string;name:string}>;disabled?:boolean}>()
</script>

<template>
  <component :is="controls.select" v-if="controls" class="apf-equipment-select" :model-value="model??''" :label="label" :options="options" size="md" :disabled="disabled" :popover-max-width="'min(320px, calc(100vw - 32px))'" @update:model-value="model=$event" />
  <select v-else v-model="model" :aria-label="label" :disabled="disabled"><option v-for="option in options" :key="option.value" :value="option.value">{{option.name}}</option></select>
</template>
