<script setup lang="ts">
import { createCanvasDataClient, createMediaClient, scienceReferenceSchema, dataResultSchema } from '@astrophotoflow/ui'
import type { CanvasInspect, MediaState, MediaViewerRequest } from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'
import Dialog from '@/components/ui/dialog/Dialog.vue'
import DialogContent from '@/components/ui/dialog/DialogContent.vue'
import DialogHeader from '@/components/ui/dialog/DialogHeader.vue'
import DialogOverlay from '@/components/ui/dialog/DialogOverlay.vue'
import DialogPortal from '@/components/ui/dialog/DialogPortal.vue'
import DialogTitle from '@/components/ui/dialog/DialogTitle.vue'
import ImagePreview from '@/renderer/extensions/vueNodes/components/ImagePreview.vue'
import type { ComponentWidget } from '@/scripts/domWidget'
import { api } from '@/scripts/api'
import { useApp } from '@/scripts/appInstance'
import MediaViewer from './MediaViewer.vue'
import DataRunWidget from './DataRunWidget.vue'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const revision = ref(0)
const graphChanged = () => { revision.value++ }
api.addEventListener('graphChanged', graphChanged)
onBeforeUnmount(() => api.removeEventListener('graphChanged', graphChanged))
const referenceText = computed(() => { void revision.value; return widget.node.widgets?.find(item => item.name === 'reference')?.value })
const nodeOutputs = useNodeOutputStore()
const bindings = computed(() => {
  void revision.value
  const result: Record<string, (string | number)[]> = {}
  for (const input of widget.node.inputs ?? []) {
    if (!['science', 'images'].includes(input.name) || input.link == null) continue
    const link = widget.node.graph?.links.get(input.link)
    if (link) result[input.name] = [String(link.origin_id), link.origin_slot]
  }
  return result
})
const connected = computed(() => Object.keys(bindings.value).length > 0)
const runtime = computed(() => {
  if (widget.node.comfyClass !== 'APF_DATA_REFERENCE') return false
  if (connected.value) return true
  const entries = nodeOutputs.getNodeOutputs(widget.node)?.apf_data
  if (!Array.isArray(entries)) return false
  const parsed = dataResultSchema.safeParse(entries.at(-1))
  try { return parsed.success && parsed.data.workflow_id === useApp().rootGraph.id && JSON.stringify(parsed.data.reference) === JSON.stringify(JSON.parse(String(referenceText.value))) }
  catch { return false }
})
const index = ref(0)
const data = ref<CanvasInspect>()
const fileReference = computed(() => widget.node.comfyClass === 'APF_FILE_REFERENCE' || data.value?.format === 'other')
const image = ref('')
const loading = ref(false)
const phase = ref<MediaState['phase']>()
const failure = ref('')
const details = ref(false)
const mediaRequest = ref<MediaViewerRequest>()
const importPath = ref('')
const importing = ref(false)
const importFailure = ref('')
const importController = new AbortController()

async function importImage() {
  const node = widget.node
  const graph = node.graph
  const reference = node.widgets?.find(item => item.name === 'reference')
  if (!graph || !reference || importing.value || !importPath.value.trim()) return
  importing.value = true
  importFailure.value = ''
  try {
    const prepared = await createCanvasDataClient((path, init) => fetch(path, { ...init, signal: importController.signal })).importPath(importPath.value.trim())
    if (node.graph !== graph || importController.signal.aborted) return
    const canvas = useApp().canvas
    canvas.emitBeforeChange()
    graph.beforeChange()
    try {
      reference.value = JSON.stringify(prepared.reference)
      node.title = prepared.title
      canvas.setDirty(true, true)
    } finally {
      graph.afterChange()
      canvas.emitAfterChange()
    }
    revision.value++
  } catch (cause) {
    if (!importController.signal.aborted) importFailure.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    importing.value = false
  }
}
let generation = 0
let controller: AbortController | undefined
let timer: ReturnType<typeof setTimeout> | undefined

function text(value: unknown) {
  return value === null || value === undefined || value === '' ? t('astrophotoflow.unspecified') : String(value)
}

