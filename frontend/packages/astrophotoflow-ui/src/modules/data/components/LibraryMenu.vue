<script setup lang="ts">
import { inject, ref } from 'vue'
import LibraryButton from './LibraryButton.vue'
import { libraryControlsKey } from '../workspace/libraryControls'
import type { LibraryMenuItem } from '../workspace/libraryControls'

const controls = inject(libraryControlsKey, undefined)
const { items } = defineProps<{items:LibraryMenuItem[]}>()
const open = ref(false)
const details = ref<HTMLDetailsElement>()
function close(restoreFocus=false){
  open.value=false
  if(details.value){details.value.open=false;if(restoreFocus)details.value.querySelector('summary')?.focus()}
}
function dismiss(event:PointerEvent){
  if(!controls?.menu&&event.target instanceof Node&&!details.value?.contains(event.target))close()
}
function selectOption(item:LibraryMenuItem,event:Event){
  const value=(event.target as HTMLSelectElement).value
  close()
  item.radioGroup?.options.find(option=>option.value===value)?.command()
}
defineExpose({close,dismiss})
</script>

<template>
  <component :is="controls.menu" v-if="controls?.menu" v-model:open="open" :items="items" align="end">
    <template #trigger><LibraryButton type="button" :aria-label="$t('apfUi.more_actions')" :tooltip="$t('apfUi.more_actions')"><i class="icon-[lucide--ellipsis] size-4" aria-hidden="true" /></LibraryButton></template>
  </component>
  <details v-else ref="details" class="apf-equipment-more apf-workspace-more" @keydown.esc.stop.prevent="close(true)" @focusout="!details?.contains($event.relatedTarget as Node|null)&&close()">
    <summary :aria-label="$t('apfUi.more_actions')" :title="$t('apfUi.more_actions')">…</summary>
    <div><template v-for="item in items" :key="item.label">
      <label v-if="item.radioGroup">{{item.label}}<select :aria-label="item.label" :value="item.radioGroup.value" :disabled="item.disabled" @change="selectOption(item,$event)"><option v-for="option in item.radioGroup.options" :key="option.value" :value="option.value">{{option.label}}</option></select></label>
      <LibraryButton v-else type="button" :disabled="item.disabled" @click="close();item.command()">{{item.label}}</LibraryButton>
    </template></div>
  </details>
</template>
