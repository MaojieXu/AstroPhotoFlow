<script setup lang="ts">
import { createBundlePreviewClient, scienceReferenceSchema } from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import ImagePreview from '@/renderer/extensions/vueNodes/components/ImagePreview.vue'
import { api } from '@/scripts/api'
import type { ComponentWidget } from '@/scripts/domWidget'
import { bundleCapabilities } from './bundleCatalog'
import PreviewControls from './PreviewControls.vue'
import type { MediaSelection } from '@astrophotoflow/ui'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const tabs = useSidebarTabStore()
const revision = ref(0)
const index = ref(0)
const image = ref('')
const expanded = ref(false)
const maxEdge = ref<MediaSelection['preview_max_edge']>(1024)
const balance = ref<MediaSelection['display_balance']>(null)
const failure = ref('')
const phase = ref<'idle' | 'waiting' | 'updating' | 'ready' | 'failed'>('idle')
const notInstalled = ref(false)
const consumer = crypto.randomUUID()
const client = createBundlePreviewClient((path, init) => fetch(path, init))
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined

const capability = computed(() => widget.node.comfyClass ? bundleCapabilities.get(widget.node.comfyClass) : undefined)

const sourceText = computed(() => {
  void revision.value
  const node = widget.node
  if (!node.graph) return ''
  const slot = node.inputs.findIndex(input => input.name === capability.value?.preview?.input)
  if (slot < 0) return ''
  const source = node.getInputNode(slot)
  if (source?.comfyClass !== 'APF_DATA_REFERENCE') return ''
  const value = source.widgets?.find(control => control.name === 'reference')?.value
  return typeof value === 'string' ? value : ''
})

const reference = computed(() => {
  if (!sourceText.value) return undefined
  try {
    const parsed = scienceReferenceSchema.safeParse(JSON.parse(sourceText.value))
    return parsed.success ? parsed.data : undefined
  } catch {
    return undefined
  }
})
const total = computed(() => reference.value?.kind === 'dataset_version' ? reference.value.members.length : reference.value ? 1 : 0)
const parameters = computed(() => {
  void revision.value
  const controls = widget.node.widgets ?? []
  if (!capability.value) return undefined
  return Object.fromEntries(capability.value.node.definition.parameters.map(parameter => [parameter.name,
    controls.find(control => control.name === parameter.name)?.value ?? parameter.default]))
})
const signature = computed(() => JSON.stringify([sourceText.value, parameters.value, index.value, capability.value?.available,
  capability.value?.node.content_token, capability.value?.development_source?.fingerprint, maxEdge.value, balance.value]))

function clearImage() {
  if (image.value) URL.revokeObjectURL(image.value)
  image.value = ''
}

function schedule() {
  generation++
  controller?.abort()
  clearTimeout(timer)
  failure.value = ''
  notInstalled.value = false
  if (!expanded.value) { phase.value = 'idle'; clearImage(); return }
  if (capability.value && !capability.value.available) {
    failure.value = capability.value.reason ?? t('apfSoftware.unavailable')
    notInstalled.value = true
    phase.value = 'failed'
    clearImage()
    return
  }
  if (!reference.value || !parameters.value) {
    phase.value = 'idle'
    clearImage()
    return
  }
  phase.value = 'waiting'
  timer = setTimeout(() => void render(), 350)
}

async function render() {
  const current = ++generation
  controller?.abort()
  controller = new AbortController()
  const signal = controller.signal
  const fixed = reference.value
  const values = parameters.value
  if (!fixed || !values || !capability.value?.operation) return
  phase.value = 'updating'
  failure.value = ''
  try {
    const blob = await client.render({ reference: fixed, member_index: index.value,
      consumer_id: consumer, generation: current, parameters: values, package_id: capability.value.operation.package_id, operation_id: capability.value.operation.operation_id,
      preview_max_edge: maxEdge.value, display_balance: balance.value }, signal)
    if (current !== generation || signal.aborted) return
    clearImage()
    image.value = URL.createObjectURL(blob)
    phase.value = 'ready'
  } catch (cause) {
    if (current !== generation || signal.aborted) return
    failure.value = cause instanceof Error ? cause.message : String(cause)
    notInstalled.value = cause instanceof Error && 'code' in cause && cause.code === 'SOFTWARE_NOT_READY'
    phase.value = 'failed'
  }
}

function changed() { revision.value++ }
function imageFailed() { failure.value = t('astrophotoflow.previewUnavailable'); phase.value = 'failed'; clearImage() }

watch(sourceText, () => { index.value = 0; clearImage() })
watch(index, clearImage)
watch(signature, schedule, { immediate: true })
watch(expanded, schedule)
onMounted(() => api.addEventListener('graphChanged', changed))
onBeforeUnmount(() => {
  generation++
  clearTimeout(timer)
  controller?.abort()
  clearImage()
  api.removeEventListener('graphChanged', changed)
  void client.release(consumer).catch(() => undefined)
})
</script>

<template>
  <div class="flex h-full min-w-0 flex-col gap-1 px-2 py-1" @pointerdown.stop @pointermove.stop @pointerup.stop @keydown.stop @wheel.stop>
    <Button size="sm" variant="textonly" :aria-expanded="expanded" @click="expanded = !expanded">{{ t('astrophotoflow.siril.quickPreview') }}</Button>
    <template v-if="expanded">
    <PreviewControls v-model:max-edge="maxEdge" v-model:balance="balance" />
    <div class="relative h-48 min-h-48 w-full overflow-hidden rounded-sm bg-component-node-widget-background">
      <ImagePreview v-if="image" :image-urls="[image]" display-only :class="phase !== 'ready' ? 'opacity-40' : ''" @load-error="imageFailed" />
      <div v-if="phase !== 'ready'" class="absolute inset-0 flex flex-col items-center justify-center gap-2 overflow-auto p-2 text-center text-xs text-muted-foreground" :role="failure ? 'alert' : 'status'">
        <i v-if="phase === 'waiting' || phase === 'updating'" class="icon-[lucide--loader-circle] size-4 animate-spin" aria-hidden="true" />
        <span class="max-h-24 overflow-auto wrap-break-word">{{ failure || t(phase === 'idle' ? 'astrophotoflow.siril.connectSource' : 'astrophotoflow.siril.updating') }}</span>
        <Button v-if="notInstalled" size="sm" variant="secondary" @click="tabs.activeSidebarTabId = 'software'">{{ t('apfSoftware.install') }}</Button>
        <Button v-if="phase === 'failed'" size="sm" variant="textonly" @click="render">{{ t('g.retry') }}</Button>
      </div>
    </div>
    <div v-if="total > 1" class="flex h-7 items-center justify-between text-xs text-muted-foreground">
      <Button size="icon" variant="textonly" :disabled="index === 0" :aria-label="t('g.previous')" @click="index--"><i class="icon-[lucide--chevron-left] size-4" /></Button>
      <span>{{ index + 1 }} / {{ total }}</span>
      <Button size="icon" variant="textonly" :disabled="index + 1 >= total" :aria-label="t('g.next')" @click="index++"><i class="icon-[lucide--chevron-right] size-4" /></Button>
    </div>
    </template>
  </div>
</template>
