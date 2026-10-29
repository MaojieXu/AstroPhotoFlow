<script setup lang="ts">
import { createSirilPreviewClient, scienceReferenceSchema } from '@astrophotoflow/ui'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import Button from '@/components/ui/button/Button.vue'
import ImagePreview from '@/renderer/extensions/vueNodes/components/ImagePreview.vue'
import { api } from '@/scripts/api'
import type { ComponentWidget } from '@/scripts/domWidget'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const tabs = useSidebarTabStore()
const revision = ref(0)
const index = ref(0)
const image = ref('')
const failure = ref('')
const phase = ref<'idle' | 'waiting' | 'updating' | 'ready' | 'failed'>('idle')
const notInstalled = ref(false)
const consumer = crypto.randomUUID()
const client = createSirilPreviewClient((path, init) => fetch(path, init))
let generation = 0
let timer: ReturnType<typeof setTimeout> | undefined
let controller: AbortController | undefined

const sourceText = computed(() => {
  void revision.value
  const node = widget.node
  if (!node.graph) return ''
  const slot = node.inputs.findIndex(input => input.name === 'image')
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
  const linked = controls.find(control => control.name === 'linked')?.value
  const shadowsclip = controls.find(control => control.name === 'shadowsclip')?.value
  const targetbg = controls.find(control => control.name === 'targetbg')?.value
  if (typeof linked !== 'boolean' || typeof shadowsclip !== 'number' || !Number.isFinite(shadowsclip) || typeof targetbg !== 'number' || !Number.isFinite(targetbg)) return undefined
  return { linked, shadowsclip, targetbg }
})
const signature = computed(() => JSON.stringify([sourceText.value, parameters.value, index.value]))

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
  if (!fixed || !values) return
  phase.value = 'updating'
  failure.value = ''
  try {
    const blob = await client.render({ reference: fixed, member_index: index.value,
      consumer_id: consumer, generation: current, ...values }, signal)
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
    <span class="text-xs text-muted-foreground">{{ t('astrophotoflow.siril.quickPreview') }}</span>
    <div class="relative h-48 min-h-48 w-full overflow-hidden rounded-sm bg-component-node-widget-background">
      <ImagePreview v-if="image" :image-urls="[image]" display-only :class="phase !== 'ready' ? 'opacity-40' : ''" @load-error="imageFailed" />
      <div v-if="phase !== 'ready'" class="absolute inset-0 flex flex-col items-center justify-center gap-2 overflow-auto p-2 text-center text-xs text-muted-foreground" :role="failure ? 'alert' : 'status'">
        <i v-if="phase === 'waiting' || phase === 'updating'" class="icon-[lucide--loader-circle] size-4 animate-spin" aria-hidden="true" />
        <span class="max-h-24 overflow-auto break-words">{{ failure || t(phase === 'idle' ? 'astrophotoflow.siril.connectSource' : 'astrophotoflow.siril.updating') }}</span>
        <Button v-if="notInstalled" size="sm" variant="secondary" @click="tabs.activeSidebarTabId = 'software'">{{ t('apfSoftware.install') }} Siril</Button>
        <Button v-if="phase === 'failed'" size="sm" variant="textonly" @click="render">{{ t('g.retry') }}</Button>
      </div>
    </div>
    <div v-if="total > 1" class="flex h-7 items-center justify-between text-xs text-muted-foreground">
      <Button size="icon" variant="textonly" :disabled="index === 0" :aria-label="t('g.previous')" @click="index--"><i class="icon-[lucide--chevron-left] size-4" /></Button>
      <span>{{ index + 1 }} / {{ total }}</span>
      <Button size="icon" variant="textonly" :disabled="index + 1 >= total" :aria-label="t('g.next')" @click="index++"><i class="icon-[lucide--chevron-right] size-4" /></Button>
    </div>
  </div>
</template>
