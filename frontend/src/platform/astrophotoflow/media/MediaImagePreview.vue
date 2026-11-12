<script setup lang="ts">
import {
  createMediaClient,
  useMediaView,
  useMediaOverview
} from '@astrophotoflow/ui'
import type { MediaSelection, MediaState } from '@astrophotoflow/ui'
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useNativeWorkspace } from '../useNativeWorkspace'
import Button from '@/components/ui/button/Button.vue'

const { base, title, selection } = defineProps<{
  base: string
  title: string
  selection?: Partial<MediaSelection>
}>()
const emit = defineEmits<{
  open: [selection: Partial<MediaSelection>]
  media: [state: MediaState]
}>()
const { t } = useI18n()
const workspace = useNativeWorkspace()
const client = createMediaClient((path, init) => fetch(path, init))
const media = useMediaView(
  computed(() =>
    workspace.workspaceId.value
      ? {
          workspaceId: workspace.workspaceId.value,
          basePath: base,
          selection: {
            preview_max_edge: 1024,
            display_balance: 'preserve',
            frame_index: 0,
            ...selection
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
watch(media.state, (state) => {
  if (state && (state.status === 'available' || state.channels?.length)) emit('media', state)
})
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
async function retryPreview() {
  if (media.error.value || media.state.value?.status !== 'available') await media.retry()
  if (overview.error.value) await overview.retry()
}
</script>

<template>
  <slot v-if="image && media.state.value" name="image" :image="image" :state="media.state.value" />
  <Button variant="textonly" size="unset"
    v-if="!$slots.image || !image || !media.state.value"
    type="button"
    class="relative h-48 shrink-0 overflow-hidden rounded-sm bg-component-node-widget-background"
    :aria-label="t('astrophotoflow.media.open')"
    :disabled="!image"
    @click="emit('open', media.state.value?.selection ?? selection ?? {})"
  >
    <img
      v-if="image"
      :src="image"
      :alt="title"
      class="size-full object-contain"
    />
    <span v-else-if="!error" role="status">{{
      loading ? t('astrophotoflow.bundle.loadingImage') : ''
    }}</span>
  </Button>
  <div v-if="error" role="alert" class="flex items-center gap-1 text-xs text-error">
    <span>{{ error }}</span>
    <Button variant="textonly" size="sm" @click="retryPreview">{{ t('astrophotoflow.retryPreview') }}</Button>
  </div>
</template>
