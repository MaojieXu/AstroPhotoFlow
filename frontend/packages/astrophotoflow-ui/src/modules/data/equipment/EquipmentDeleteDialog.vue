<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useEquipmentDeletePreview, useDeleteEquipmentEntries } from './mutations'
import type { EquipmentDeleteSelection, ManagementTrashPreviewOut } from '../../../generated/api/types.gen'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryDialog from '../components/LibraryDialog.vue'

export type EquipmentDeleteItem = EquipmentDeleteSelection['items'][number]
const props = defineProps<{workspaceId:string;viewKey:string;items?:EquipmentDeleteItem[]}>()
const emit = defineEmits<{close:[];deleted:[]}>()
const previewWrite=useEquipmentDeletePreview()
const deletion=useDeleteEquipmentEntries()
const preview = ref<ManagementTrashPreviewOut>()
const loading = previewWrite.isPending
const busy = deletion.isPending
const error = computed(()=>{const cause=previewWrite.error.value??deletion.error.value;return cause instanceof Error?cause.message:cause?uiT('apfUi.could_not_read_deletion_impact'):''})
const context=shallowRef({})
async function loadPreview() {
  const current = context.value = {}
  preview.value = undefined; previewWrite.reset();deletion.reset()
  if (!props.items) return
  try {
    const result = await previewWrite.mutateAsync({items:props.items.map(item=>({...item}))})
    if (current === context.value) preview.value = result
  } catch {/* Mutation diagnostic belongs to the current scope. */}
}
watch([()=>props.workspaceId,()=>props.viewKey,()=>props.items],()=>{void loadPreview()},{immediate:true,deep:true,flush:'sync'})
onBeforeUnmount(()=>{context.value={}})
async function remove() {
  if (!preview.value || !props.items || busy.value) return
  const current=context.value
  const workspaceId=props.workspaceId
  const body={items:props.items.map(item=>({...item})),preview_fingerprint:preview.value.preview_fingerprint}
  deletion.reset()
  try {
    await deletion.mutateAsync({workspaceId,body})
    if(current!==context.value)return
    emit('deleted'); emit('close')
  } catch {
    if(current!==context.value)return
    preview.value = undefined

  }
}
</script>

<template>
  <LibraryDialog :open="!!items" :title="$t('apfUi.confirm_deletion')" :busy="busy" @close="emit('close')">
    <div class="apf-equipment-dialog-body">
      <p>{{ $t('apfUi.deletion_cannot_be_undone_existing_assets_and_accepted_tasks_retain_th') }}</p>
      <p v-if="loading" role="status">{{ $t('apfUi.reading_deletion_impact') }}</p>
      <p v-if="error" role="alert">{{error}}</p>
      <template v-if="preview">
        <ul><li v-for="item in preview.items" :key="item.entry_type+item.id">{{item.name}}</li></ul>
        <section v-for="dependency in preview.dependencies" :key="dependency.id+dependency.kind">
          <h3>{{dependency.name}} · {{dependency.count}}</h3>
          <ul><li v-for="name in dependency.references" :key="name">{{name}}</li></ul>
        </section>
      </template>
    </div>
      <footer class="apf-equipment-dialog-footer">
        <LibraryButton type="button" :disabled="busy" @click="emit('close')">{{ $t('apfUi.cancel') }}</LibraryButton>
        <LibraryButton v-if="error" type="button" :disabled="loading||busy" @click="loadPreview">{{ $t('apfUi.read_impact_again') }}</LibraryButton>
        <LibraryButton type="button" :disabled="!preview||loading||busy" @click="remove">{{busy?$t('apfUi.deleting'):$t('apfUi.confirm_deletion')}}</LibraryButton>
      </footer>
  </LibraryDialog>
</template>
