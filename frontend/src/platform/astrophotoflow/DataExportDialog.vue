<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { createDataExportClient } from '@astrophotoflow/ui'
import type { DataResult, ExportReceipt, MediaState } from '@astrophotoflow/ui'
import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'
import Dialog from '@/components/ui/dialog/Dialog.vue'
import DialogContent from '@/components/ui/dialog/DialogContent.vue'
import DialogHeader from '@/components/ui/dialog/DialogHeader.vue'
import DialogOverlay from '@/components/ui/dialog/DialogOverlay.vue'
import DialogPortal from '@/components/ui/dialog/DialogPortal.vue'
import DialogTitle from '@/components/ui/dialog/DialogTitle.vue'

const props = defineProps<{ result: DataResult; index: number; target: 'library' | 'local'; media?: MediaState }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const controller = new AbortController()
const client = createDataExportClient((path, init) => fetch(path, { ...init, signal: controller.signal }))
const formats = ['original', 'fits', 'xisf', 'tiff', 'png', 'jpeg']
const precisions: Record<string, string[]> = {
  original: ['original'], fits: ['uint8', 'uint16', 'uint32', 'int16', 'int32', 'float32', 'float64'],
  xisf: ['uint8', 'uint16', 'uint32', 'float32', 'float64'], tiff: ['uint8', 'uint16', 'uint32', 'int16', 'int32', 'float32', 'float64'],
  png: ['uint8', 'uint16'], jpeg: ['uint8']
}
const format = ref('original')
const precision = ref('original')
const conversion = ref('preserve')
const name = ref('Data')
const scope = ref('current')
const rangeLow = ref('0')
const rangeHigh = ref('1')
const hdu = ref(props.media?.selection.hdu_index?.toString() ?? '')
const frame = ref(props.media?.selection.frame_index?.toString() ?? '')
const quality = ref('95')
const receipt = ref<ExportReceipt>()
const pendingBody = ref<Record<string, unknown>>()
const requestId = ref('')
const busy = ref(false)
const error = ref('')
const active = computed(() => !!receipt.value && ['queued', 'running', 'cancelling'].includes(receipt.value.state))
const storageKey = `apf-export:${props.result.run_id}:${props.result.execution_id}:${props.target}`
let timer: ReturnType<typeof setTimeout> | undefined
const label = (key: string) => t(`astrophotoflow.dataExport.${key}`)
watch(format, value => {
  precision.value = value === 'original' ? 'original' : value === 'png' ? 'uint16' : value === 'jpeg' ? 'uint8' : 'float32'
  if (value === 'original') conversion.value = 'preserve'
})
watch(precision, value => { if (value.startsWith('float') && conversion.value === 'round') conversion.value = 'preserve' })

async function refresh() {
  if (!requestId.value) return
  clearTimeout(timer)
  try {
    receipt.value = await client.status(requestId.value)
    error.value = ''
    if (active.value) timer = setTimeout(() => void refresh(), 2000)
  } catch (cause) {
    if (!controller.signal.aborted) error.value = String(cause)
  }
}

function frozenSettings() {
  const settings: Record<string, unknown> = { format: format.value, precision: precision.value, conversion: conversion.value, jpeg_quality: Number(quality.value) }
  if (conversion.value === 'normalize') settings.value_range = [Number(rangeLow.value), Number(rangeHigh.value)]
  if (conversion.value === 'display') {
    const recipe = props.media?.display_recipe
    if (recipe?.auto_stretch) settings.auto_stretch = recipe.auto_stretch
    else if (recipe?.display_range) settings.display_range = recipe.display_range
    else if (typeof recipe?.stretch_low === 'number' && typeof recipe?.stretch_high === 'number') settings.display_range = [recipe.stretch_low, recipe.stretch_high]
    else if (props.media?.selection.display_range) settings.display_range = props.media.selection.display_range
    else throw new Error(label('displayRequired'))
  }
  return settings
}

async function submit() {
  if (busy.value || active.value || receipt.value) return
  busy.value = true
  error.value = ''
  try {
    if (!pendingBody.value) {
      const indexes = scope.value === 'all' ? props.result.members.map((_, index) => index) : [props.index]
      const settings = frozenSettings()
      const selections: Record<string, unknown> = {}
      if (format.value !== 'original') {
        for (const index of indexes) selections[String(index)] = {
          ...(indexes.length === 1 ? props.media?.selection : props.result.members[index]?.selection),
          ...(hdu.value !== '' ? { hdu_index: Number(hdu.value) } : {}),
          ...(frame.value !== '' ? { frame_index: Number(frame.value), media_time: null } : {})
        }
      }
      let destination: string | undefined
      if (props.target === 'local') {
        const suffix = format.value === 'original' ? props.result.members[props.index]?.name.match(/\.(?:fits\.fz|fit\.fz|fts\.fz|[^.]+)$/i)?.[0] ?? '.fits' : ({ fits: '.fits', xisf: '.xisf', tiff: '.tif', png: '.png', jpeg: '.jpg' } as Record<string, string>)[format.value]
        const selected = await client.choose({ mode: indexes.length > 1 ? 'folder' : 'file', suggested_name: name.value + suffix })
        if (!selected.path) return
        destination = selected.path
      }
      requestId.value = crypto.randomUUID()
      pendingBody.value = { request_id: requestId.value, source: { run_id: props.result.run_id, execution_id: props.result.execution_id },
        member_indexes: indexes, target: props.target, name: name.value, settings, selections,
        ...(destination ? { destination } : {}) }
      sessionStorage.setItem(storageKey, JSON.stringify(pendingBody.value))
    }
    receipt.value = await client.submit(pendingBody.value)
    if (active.value) timer = setTimeout(() => void refresh(), 1000)
  } catch (cause) {
    if (!controller.signal.aborted) error.value = String(cause)
  } finally { busy.value = false }
}