const summary = computed(() => {
  const item = data.value
  if (!item) return []
  if (fileReference.value) return [[t('astrophotoflow.results.fileSize'), item.byte_size == null ? text(null) : `${item.byte_size} B`]]
  const parameters = item.parameters
  const mode = parameters.parameter_mode
  return [
    [t('astrophotoflow.originalDimensions'), item.width !== null && item.height !== null ? `${item.width} × ${item.height}` : text(null)],
    [t('astrophotoflow.exposure'), parameters.exposure_seconds == null ? text(null) : `${text(parameters.exposure_seconds)} s`],
    [t('astrophotoflow.filter'), text(item.equipment.filter)],
    [mode === 'iso' ? 'ISO' : mode === 'gain' ? 'Gain' : 'ISO / Gain', text(mode === 'iso' ? parameters.iso : mode === 'gain' ? parameters.gain : null)],
    [t('astrophotoflow.temperature'), parameters.sensor_temperature_c == null ? text(null) : `${text(parameters.sensor_temperature_c)} °C`]
  ]
})

const extra = computed(() => {
  const item = data.value
  if (!item) return []
  if (fileReference.value) return [[t('astrophotoflow.results.contentHash'), text(item.content_hash)]]
  return [
    [t('astrophotoflow.camera'), text(item.equipment.camera)],
    ['Offset', text(item.parameters.offset)],
    ['Bin X / Y', `${text(item.parameters.binning_x)} / ${text(item.parameters.binning_y)}`],
    ['CFA', text(item.parameters.cfa_pattern)],
    [t('astrophotoflow.format'), text(item.format)],
    ['BITPIX', text(item.bitpix)],
    [t('astrophotoflow.pixelType'), text(item.pixel_type)]
  ]
})

function clearImage() {
  if (image.value) URL.revokeObjectURL(image.value)
  image.value = ''
}

function imageFailed() {
  failure.value = t('astrophotoflow.previewUnavailable')
  clearImage()
}

let consumerId = crypto.randomUUID()
let consumerBase: string | undefined

function releaseConsumer() {
  if (consumerBase) void fetch(consumerBase + '/viewer/consumer/' + consumerId, { method: 'DELETE', keepalive: true }).catch(() => undefined)
  consumerBase = undefined
}

async function load() {
  const current = ++generation
  clearTimeout(timer)
  controller?.abort()
  releaseConsumer()
  consumerId = crypto.randomUUID()
  controller = new AbortController()
  const signal = controller.signal
  clearImage()
  data.value = undefined
  failure.value = ''
  loading.value = true
  phase.value = undefined
  const client = createCanvasDataClient((path, init) => fetch(path, { ...init, signal }))
  let waiting = false
  try {
    if (runtime.value) { loading.value = false; return }
    if (typeof referenceText.value !== 'string' || !referenceText.value) {
      failure.value = t('astrophotoflow.chooseLibraryImage')
      loading.value = false
      return
    }
    const reference = scienceReferenceSchema.parse(JSON.parse(referenceText.value))
    const item = await client.inspect(reference, index.value)
    if (current !== generation) return
    data.value = item
    if (item.format === 'other') return
    if (item.availability === 'available') {
      const base = `/astrophotoflow/api/v1/library/assets/${item.asset_id}/versions/${item.asset_version_id}/previews`
      consumerBase = base
      let overviewReady = false
      if (item.preview_status === 'available' && item.preview_url) {
        void client.getBlob(item.preview_url).then(blob => {
          if (current !== generation || signal.aborted || overviewReady) return
          clearImage()
          image.value = URL.createObjectURL(blob)
        }).catch(() => undefined)
      }
      const media = createMediaClient((path, init) => fetch(path, { ...init, signal }))
      const member = reference.kind === 'dataset_version' ? reference.members[index.value] : reference
      const selection = { hdu_index: member?.selection.hdu_index, ...(item.format === 'video' ? { frame_index: 0 } : {}) }
      let state = await media.prepare(base, { ...selection, consumer_id: consumerId, generation: current })
      while (state.status === 'generating') {
        phase.value = state.phase
        await new Promise<void>(resolve => {
          const finish = () => { signal.removeEventListener('abort', finish); resolve() }
          timer = setTimeout(finish, 1000)
          signal.addEventListener('abort', finish, { once: true })
        })
        if (current !== generation) return
        state = await media.status(base, state.key)
      }
      if (current !== generation) return
      if (state.status !== 'available') failure.value = state.error?.message ?? t('astrophotoflow.previewUnavailable')
      else if (state.needs_selection) failure.value = t('astrophotoflow.media.chooseArrayInViewer')
      else if (state.overview_url) {
        const blob = await client.getBlob(state.overview_url)
        if (current !== generation) return
        overviewReady = true
        clearImage()
        image.value = URL.createObjectURL(blob)
        data.value = { ...item, width: state.width, height: state.height }
      }
      return
    }
    if (item.preview_status === 'available' && item.preview_url) {
      const blob = await client.getBlob(item.preview_url)
      if (current !== generation) return
      image.value = URL.createObjectURL(blob)
    } else if (item.preview_status === 'pending') {
      waiting = true
      timer = setTimeout(() => void load(), 1500)
    } else {
      failure.value = item.preview_error ?? t('astrophotoflow.previewUnavailable')
    }
  } catch (error) {
    if (current !== generation) return
    failure.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (current === generation) loading.value = waiting
  }
}

