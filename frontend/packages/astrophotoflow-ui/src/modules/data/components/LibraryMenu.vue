<script setup lang="ts">
import { inject, ref } from 'vue'
import LibraryButton from './LibraryButton.vue'
import { libraryControlsKey } from '../workspace/libraryControls'
import type { LibraryMenuItem } from '../workspace/libraryControls'

defineOptions({ inheritAttrs: false })

const controls = inject(libraryControlsKey, undefined)
const { items } = defineProps<{items:LibraryMenuItem[]}>()
const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{ closeAutoFocus: [event: Event] }>()
const details = ref<HTMLDetailsElement>()
function close(restoreFocus=false){
  open.value=false
  if(restoreFocus)details.value?.querySelector('summary')?.focus()
}
function selectOption(item:LibraryMenuItem,event:Event){
  const value=(event.target as HTMLSelectElement).value
  close()
  item.radioGroup?.options.find(option=>option.value===value)?.command()
}
</script>

<template>
  <component :is="controls.menu" v-if="controls?.menu" v-model:open="open" :items="items" :modal="false" align="end" @close-auto-focus="emit('closeAutoFocus', $event)">
    <template #trigger><LibraryButton v-bind="$attrs" type="button" :aria-label="$t('apfUi.more_actions')" :tooltip="$t('apfUi.more_actions')"><i class="icon-[lucide--ellipsis] size-4" aria-hidden="true" /></LibraryButton></template>
  </component>
  <details v-else ref="details" v-bind="$attrs" :open="open" class="apf-equipment-more apf-workspace-more" @keydown.esc.stop.prevent="close(true)" @focusout="!details?.contains($event.relatedTarget as Node|null)&&close()">
    <summary :aria-label="$t('apfUi.more_actions')" :title="$t('apfUi.more_actions')" @click.prevent="open = !open">…</summary>
    <div><template v-for="item in items" :key="item.label">
      <label v-if="item.radioGroup">{{item.label}}<select :aria-label="item.label" :value="item.radioGroup.value" :disabled="item.disabled" @change="selectOption(item,$event)"><option v-for="option in item.radioGroup.options" :key="option.value" :value="option.value">{{option.label}}</option></select></label>
      <LibraryButton v-else type="button" :disabled="item.disabled" @click="close();item.command()">{{item.label}}</LibraryButton>
    </template></div>
  </details>
</template>
