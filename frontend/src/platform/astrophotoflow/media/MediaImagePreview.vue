<script setup lang="ts">
import {
  createMediaClient,
  useMediaView,
  useMediaOverview
} from '@astrophotoflow/ui'
import type { MediaSelection } from '@astrophotoflow/ui'
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import PreviewControls from './PreviewControls.vue'
import { useNativeWorkspace } from '../useNativeWorkspace'

const { base, title } = defineProps<{ base: string; title: string }>()
const emit = defineEmits<{ open: [selection: Partial<MediaSelection>] }>()
const { t } = useI18n()
const maxEdge = ref<MediaSelection['preview_max_edge']>(1024)
const balance = ref<MediaSelection['display_balance']>(null)
const workspace = useNativeWorkspace()
const client = createMediaClient((path, init) => fetch(path, init))
const media = useMediaView(
  computed(() =>
    workspace.workspaceId.value
      ? {
          workspaceId: workspace.workspaceId.value,
          basePath: base,
          selection: {
            preview_max_edge: maxEdge.value,
            display_balance: balance.value,
            frame_index: 0
          }
        }
      : undefined
  ),
  client
)
const overview = useMediaOverview(
  computed(() => {
    const state = media.state.value
    return workspace.workspaceId.value &&
      state?.status === 'available' &&
      state.overview_url
      ? {
          workspaceId: workspace.workspaceId.value,
          viewKey: state.key,
          url: state.overview_url
        }
      : undefined
  }),
  client
)
const image = overview.imageUrl
const loading = computed(() => media.loading.value || overview.loading.value)
const error = computed(() => {
  const cause =
    workspace.error.value ?? media.error.value ?? overview.error.value
  if (cause) return cause instanceof Error ? cause.message : String(cause)
  const state = media.state.value
  return state &&
    state.status !== 'generating' &&
    (state.status !== 'available' || !state.overview_url)
    ? t('astrophotoflow.previewUnavailable')
    : ''
})
</script>

<template>
  <PreviewControls v-model:max-edge="maxEdge" v-model:balance="balance" />
  <button
    type="button"
    class="relative h-48 shrink-0 overflow-hidden rounded-sm bg-component-node-widget-background"
    :aria-label="t('astrophotoflow.media.open')"
    @click="
      emit('open', { preview_max_edge: maxEdge, display_balance: balance })
    "
  >
    <img
      v-if="image"
      :src="image"
      :alt="title"
      class="size-full object-contain"
    />
    <span v-else :role="error ? 'alert' : 'status'">{{
      error || (loading ? t('astrophotoflow.media.preparing') : '')
    }}</span>
  </button>
</template>
