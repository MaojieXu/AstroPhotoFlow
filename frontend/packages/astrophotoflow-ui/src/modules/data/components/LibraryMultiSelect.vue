<script setup lang="ts">
import { computed, inject } from 'vue'
import { libraryControlsKey } from '../workspace/libraryControls'

const controls = inject(libraryControlsKey, undefined)
const model = defineModel<string[]>({required:true})
const { label, options, disabled = false } = defineProps<{label:string;options:Array<{value:string;name:string}>;disabled?:boolean}>()
const selected = computed({get:()=>options.filter(option=>model.value.includes(option.value)),set:(value:Array<{value:string;name:string}>)=>{model.value=value.map(option=>option.value)}})
</script>

<template>
  <component :is="controls.multiSelect" v-if="controls" v-model="selected" class="apf-equipment-select" :label="label" :options="options" size="md" show-search-box show-selected-count show-clear-button :disabled="disabled" :popover-max-width="'min(320px, calc(100vw - 32px))'" :content-style="{overflowWrap:'anywhere'}" />
  <select v-else v-model="model" multiple :aria-label="label" :disabled="disabled"><option v-for="option in options" :key="option.value" :value="option.value">{{option.name}}</option></select>
</template>