function openViewer() {
  if (fileReference.value) return
  let value: unknown
  try { value = typeof referenceText.value === 'string' ? JSON.parse(referenceText.value) : undefined }
  catch (cause) { failure.value = cause instanceof Error ? cause.message : String(cause); return }
  const parsed = scienceReferenceSchema.safeParse(value)
  if (!parsed.success) return
  const reference = parsed.data
  mediaRequest.value = {
    index: index.value, total: reference.kind === 'dataset_version' ? reference.members.length : 1,
    member: async (position, signal) => {
      const client = createCanvasDataClient((path, init) => fetch(path, { ...init, signal }))
      const current = await client.inspect(reference, position)
      const selected = reference.kind === 'dataset_version' ? reference.members[position] : reference
      return { title: current.name, basePath: `/astrophotoflow/api/v1/library/assets/${current.asset_id}/versions/${current.asset_version_id}/previews`, selection: { hdu_index: selected?.selection.hdu_index } }
    }
  }
}

watch(referenceText, () => { index.value = 0; details.value = false; mediaRequest.value = undefined })
watch([referenceText, index, runtime], () => void load(), { immediate: true })
onBeforeUnmount(() => {
  importController.abort()
  generation++
  controller?.abort()
  clearTimeout(timer)
  clearImage()
  releaseConsumer()
})
</script>