async function cancel() {
  try { receipt.value = await client.cancel(requestId.value); await refresh() }
  catch (cause) { error.value = String(cause) }
}
function newExport() {
  receipt.value = undefined; pendingBody.value = undefined; requestId.value = ''; error.value = ''
  sessionStorage.removeItem(storageKey)
}
onMounted(() => {
  const saved = sessionStorage.getItem(storageKey)
  if (!saved) return
  try {
    pendingBody.value = JSON.parse(saved)
    requestId.value = String(pendingBody.value?.request_id ?? '')
    void refresh()
  } catch { error.value = label('receiptUnavailable') }
})
onBeforeUnmount(() => { clearTimeout(timer); controller.abort() })
</script>

<template>
  <Dialog :open="true" @update:open="!$event && emit('close')">
    <DialogPortal><DialogOverlay /><DialogContent size="md" class="max-h-[85vh] overflow-y-auto" :aria-describedby="undefined">
      <DialogHeader><DialogTitle>{{ label(target === 'library' ? 'saveLibrary' : 'saveLocal') }}</DialogTitle></DialogHeader>
      <p class="text-sm text-muted-foreground">{{ label('copyOnly') }}</p>
      <fieldset :disabled="busy || !!pendingBody" class="grid grid-cols-2 gap-3 border-0 p-0 text-sm">
        <label class="col-span-2">{{ label('name') }}<Input v-model="name" /></label>
        <label>{{ label('scope') }}<select v-model="scope" :aria-label="label('scope')" class="w-full rounded border p-2"><option value="current">{{ label('current') }}</option><option value="all">{{ label('all') }} ({{ result.members.length }})</option></select></label>
        <label>{{ label('format') }}<select v-model="format" :aria-label="label('format')" class="w-full rounded border p-2"><option v-for="value in formats" :key="value" :value="value">{{ value === 'original' ? label('original') : value.toUpperCase() }}</option></select></label>
        <label>{{ label('precision') }}<select v-model="precision" :aria-label="label('precision')" class="w-full rounded border p-2"><option v-for="value in precisions[format]" :key="value" :value="value">{{ label(value) }}</option></select></label>
        <label>{{ label('conversion') }}<select v-model="conversion" :aria-label="label('conversion')" class="w-full rounded border p-2" :disabled="format === 'original'"><option v-for="value in ['preserve', 'round', 'normalize', 'display']" :key="value" :value="value" :disabled="value === 'round' && precision.startsWith('float')">{{ label(value) }}</option></select></label>
        <template v-if="conversion === 'normalize'"><label>{{ label('low') }}<Input v-model="rangeLow" type="number" /></label><label>{{ label('high') }}<Input v-model="rangeHigh" type="number" /></label></template>
        <template v-if="format !== 'original'"><label>{{ label('hdu') }}<Input v-model="hdu" type="number" min="0" /></label><label>{{ label('frame') }}<Input v-model="frame" type="number" min="0" /></label></template>
        <label v-if="format === 'jpeg'">{{ label('quality') }}<Input v-model="quality" type="number" min="1" max="100" /></label>
      </fieldset>
      <p v-if="requestId" class="break-all text-xs">{{ label('receipt') }}: {{ requestId }}</p>
      <p v-if="error" role="alert" class="text-error">{{ error }}</p>
      <template v-if="receipt">
        <p role="status">{{ label(receipt.state) }} · {{ receipt.results.filter(item => item.state === 'completed').length }} / {{ receipt.member_indexes.length }}</p>
        <ul class="max-h-56 overflow-auto text-xs"><li v-for="item in receipt.results" :key="item.member_index" class="mb-2 break-all">{{ item.member_index + 1 }} · {{ label(item.state) }}<br />{{ item.path || item.registration_task_id }}<span v-if="item.error" class="text-error"> {{ item.error.code }}: {{ item.error.message }}</span></li></ul>
      </template>
      <div class="flex flex-wrap justify-end gap-2">
        <Button v-if="requestId" variant="secondary" @click="refresh">{{ label('refresh') }}</Button>
        <Button v-if="active" variant="secondary" @click="cancel">{{ label('cancel') }}</Button>
        <Button v-else-if="receipt" variant="secondary" @click="newExport">{{ label('newExport') }}</Button>
        <Button v-else :disabled="busy" @click="submit">{{ label(pendingBody ? 'recover' : busy ? 'preparing' : 'start') }}</Button>
        <Button variant="textonly" @click="emit('close')">{{ label('close') }}</Button>
      </div>
    </DialogContent></DialogPortal>
  </Dialog>
</template>
