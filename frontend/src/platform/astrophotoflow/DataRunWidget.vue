<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { createMediaClient, dataResultSchema } from '@astrophotoflow/ui'
import type { MediaState, MediaViewerRequest } from '@astrophotoflow/ui'
import type { ComponentWidget } from '@/scripts/domWidget'
import { useNodeOutputStore } from '@/stores/nodeOutputStore'
import { useApp } from '@/scripts/appInstance'
import { api } from '@/scripts/api'
import Button from '@/components/ui/button/Button.vue'
import ImagePreview from '@/renderer/extensions/vueNodes/components/ImagePreview.vue'
import MediaViewer from './MediaViewer.vue'
import DataExportDialog from './DataExportDialog.vue'

const props = defineProps<{ widget: ComponentWidget<string | object>; reference?: unknown; bindings: Record<string, (string | number)[]> }>()
const { t } = useI18n()
const label = (key: string) => t(`astrophotoflow.dataExport.${key}`)
const outputs = useNodeOutputStore()
const currentRun = ref('')
const executionFailure = ref('')
const result = computed(() => {
  const entries = outputs.getNodeOutputs(props.widget.node)?.apf_data
  if (!Array.isArray(entries)) return undefined
  const parsed = dataResultSchema.safeParse(entries.at(-1))
  if (!parsed.success || parsed.data.state !== 'completed' || parsed.data.workflow_id !== useApp().rootGraph.id) return undefined
  if (currentRun.value && parsed.data.run_id !== currentRun.value) return undefined
  const actual = parsed.data.input_bindings
  if (JSON.stringify(Object.keys(actual).sort()) !== JSON.stringify(Object.keys(props.bindings).sort())) return undefined
  if (Object.keys(actual).some(key => JSON.stringify(actual[key]?.map(String)) !== JSON.stringify(props.bindings[key]?.map(String)))) return undefined
  if (!Object.keys(actual).length) {
    try { if (JSON.stringify(JSON.parse(String(props.reference))) !== JSON.stringify(parsed.data.reference)) return undefined }
    catch { return undefined }
  }
  return parsed.data
})
const index = ref(0)
const member = computed(() => result.value?.members[index.value])
const parameterSummary = computed(() => {
  const metadata = member.value?.metadata
  const raw = metadata?.parameters ?? metadata?.observed_parameters
  const parameters = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {}
  return [
    [t('astrophotoflow.exposure'), parameters.exposure_seconds],
    ['Gain', parameters.gain], ['ISO', parameters.iso], ['Offset', parameters.offset],
    [t('astrophotoflow.temperature'), parameters.sensor_temperature_c ?? parameters.sensor_temperature_setpoint_c]
  ].filter(([, value]) => value !== undefined && value !== null)
})
const media = ref<MediaState>()
const viewerMedia = ref<MediaState>()
const image = ref('')
const failure = ref('')
const loading = ref(false)
const viewer = ref<MediaViewerRequest>()
const exportTarget = ref<'library' | 'local'>()
let controller: AbortController | undefined
let generation = 0
let consumer = crypto.randomUUID()
let base: string | undefined
function clear() {
  controller?.abort()
  if (image.value) URL.revokeObjectURL(image.value)
  image.value = ''; media.value = undefined
  if (base) void fetch(base + '/viewer/consumer/' + consumer, { method: 'DELETE', keepalive: true }).catch(() => undefined)
  base = undefined
}
const onStart = (event: CustomEvent<{ prompt_id: string }>) => {
  if (props.widget.node.graph !== useApp().graph) return
  currentRun.value = event.detail.prompt_id; executionFailure.value = ''
}
const onFailure = (event: CustomEvent<{ prompt_id: string; exception_message?: string }>) => {
  if (event.detail.prompt_id === currentRun.value) executionFailure.value = event.detail.exception_message || label('executionFailed')
}
api.addEventListener('execution_start', onStart)
api.addEventListener('execution_error', onFailure)

