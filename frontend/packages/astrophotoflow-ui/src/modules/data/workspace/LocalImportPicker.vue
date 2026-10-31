<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { onBeforeUnmount, ref, watch } from 'vue'

import { assetApi } from '../api/index'
import { localSelectionSchema } from '../api/contracts'
import type { LocalImportFile } from '../api/contracts'
import LibraryButton from './LibraryButton.vue'
import LibraryDialog from './LibraryDialog.vue'

const { open, mode } = defineProps<{open:boolean;mode:'files'|'folder'}>()
const emit = defineEmits<{close:[];selected:[files:LocalImportFile[],name:string,folder:boolean]}>()
const loading = ref(false)
const error = ref('')
let generation = 0
let selection: AbortController | undefined

function cancelSelection() {
  generation++
  selection?.abort()
  selection = undefined
  loading.value = false
}

function close() {
  cancelSelection()
  emit('close')
}

async function choose() {
  if (loading.value) return
  const current = ++generation
  const controller = new AbortController()
  selection = controller
  loading.value = true
  error.value = ''
  try {
    const result = await assetApi.send('/astrophotoflow/api/v1/imports/select-local', localSelectionSchema, 'POST', {mode}, {signal:controller.signal})
    if (current !== generation || !open) return
    if (result.cancelled) close()
    else if (!result.files.length) error.value = uiT('apfUi.no_supported_asset_files_at_the_selected_folder_level')
    else emit('selected', result.files, result.name ?? '', result.folder)
  } catch (cause) {
    if (current === generation) error.value = cause instanceof Error ? cause.message : uiT('apfUi.could_not_select_local_files')
  } finally {
    if (current === generation) {
      loading.value = false
      selection = undefined
    }
  }
}

watch(() => open, value => { if (value) void choose(); else cancelSelection() }, {immediate:true})
onBeforeUnmount(cancelSelection)
</script>

<template>
  <LibraryDialog :open="open" :title="mode==='folder'?$t('apfUi.select_local_folder'):$t('apfUi.select_local_files')" @close="close">
    <div class="apf-equipment-dialog-body">
      <p v-if="loading" role="status">{{ $t('apfUi.select_value_in_the_system_dialog', { p0: mode==='folder'?$t('apfUi.folder'):$t('apfUi.one_or_more_files') }) }}</p>
      <p v-if="mode==='folder'">{{ $t('apfUi.only_supported_files_in_this_folder_are_imported_subfolders_are_exclud') }}</p>
      <p v-if="error" role="alert">{{error}}</p>
    </div>
    <footer class="apf-equipment-dialog-footer">
      <LibraryButton @click="close">{{ $t('apfUi.cancel') }}</LibraryButton>
      <LibraryButton v-if="error" variant="primary" @click="choose">{{ $t('apfUi.choose_again') }}</LibraryButton>
    </footer>
  </LibraryDialog>
</template>
