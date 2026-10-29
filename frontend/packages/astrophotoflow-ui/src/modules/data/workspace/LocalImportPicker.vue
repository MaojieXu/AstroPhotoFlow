<script setup lang="ts">
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
    else if (!result.files.length) error.value = '所选文件夹当前层没有支持的素材文件。'
    else emit('selected', result.files, result.name ?? '', result.folder)
  } catch (cause) {
    if (current === generation) error.value = cause instanceof Error ? cause.message : '本机文件选择失败。'
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
  <LibraryDialog :open="open" :title="mode==='folder'?'选择本机文件夹':'选择本机文件'" @close="close">
    <div class="apf-equipment-dialog-body">
      <p v-if="loading" role="status">请在系统选择窗口中选择{{mode==='folder'?'文件夹':'一个或多个文件'}}。</p>
      <p v-if="mode==='folder'">仅导入当前层支持的文件，不包含子文件夹。</p>
      <p v-if="error" role="alert">{{error}}</p>
    </div>
    <footer class="apf-equipment-dialog-footer">
      <LibraryButton @click="close">取消</LibraryButton>
      <LibraryButton v-if="error" variant="primary" @click="choose">重新选择</LibraryButton>
    </footer>
  </LibraryDialog>
</template>