async function load() {
  const turn = ++generation
  clear()
  failure.value = ''; loading.value = false
  if (!member.value) return
  controller = new AbortController()
  const signal = controller.signal
  consumer = crypto.randomUUID()
  base = member.value.view_base
  loading.value = true
  try {
    const client = createMediaClient((path, init) => fetch(path, { ...init, signal }))
    let state = await client.prepare(base, { ...member.value.selection, consumer_id: consumer, generation: turn })
    while (state.status === 'generating') {
      await new Promise<void>(resolve => {
        const timer = setTimeout(done, 1000)
        function done() { clearTimeout(timer); signal.removeEventListener('abort', done); resolve() }
        signal.addEventListener('abort', done, { once: true })
      })
      if (turn !== generation || signal.aborted) return
      state = await client.status(base, state.key)
    }
    if (turn !== generation) return
    media.value = state
    if (state.status === 'available' && state.overview_url) {
      const response = await fetch(state.overview_url, { signal })
      if (!response.ok) throw new Error(label('unavailable'))
      const blob = await response.blob()
      if (turn === generation && !signal.aborted && !viewerMedia.value) image.value = URL.createObjectURL(blob)
    } else if (state.status !== 'available') failure.value = state.error?.message ?? label('unavailable')
  } catch (cause) { if (turn === generation && !signal.aborted) failure.value = String(cause) }
  finally { if (turn === generation) loading.value = false }
}
function openViewer() {
  const snapshot = result.value
  if (!snapshot) return
  viewer.value = { index: index.value, total: snapshot.members.length,
    member: async position => ({ title: snapshot.members[position]!.name, basePath: snapshot.members[position]!.view_base, selection: snapshot.members[position]!.selection }) }
}
async function selectedView(state: MediaState) {
  viewerMedia.value = state
  if (!state.overview_url) return
  const turn = generation
  try {
    const response = await fetch(state.overview_url, { signal: controller?.signal })
    if (!response.ok) return
    const blob = await response.blob()
    if (turn === generation && viewerMedia.value === state) {
      if (image.value) URL.revokeObjectURL(image.value)
      image.value = URL.createObjectURL(blob)
    }
  } catch { /* a new selection or graph may cancel this display-only fetch */ }
}
watch(() => result.value?.execution_id, () => { index.value = 0; viewer.value = undefined; exportTarget.value = undefined })
watch(() => [result.value?.execution_id, index.value], () => { viewerMedia.value = undefined; void load() }, { immediate: true })
onBeforeUnmount(() => {
  generation++; clear()
  api.removeEventListener('execution_start', onStart)
  api.removeEventListener('execution_error', onFailure)
})
</script>

<template>
  <div class="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
    <p class="m-0 text-xs text-muted-foreground">{{ label(bindings.images ? 'sourceImage' : bindings.science ? 'sourceScience' : 'sourceLibrary') }}</p>
    <p v-if="!result" class="text-sm text-muted-foreground" role="status">{{ executionFailure || label('runFirst') }}</p>
    <template v-else>
      <strong class="truncate text-sm" :title="member?.name">{{ member?.name }}</strong>
      <button type="button" class="relative h-56 min-h-56 w-full overflow-hidden rounded-sm bg-component-node-widget-background" :aria-label="label('view')" @click="openViewer">
        <ImagePreview v-if="image" :image-urls="[image]" display-only />
        <span v-else class="block p-3 text-xs text-muted-foreground">{{ loading ? label('preparing') : failure || label('view') }}</span>
      </button>
      <div class="flex items-center justify-between"><Button variant="textonly" size="icon" :disabled="index === 0" :aria-label="t('g.previousImage')" @click="index--">‹</Button><span>{{ index + 1 }} / {{ result.members.length }}</span><Button variant="textonly" size="icon" :disabled="index + 1 >= result.members.length" :aria-label="t('g.nextImage')" @click="index++">›</Button></div>
      <p class="m-0 break-words text-xs text-muted-foreground">{{ member?.format }} · {{ member?.metadata?.pixel_type ?? '' }} · {{ member?.byte_size }} B</p>
      <dl v-if="parameterSummary.length" class="m-0 grid grid-cols-2 gap-x-2 text-xs"><div v-for="[name, value] in parameterSummary" :key="String(name)" class="flex gap-1"><dt class="text-muted-foreground">{{ name }}</dt><dd class="m-0">{{ value }}</dd></div></dl>
      <div class="mt-auto flex flex-wrap gap-1"><Button size="sm" variant="secondary" @click="exportTarget = 'library'">{{ label('saveLibrary') }}</Button><Button size="sm" variant="secondary" @click="exportTarget = 'local'">{{ label('saveLocal') }}</Button></div>
      <DataExportDialog v-if="exportTarget" :key="result.execution_id + exportTarget" :result="result" :index="index" :target="exportTarget" :media="viewerMedia ?? media" @close="exportTarget = undefined" />
    </template>
    <MediaViewer v-if="viewer" :request="viewer" @close="viewer = undefined" @index="index = $event" @selection="selectedView" />
  </div>
</template>