<template>
  <div class="flex h-full w-full min-w-0 flex-col gap-2 px-2 py-1" @pointerdown.stop @pointermove.stop @pointerup.stop @keydown.stop @wheel.stop>
    <div class="flex shrink-0 items-center gap-1">
      <Input v-model="importPath" class="min-w-0 flex-1" :aria-label="t('astrophotoflow.imagePath')" :placeholder="t('astrophotoflow.imagePath')" :disabled="importing || connected" @keydown.enter.prevent="!connected && importImage()" />
      <Button size="sm" variant="secondary" :disabled="importing || connected || !importPath.trim()" @click="importImage">{{ t(importing ? 'astrophotoflow.importingImage' : 'astrophotoflow.importImage') }}</Button>
    </div>
    <span v-if="importFailure" role="alert" class="text-error">{{ importFailure }}</span>
    <DataRunWidget v-if="runtime" :widget="widget" :reference="referenceText" :bindings="bindings" />
    <template v-else>
    <strong class="shrink-0 truncate text-base-foreground" :title="data?.name">{{ data?.name ?? t('astrophotoflow.libraryImage') }}</strong>
    <div v-if="fileReference" class="flex min-h-20 items-center gap-2 rounded-sm bg-component-node-widget-background p-3"><i class="icon-[lucide--file-text] size-6" aria-hidden="true" /><span class="break-words">{{ failure || t('astrophotoflow.results.fixedFile') }}</span></div>
    <div v-else class="group relative h-56 min-h-56 w-full overflow-hidden rounded-sm bg-component-node-widget-background" role="button" tabindex="0" :aria-label="t('astrophotoflow.media.open')" @click="openViewer" @keydown.enter.prevent="openViewer" @keydown.space.prevent="openViewer">
      <ImagePreview v-if="image" :image-urls="[image]" display-only @load-error="imageFailed" />
      <div v-else class="flex h-full min-w-0 flex-col items-center justify-center gap-2 px-3 text-muted-foreground" role="status">
        <i :class="loading ? 'icon-[lucide--loader-circle] size-5 animate-spin' : 'icon-[lucide--image-off] size-5'" aria-hidden="true" />
        <span class="max-h-24 overflow-auto break-words">{{ failure || t(phase === 'queued' ? 'astrophotoflow.media.queued' : 'astrophotoflow.media.preparing') }}</span>
        <Button v-if="failure" variant="textonly" @click.stop="load()">{{ t('astrophotoflow.retryPreview') }}</Button>
      </div>
      <div v-if="image && (loading || failure)" class="absolute bottom-1 left-1 right-1 rounded-sm bg-base-background px-2 py-1" role="status">
        {{ failure || t(phase === 'queued' ? 'astrophotoflow.media.queued' : 'astrophotoflow.media.preparing') }}
        <Button v-if="failure" variant="textonly" @click.stop="load()">{{ t('astrophotoflow.retryPreview') }}</Button>
      </div>
      <Button class="absolute top-1 right-1 invisible group-hover:visible group-focus-within:visible" variant="textonly" size="icon" :aria-label="t('astrophotoflow.media.open')" @click.stop="openViewer"><i class="icon-[lucide--expand] size-4" /></Button>
    </div>
    <div class="flex h-8 shrink-0 items-center justify-between gap-1">
      <Button size="icon" variant="textonly" :aria-label="t('g.previousImage')" :disabled="index === 0" @click="index--"><i class="icon-[lucide--chevron-left] size-4" /></Button>
      <span class="text-muted-foreground">{{ data ? `${index + 1} / ${data.total}` : t('g.loading') }}</span>
      <Button size="icon" variant="textonly" :aria-label="t('g.nextImage')" :disabled="!data || index + 1 >= data.total" @click="index++"><i class="icon-[lucide--chevron-right] size-4" /></Button>
    </div>
    <dl class="m-0 grid min-w-0 grid-cols-2 gap-x-2 gap-y-1">
      <div v-for="[label, value] in summary" :key="label" class="flex min-w-0 gap-1"><dt class="shrink-0 text-muted-foreground">{{ label }}</dt><dd class="m-0 truncate" :title="value">{{ value }}</dd></div>
    </dl>
    <div class="mt-auto flex items-center justify-between gap-1">
      <span class="truncate text-muted-foreground" role="status">{{ data?.availability === 'available' ? t('astrophotoflow.originalReady') : data ? t('astrophotoflow.originalUnavailable') : '' }}</span>
      <Button variant="textonly" :disabled="!data" @click="details = true">{{ t('astrophotoflow.imageDetails') }}</Button>
    </div>
    <Dialog :open="details" @update:open="details = $event">
      <DialogPortal><DialogOverlay /><DialogContent size="md" class="max-h-[85vh] overflow-y-auto" :aria-describedby="undefined">
        <DialogHeader><DialogTitle>{{ data?.name }}</DialogTitle><Button variant="textonly" size="icon" :aria-label="t('g.close')" @click="details = false"><i class="icon-[lucide--x] size-4" /></Button></DialogHeader>
        <p class="text-muted-foreground">{{ t(fileReference ? 'astrophotoflow.results.fixedFile' : 'astrophotoflow.currentImageMetadata') }}</p>
        <dl class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2"><template v-for="[label, value] in [...summary, ...extra]" :key="label"><dt class="text-muted-foreground">{{ label }}</dt><dd class="m-0 break-words">{{ value }}</dd></template></dl>
      </DialogContent></DialogPortal>
    </Dialog>
    <MediaViewer v-if="mediaRequest" :request="mediaRequest" @close="mediaRequest = undefined" @index="index = $event" />
    </template>
  </div>
</template>
