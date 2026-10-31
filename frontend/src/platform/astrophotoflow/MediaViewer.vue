<script setup lang="ts">
import { createMediaClient, mediaSelectionSchema } from '@astrophotoflow/ui'
import type { MediaMember, MediaSelection, MediaState, MediaViewerRequest } from '@astrophotoflow/ui'
import { computed, nextTick, onBeforeUnmount, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import Dialog from '@/components/ui/dialog/Dialog.vue'
import DialogContent from '@/components/ui/dialog/DialogContent.vue'
import DialogHeader from '@/components/ui/dialog/DialogHeader.vue'
import DialogOverlay from '@/components/ui/dialog/DialogOverlay.vue'
import DialogPortal from '@/components/ui/dialog/DialogPortal.vue'
import DialogTitle from '@/components/ui/dialog/DialogTitle.vue'
import Input from '@/components/ui/input/Input.vue'

import { createImageViewport } from './mediaViewport'
import PreviewControls from './PreviewControls.vue'
import type { ImageScreenBounds, ImageViewportSnapshot } from './mediaViewport'

const { request } = defineProps<{ request: MediaViewerRequest }>()
const emit = defineEmits<{ close: []; index: [index: number] }>()
const { t } = useI18n()
const stage = useTemplateRef<HTMLDivElement>('stage')
const video = useTemplateRef<HTMLVideoElement>('video')
const index = ref(request.index)
const position = ref(String(request.index + 1))
const member = ref<MediaMember>()
const state = ref<MediaState>()
const loading = ref(false)
const error = ref('')
const percent = ref(100)
const maximized = ref(false)
const chooseArray = ref(false)
const showDisplayRange = ref(false)
const displayLow = ref(0)
const displayHigh = ref(1)
const validDisplayRange = computed(() => Number.isFinite(displayLow.value) && Number.isFinite(displayHigh.value) && displayLow.value < displayHigh.value)
const form = ref<MediaSelection>(mediaSelectionSchema.parse({}))
const pausedFrame = ref(false)
const presentedTime = ref<number>()
const initialOverview = ref('')
const imageBounds = ref<ImageScreenBounds>()
const overviewStyle = computed(() => imageBounds.value ? {
  left: `${imageBounds.value.left}px`, top: `${imageBounds.value.top}px`,
  width: `${imageBounds.value.width}px`, height: `${imageBounds.value.height}px`
} : undefined)
const neighbors = new Map<number, { member: MediaMember; url: string }>()
let viewer: ReturnType<typeof createImageViewport> | undefined
let controller: AbortController | undefined
let generation = 0
let consumerId = crypto.randomUUID()
let consumerBase: string | undefined
let playbackSelection: Partial<MediaSelection> = {}
let playbackTime = 0
let frameCallback: number | undefined
let savedViewport: ImageViewportSnapshot | undefined

const selectedArray = computed(() => state.value?.arrays.find(array => array.key === form.value.array_key))
const axes = computed(() => selectedArray.value?.shape.map((length, axis) => ({ axis, length })) ?? [])
const sliceAxes = computed(() => axes.value.filter(({ axis }) => ![form.value.x_axis, form.value.y_axis, form.value.channel_axis].includes(axis)))

function message(cause: unknown) {
  return cause instanceof Error ? cause.message : String(cause)
}

function disposeImage() {
  if (viewer) savedViewport = viewer.snapshot()
  viewer?.destroy()
  viewer = undefined
  imageBounds.value = undefined
}

function stopVideo() {
  if (video.value) {
    if (frameCallback !== undefined) video.value.cancelVideoFrameCallback(frameCallback)
    video.value.pause()
  }
  frameCallback = undefined
}

async function wait(signal: AbortSignal) {
  await new Promise<void>((resolve, reject) => {
    const finish = () => { signal.removeEventListener('abort', abort); resolve() }
    const timeout = setTimeout(finish, 1000)
    function abort() { clearTimeout(timeout); reject(new DOMException('Aborted', 'AbortError')) }
    signal.addEventListener('abort', abort, { once: true })
  })
}

function changeZoom(factor: number) {
  viewer?.zoomBy(factor)
}

function fit() { viewer?.fit() }
function actual() { viewer?.actual() }

async function attachImage(current: number) {
  await nextTick()
  const image = state.value
  if (current !== generation || !stage.value || !image?.tile_url) return
  viewer = createImageViewport(stage.value, image, {
    previous: savedViewport,
    zoom: value => { if (current === generation) percent.value = value },
    bounds: value => { if (current === generation) imageBounds.value = value },
    failed: () => { if (current === generation) error.value = t('astrophotoflow.media.tileError') }
  })
}

async function load(next: number, selection: Partial<MediaSelection> = {}) {
  if (next < 0 || next >= request.total) return
  const current = ++generation
  controller?.abort()
  releaseConsumer()
  consumerId = crypto.randomUUID()
  controller = new AbortController()
  const signal = controller.signal
  disposeImage()
  stopVideo()
  state.value = undefined
  initialOverview.value = neighbors.get(next)?.url ?? ''
  loading.value = true
  error.value = ''
  presentedTime.value = undefined
  index.value = next
  position.value = String(next + 1)
  emit('index', next)
  const client = createMediaClient((path, init) => fetch(path, { ...init, signal }))
  try {
    const selected = neighbors.get(next)?.member ?? await request.member(next, signal)
    if (current !== generation) return
    member.value = selected
    consumerBase = selected.basePath
    let settled = false
    void fetch(selected.basePath + '/thumbnail', { signal }).then(async response => {
      if (!response.ok) return
      const blob = await response.blob()
      if (current !== generation || signal.aborted || settled) return
      const cached = neighbors.get(next)
      if (cached) URL.revokeObjectURL(cached.url)
      const url = URL.createObjectURL(blob)
      neighbors.set(next, { member: selected, url })
      initialOverview.value = url
    }).catch(() => undefined)
    let result = await client.prepare(selected.basePath, { ...selected.selection, ...selection, consumer_id: consumerId, generation: current })
    while (result.status === 'generating') {
      if (current !== generation) return
      state.value = result
      await wait(signal)
      result = await client.status(selected.basePath, result.key)
    }
    if (current !== generation) return
    settled = true
    state.value = result
    form.value = result.selection
    displayLow.value = result.selection.display_range?.[0] ?? 0
    displayHigh.value = result.selection.display_range?.[1] ?? 1
    chooseArray.value = result.needs_selection
    if (result.status !== 'available') {
      error.value = result.error?.message ?? t('astrophotoflow.previewUnavailable')
      return
    }
    if (result.kind === 'image' && !result.needs_selection) await attachImage(current)
    if (result.kind === 'video') playbackSelection = selection
    void prefetch(next, current, signal)
  } catch (cause) {
    if (current === generation && !signal.aborted) error.value = message(cause)
  } finally {
    if (current === generation) loading.value = false
  }
}

function releaseConsumer() {
  if (consumerBase) void fetch(consumerBase + '/viewer/consumer/' + consumerId, { method: 'DELETE', keepalive: true }).catch(() => undefined)
  consumerBase = undefined
}

async function prefetch(currentIndex: number, currentGeneration: number, signal: AbortSignal) {
  for (const [position, cached] of neighbors) {
    if (Math.abs(position - currentIndex) > 1) { URL.revokeObjectURL(cached.url); neighbors.delete(position) }
  }
  await Promise.all([currentIndex - 1, currentIndex + 1].filter(position => position >= 0 && position < request.total && !neighbors.has(position)).map(async position => {
    try {
      const selected = await request.member(position, signal)
      const response = await fetch(selected.basePath + '/thumbnail', { signal })
      if (!response.ok) return
      const blob = await response.blob()
      if (currentGeneration === generation && !signal.aborted) neighbors.set(position, { member: selected, url: URL.createObjectURL(blob) })
    } catch (cause) {
      if (!(cause instanceof DOMException && cause.name === 'AbortError')) return
    }
  }))
}

function jump() {
  const value = Number(position.value)
  if (Number.isInteger(value) && value >= 1 && value <= request.total) {
    pausedFrame.value = false
    playbackTime = 0
    void load(value - 1)
  } else position.value = String(index.value + 1)
}

function move(delta: number) { position.value = String(index.value + delta + 1); jump() }

function videoReady() {
  const element = video.value
  if (!element) return
  if (playbackTime) element.currentTime = playbackTime
  if (!('requestVideoFrameCallback' in element)) {
    error.value = t('astrophotoflow.media.frameCallbackUnavailable')
    return
  }
  const capture = (_now: number, metadata: VideoFrameCallbackMetadata) => {
    presentedTime.value = metadata.mediaTime
    if (video.value === element) frameCallback = element.requestVideoFrameCallback(capture)
  }
  frameCallback = element.requestVideoFrameCallback(capture)
}

function videoFailed() {
  if (!state.value?.proxy) void load(index.value, { proxy: true })
  else error.value = t('astrophotoflow.media.videoError')
}

function inspectFrame() {
  if (!video.value || presentedTime.value === undefined || !state.value) return
  video.value.pause()
  playbackTime = video.value.currentTime
  pausedFrame.value = true
  void load(index.value, { media_time: presentedTime.value, playback_key: state.value.proxy ? state.value.key : undefined })
}

function resumeVideo() { pausedFrame.value = false; void load(index.value, playbackSelection) }

function arrayChanged() {
  form.value.x_axis = null
  form.value.y_axis = null
  form.value.channel_axis = null
  form.value.slices = {}
}

function applyArray() {
  chooseArray.value = false
  const slices = Object.fromEntries(sliceAxes.value.map(({ axis }) => [String(axis), form.value.slices[axis] ?? 0]))
  void load(index.value, { ...form.value, slices })
}

function keydown(event: KeyboardEvent) {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || state.value?.kind === 'video') return
  if (event.key === 'ArrowLeft') move(-1)
  else if (event.key === 'ArrowRight') move(1)
  else if (event.key === '+' || event.key === '=') changeZoom(1.2)
  else if (event.key === '-') changeZoom(1 / 1.2)
  else if (event.key === '0') fit()
  else if (event.key === '1') actual()
  else return
  event.preventDefault()
}

