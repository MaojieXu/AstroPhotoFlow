<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { ref, watch } from 'vue'
import { z } from 'zod'
import { assetApi } from '../api/index'
import LibraryButton from './LibraryButton.vue'
import LibraryDialog from './LibraryDialog.vue'

export type EquipmentDeleteItem = {entry_type:'equipment'|'equipment_setup'|'capture_preset';id:string;revision:number}
const props = defineProps<{items?:EquipmentDeleteItem[]}>()
const emit = defineEmits<{close:[];deleted:[]}>()
const previewSchema = z.object({
  items:z.array(z.object({entry_type:z.string(),id:z.string(),name:z.string(),revision:z.number().int(),updated_at:z.string(),details:z.record(z.string(),z.unknown())}).strict()),
  dependencies:z.array(z.object({entry_type:z.string(),id:z.string(),kind:z.string(),name:z.string(),count:z.number().int(),blocks_delete:z.boolean(),references:z.array(z.string())}).strict()),
  blocked:z.boolean(),preview_fingerprint:z.string()
}).strict()
const preview = ref<z.infer<typeof previewSchema>>()
const loading = ref(false)
const busy = ref(false)
const error = ref('')
let generation = 0
async function loadPreview() {
  const current = ++generation
  preview.value = undefined; error.value = ''
  if (!props.items) return
  loading.value = true
  try {
    const result = await assetApi.send('/astrophotoflow/api/v1/equipment-management/delete-preview',previewSchema,'POST',{items:props.items})
    if (current === generation) preview.value = result
  } catch (cause) {
    if (current === generation) error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_read_deletion_impact')
  } finally {if (current === generation) loading.value = false}
}
watch(()=>props.items,()=>{void loadPreview()},{immediate:true})
async function remove() {
  if (!preview.value || !props.items || busy.value) return
  busy.value = true; error.value = ''
  try {
    await assetApi.send('/astrophotoflow/api/v1/equipment-management/delete',z.object({deleted_count:z.number().int(),detached_material_count:z.number().int()}).strict(),'POST',
      {items:props.items,preview_fingerprint:preview.value.preview_fingerprint})
    emit('deleted'); emit('close')
  } catch (cause) {
    preview.value = undefined
    error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_delete_check_the_current_record_before_retrying')
  } finally {busy.value = false}
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
