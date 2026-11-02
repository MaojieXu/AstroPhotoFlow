<script setup lang="ts">
import { uiT } from '../../../core/i18n'

import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { useQueryAvailability } from '../../../core/query/availability'
import { useSelectLocalFiles } from './mutations'
import type { LocalImportFile } from '../api/contracts'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryDialog from '../components/LibraryDialog.vue'

const { open, mode } = defineProps<{open:boolean;mode:'files'|'folder'}>()
const emit = defineEmits<{close:[];selected:[files:LocalImportFile[],name:string,folder:boolean]}>()
const connectionReady = useQueryAvailability()
const chooser = useSelectLocalFiles()
const loading = chooser.isPending
const selectionError = ref('')
const error = computed(()=>selectionError.value || (chooser.error.value ? chooser.error.value instanceof Error ? chooser.error.value.message : uiT('apfUi.could_not_select_local_files') : ''))
let selection: AbortController | undefined

function cancelSelection() {
  selection?.abort()
  selection = undefined
  chooser.reset()
}

function close() {
  cancelSelection()
  emit('close')
}

async function choose() {
  if (!connectionReady.value || selection) return
  const controller = new AbortController()
  selection = controller
  selectionError.value = ''
  try {
    const result = await chooser.mutateAsync({mode,signal:controller.signal})
    if (selection !== controller || controller.signal.aborted || !open) return
    if (result.cancelled) close()
    else if (!result.files.length) selectionError.value = uiT('apfUi.no_supported_asset_files_at_the_selected_folder_level')
    else emit('selected', result.files, result.name ?? '', result.folder)
  } catch {
    // The mutation owns request diagnostics; cancelled sessions are reset.
  } finally {
    if (selection === controller) selection = undefined
  }
}

watch(() => open, value => { if (value) void choose(); else cancelSelection() }, {immediate:true})
watch(connectionReady, ready => { if (!ready && open) close() }, {flush:'sync'})
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