watch(() => request, () => { savedViewport = undefined; pausedFrame.value = false; void load(request.index) }, { immediate: true })
onBeforeUnmount(() => {
  generation++
  controller?.abort()
  stopVideo()
  disposeImage()
  for (const cached of neighbors.values()) URL.revokeObjectURL(cached.url)
  neighbors.clear()
  releaseConsumer()
})
</script>

<template>
  <Dialog :open="true" @update:open="!$event && emit('close')">
    <DialogPortal><DialogOverlay /><DialogContent size="full" :maximized class="gap-2 p-3" :aria-describedby="undefined" @keydown="keydown" @pointerdown.stop @wheel.stop>
      <DialogHeader class="shrink-0"><DialogTitle class="min-w-0 truncate">{{ member?.title ?? t('astrophotoflow.libraryImage') }}</DialogTitle>
        <Button variant="textonly" size="icon" :aria-label="t('g.close')" @click="emit('close')"><i class="icon-[lucide--x] size-4" /></Button>
      </DialogHeader>
      <div class="flex shrink-0 flex-wrap items-center gap-1">
        <template v-if="state?.kind !== 'video'">
          <Button variant="textonly" :disabled="loading || !viewer" @click="fit">{{ t('astrophotoflow.media.fit') }}</Button>
          <Button variant="textonly" :disabled="loading || !viewer" @click="actual">100%</Button>
          <Button variant="textonly" size="icon" :disabled="!viewer" :aria-label="t('astrophotoflow.media.zoomOut')" @click="changeZoom(1 / 1.2)">−</Button>
          <span class="w-16 text-center tabular-nums">{{ Math.round(percent) }}%</span>
          <Button variant="textonly" size="icon" :disabled="!viewer" :aria-label="t('astrophotoflow.media.zoomIn')" @click="changeZoom(1.2)">＋</Button>
        </template>
        <Button v-if="state?.arrays.length || (state?.hdus.length ?? 0) > 1" variant="textonly" @click="chooseArray = !chooseArray">{{ t('astrophotoflow.media.arraySelection') }}</Button>
        <Button v-if="state?.kind === 'image' && !state.needs_selection" variant="textonly" :disabled="loading" @click="showDisplayRange = !showDisplayRange">{{ t('astrophotoflow.media.displayThresholds') }}</Button>
        <PreviewControls v-if="state?.kind === 'image' && !state.needs_selection" v-model:max-edge="form.preview_max_edge" v-model:balance="form.display_balance" :disabled="loading" @change="load(index, { ...form, display_range: null })" />
        <Button v-if="state?.kind === 'video'" variant="textonly" :disabled="presentedTime === undefined" @click="inspectFrame">{{ t('astrophotoflow.media.inspectFrame') }}</Button>
        <Button v-if="pausedFrame" variant="textonly" @click="resumeVideo">{{ t('astrophotoflow.media.backToVideo') }}</Button>
        <span class="ml-auto text-muted-foreground">{{ state?.width && state.height ? `${state.width} × ${state.height}` : '' }}</span>
        <Button variant="textonly" size="icon" :aria-label="t('astrophotoflow.media.maximize')" @click="maximized = !maximized"><i :class="maximized ? 'icon-[lucide--minimize] size-4' : 'icon-[lucide--maximize] size-4'" /></Button>
      </div>
      <div v-if="showDisplayRange && state?.kind === 'image' && !state.needs_selection" class="flex shrink-0 flex-wrap items-center gap-2 rounded-sm bg-component-node-widget-background p-2">
        <label class="flex items-center gap-1">{{ t('astrophotoflow.media.displayLow') }}<Input v-model.number="displayLow" type="number" step="any" class="w-28" /></label>
        <label class="flex items-center gap-1">{{ t('astrophotoflow.media.displayHigh') }}<Input v-model.number="displayHigh" type="number" step="any" class="w-28" /></label>
        <Button :disabled="loading || !validDisplayRange" @click="load(index, { ...form, display_range: [displayLow, displayHigh] })">{{ t('astrophotoflow.media.showSelection') }}</Button>
        <Button variant="textonly" :disabled="loading || !form.display_range" @click="load(index, { ...form, display_range: null })">{{ t('astrophotoflow.media.resetDisplay') }}</Button>
        <span class="text-muted-foreground">{{ t('astrophotoflow.media.displayOnly') }}</span>
      </div>
      <div v-if="chooseArray && (state?.hdus.length ?? 0) > 1" class="flex shrink-0 flex-wrap items-center gap-2 rounded-sm bg-component-node-widget-background p-2">
        <label class="flex items-center gap-1">{{ t('astrophotoflow.media.hdu') }}<select v-model.number="form.hdu_index" class="rounded-sm border border-border-default bg-base-background p-1"><option v-for="hdu in state?.hdus" :key="hdu.index" :value="hdu.index" :disabled="!hdu.kind">{{ hdu.index }} · {{ hdu.name ?? hdu.kind ?? '—' }} · {{ hdu.shape.join(' × ') }}</option></select></label>
        <Button @click="load(index, { ...form })">{{ t('astrophotoflow.media.showSelection') }}</Button>
      </div>
      <div v-if="chooseArray && state?.arrays.length" class="flex shrink-0 flex-wrap items-center gap-2 rounded-sm bg-component-node-widget-background p-2">
        <label class="flex items-center gap-1">{{ t('astrophotoflow.media.array') }}<select v-model="form.array_key" class="rounded-sm border border-border-default bg-base-background p-1" @change="arrayChanged"><option :value="null">—</option><option v-for="array in state.arrays" :key="array.key" :value="array.key" :disabled="!array.numeric">{{ array.key }} · {{ array.shape.join(' × ') }} · {{ array.dtype }}</option></select></label>
        <label v-for="field in (['x_axis', 'y_axis', 'channel_axis'] as const)" :key="field" class="flex items-center gap-1">{{ t(`astrophotoflow.media.${field}`) }}<select v-model="form[field]" class="rounded-sm border border-border-default bg-base-background p-1"><option :value="null">—</option><option v-for="axis in axes" :key="axis.axis" :value="axis.axis">{{ axis.axis }} ({{ axis.length }})</option></select></label>
        <label v-for="axis in sliceAxes" :key="axis.axis" class="flex items-center gap-1">{{ t('astrophotoflow.media.slice') }} {{ axis.axis }}<Input v-model.number="form.slices[axis.axis]" type="number" :min="0" :max="axis.length - 1" class="w-20" /></label>
        <Button :disabled="!selectedArray?.numeric" @click="applyArray">{{ t('astrophotoflow.media.showSelection') }}</Button>
      </div>
      <p v-if="error" role="alert" class="m-0 shrink-0 text-error">{{ error }} <Button variant="textonly" @click="load(index, state?.selection)">{{ t('astrophotoflow.retryPreview') }}</Button></p>
      <div class="relative min-h-0 flex-1 overflow-hidden rounded-sm bg-component-node-widget-background">
        <img v-if="state?.overview_url || initialOverview" :src="state?.overview_url ?? initialOverview" :alt="member?.title ?? t('astrophotoflow.libraryImage')" class="pointer-events-none absolute max-w-none" :class="imageBounds ? 'object-fill' : 'inset-0 size-full object-contain'" :style="overviewStyle" />
        <div v-show="state?.kind !== 'video'" ref="stage" class="absolute inset-0" />
        <video v-if="state?.kind === 'video' && state.video_url && !loading" ref="video" :key="state.key" :src="state.video_url" :aria-label="t('g.videoPreview')" controls playsinline preload="metadata" class="size-full object-contain" @loadedmetadata="videoReady" @error="videoFailed" />
        <div v-if="loading" role="status" class="pointer-events-none absolute top-3 left-3 flex items-center gap-2 rounded-sm bg-base-background px-3 py-2"><i class="icon-[lucide--loader-circle] size-4 animate-spin" />{{ t(state?.phase === 'queued' ? 'astrophotoflow.media.queued' : 'astrophotoflow.media.preparing') }}</div>
      </div>
      <div class="flex shrink-0 items-center justify-between gap-2">
        <span class="min-w-0 truncate text-muted-foreground" :title="state?.note ?? undefined">{{ state?.note }}</span>
        <div v-if="request.total > 1" class="flex shrink-0 items-center gap-1">
          <Button variant="textonly" size="icon" :disabled="index === 0" :aria-label="t('g.previousImage')" @click="move(-1)"><i class="icon-[lucide--chevron-left] size-4" /></Button>
          <Input v-model="position" type="number" min="1" :max="request.total" class="w-20" :aria-label="t('astrophotoflow.media.memberIndex')" @change="jump" @keydown.enter="jump" /><span>/ {{ request.total }}</span>
          <Button variant="textonly" size="icon" :disabled="index + 1 === request.total" :aria-label="t('g.nextImage')" @click="move(1)"><i class="icon-[lucide--chevron-right] size-4" /></Button>
        </div>
      </div>
    </DialogContent></DialogPortal>
  </Dialog>
</template>
