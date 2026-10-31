<script setup lang="ts">
import { inject } from 'vue'
import { libraryControlsKey } from './libraryControls'
import LibraryButton from './LibraryButton.vue'

const controls = inject(libraryControlsKey, undefined)
const { open, title, label, busy = false } = defineProps<{open:boolean;title:string;label?:string;busy?:boolean}>()
const emit = defineEmits<{close:[]}>()
function requestClose(){if(!busy)emit('close')}
</script>

<template>
  <component :is="controls.dialog" v-if="controls" :open="open" :title="title" :label="label" :busy="busy" @close="requestClose"><slot /></component>
  <div v-else-if="open" class="apf-equipment-modal-backdrop" @click.self="requestClose" @keydown.esc.stop="requestClose">
    <section class="apf-equipment-dialog" role="dialog" aria-modal="true" :aria-label="label??title">
      <header class="apf-equipment-dialog-header"><h2>{{title}}</h2><LibraryButton type="button" :aria-label="$t('apfUi.close_form')" :disabled="busy" @click="requestClose">×</LibraryButton></header>
      <slot />
    </section>
  </div>
</template>
