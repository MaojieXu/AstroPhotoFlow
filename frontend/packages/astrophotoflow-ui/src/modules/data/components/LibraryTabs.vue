<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from '../workspace/libraryControls'

const controls = inject(libraryControlsKey, undefined)
const { value, options, label } = defineProps<{value:string;options:Array<{value:string;label:string}>;label:string}>()
const emit = defineEmits<{change:[value:string]}>()
</script>

<template>
  <component :is="controls.tabs" v-if="controls?.tabs&&controls.tabsList&&controls.tabsTrigger" :model-value="value" @update:model-value="emit('change',String($event))">
    <component :is="controls.tabsList" :aria-label="label" style="justify-content:flex-start">
      <component :is="controls.tabsTrigger" v-for="option in options" :key="option.value" :value="option.value" :aria-current="value===option.value?'page':undefined">{{option.label}}</component>
    </component>
  </component>
  <div v-else role="tablist" :aria-label="label"><button v-for="option in options" :key="option.value" type="button" role="tab" :aria-selected="value===option.value" :aria-current="value===option.value?'page':undefined" @click="emit('change',option.value)">{{option.label}}</button></div>
</template>
