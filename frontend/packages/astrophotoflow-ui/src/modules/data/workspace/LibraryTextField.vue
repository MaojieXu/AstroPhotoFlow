<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from './libraryControls'
import LibraryInfo from './LibraryInfo.vue'
import LibraryInput from './LibraryInput.vue'

const controls = inject(libraryControlsKey, undefined)
const model = defineModel<string>()
const { id, name, hint, disabled = false, required = false, autofocus = false } = defineProps<{ id: string; name: string; hint?: string; disabled?: boolean; required?: boolean; autofocus?:boolean }>()
</script>

<template>
  <component :is="controls.formItem" v-if="controls" :id="id" :item="{ id, name, type: 'text', attrs: { disabled, required, autofocus } }" :form-value="model" @update:form-value="model = String($event)">
    <template #name-suffix><LibraryInfo v-if="hint" :text="hint" :label="name" /></template>
  </component>
  <label v-else :for="id">{{ name }}<LibraryInfo v-if="hint" :text="hint" :label="name" /><LibraryInput :id="id" v-model="model" :disabled="disabled" :required="required" :autofocus="autofocus" /></label>
</template>
