<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from '../workspace/libraryControls'

const controls = inject(libraryControlsKey, undefined)
const model = defineModel<string | number | null | undefined>()
const { label, options, disabled = false, searchable = true, density = 'normal' } = defineProps<{label:string;options:Array<{value:string;name:string}>;disabled?:boolean;searchable?:boolean;density?:'normal'|'compact'}>()
</script>

<template>
  <component :is="controls.select" v-if="controls" class="apf-equipment-select" :model-value="model??''" :label="label" :options="options" size="md" :disabled="disabled" :searchable="searchable" :density="density" :popover-min-width="density==='compact'?'min(160px, calc(100vw - 32px))':undefined" :content-style="density==='compact'?{width:'180px'}:undefined" :popover-max-width="density==='compact'?'min(200px, calc(100vw - 32px))':'min(320px, calc(100vw - 32px))'" @update:model-value="model=$event" />
  <select v-else v-model="model" :aria-label="label" :disabled="disabled"><option v-for="option in options" :key="option.value" :value="option.value">{{option.name}}</option></select>
</template>
