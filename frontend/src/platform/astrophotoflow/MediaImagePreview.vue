<script setup lang="ts">
import { createMediaClient } from '@astrophotoflow/ui'
import type { MediaSelection } from '@astrophotoflow/ui'
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import PreviewControls from './PreviewControls.vue'

const { base, title } = defineProps<{ base: string; title: string }>()
const emit = defineEmits<{ open: [selection: Partial<MediaSelection>] }>()
const { t } = useI18n()
const maxEdge = ref<MediaSelection['preview_max_edge']>(1024)
const balance = ref<MediaSelection['display_balance']>(null)
const image = ref('')
const error = ref('')
const loading = ref(false)

watch(() => [base, maxEdge.value, balance.value], async (_, _old, cleanup) => {
  const controller = new AbortController()
  const { signal } = controller
  const consumer = crypto.randomUUID()
  const currentBase = base
  let url = ''
  let timer: ReturnType<typeof setTimeout> | undefined
  cleanup(() => {
    controller.abort()
    clearTimeout(timer)
    if (url) URL.revokeObjectURL(url)
    void fetch(currentBase + '/viewer/consumer/' + consumer, { method: 'DELETE', keepalive: true }).catch(() => undefined)
  })
  image.value = ''
  error.value = ''
  loading.value = true
  const client = createMediaClient((path, init) => fetch(path, { ...init, signal }))
  try {
    let state = await client.prepare(base, { preview_max_edge: maxEdge.value, display_balance: balance.value, consumer_id: consumer, generation: 1, frame_index: 0 })
    while (state.status === 'generating') {
      await new Promise<void>((resolve, reject) => {
        const abort = () => reject(new DOMException('Aborted', 'AbortError'))
        signal.addEventListener('abort', abort, { once: true })
        timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, 1000)
      })
      state = await client.status(base, state.key)
    }
    if (state.status !== 'available' || !state.overview_url) throw new Error(state.error?.message ?? t('astrophotoflow.previewUnavailable'))
    const response = await fetch(state.overview_url, { signal })
    if (!response.ok) throw new Error(t('astrophotoflow.previewUnavailable'))
    const blob = await response.blob()
    if (signal.aborted) return
    url = URL.createObjectURL(blob)
    image.value = url
  } catch (cause) {
    if (!signal.aborted) error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    if (!signal.aborted) loading.value = false
  }
}, { immediate: true })
</script>

<template>
  <PreviewControls v-model:max-edge="maxEdge" v-model:balance="balance" />
  <button type="button" class="relative h-48 shrink-0 overflow-hidden rounded-sm bg-component-node-widget-background" :aria-label="t('astrophotoflow.media.open')" @click="emit('open', { preview_max_edge: maxEdge, display_balance: balance })">
    <img v-if="image" :src="image" :alt="title" class="size-full object-contain" />
    <span v-else :role="error ? 'alert' : 'status'">{{ error || (loading ? t('astrophotoflow.media.preparing') : '') }}</span>
  </button>
</template>
