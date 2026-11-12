<script setup lang="ts">
import type { MediaSelection, MediaState } from '@astrophotoflow/ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SingleSelect from '@/components/ui/single-select/SingleSelect.vue'

const maxEdge = defineModel<MediaSelection['preview_max_edge']>('maxEdge', {
  default: 1024
})
const balance = defineModel<MediaSelection['display_balance']>('balance', {
  default: null
})
const { disabled = false, media } = defineProps<{
  disabled?: boolean
  media?: MediaState
}>()
const emit = defineEmits<{ change: [] }>()
const { t } = useI18n()

const resolutions = computed(() => [
  ...[512, 1024, 2048].map((value) => ({ name: `${value} px`, value })),
  { name: t('astrophotoflow.media.originalResolution'), value: 'original' }
])
const balances = computed(() => [
  { name: t('astrophotoflow.media.defaultDisplay'), value: 'default' },
  { name: t('astrophotoflow.media.balanceRgb'), value: 'auto' },
  { name: t('astrophotoflow.media.preserveRgb'), value: 'preserve' }
])
const resolution = computed({
  get: () => maxEdge.value ?? 'original',
  set: (value: string | number | undefined) => {
    maxEdge.value =
      value === 'original'
        ? null
        : (value as MediaSelection['preview_max_edge'])
    emit('change')
  }
})
const rgbBalance = computed({
  get: () => balance.value ?? 'default',
  set: (value: string | number | undefined) => {
    balance.value =
      value === 'default' ? null : (value as MediaSelection['display_balance'])
    emit('change')
  }
})
const resolvedDisplay = computed(() => {
  if (balance.value != null || media?.status !== 'available') return ''
  if (media.channels?.length === 1)
    return t('astrophotoflow.media.monochromeDisplay')
  const recipe = media.display_recipe
  const stretch = recipe?.auto_stretch
  const gains =
    recipe?.display_white_balance ??
    (stretch && typeof stretch === 'object' && 'white_balance' in stretch
      ? stretch.white_balance
      : undefined)
  if (
    !Array.isArray(gains) ||
    gains.length !== 3 ||
    !gains.every((value) => typeof value === 'number' && Number.isFinite(value))
  )
    return ''
  return t(
    gains.every((value) => value === 1)
      ? 'astrophotoflow.media.preserveRgb'
      : 'astrophotoflow.media.balanceRgb'
  )
})
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-2 text-xs"
    @pointerdown.stop
    @keydown.stop
    @wheel.stop
  >
    <div class="flex items-center gap-1">
      <span>{{ t('astrophotoflow.media.previewResolution') }}</span>
      <SingleSelect
        v-model="resolution"
        :label="t('astrophotoflow.media.previewResolution')"
        :options="resolutions"
        :disabled
        size="md"
        density="compact"
      />
    </div>
    <div class="flex items-center gap-1">
      <span>{{ t('astrophotoflow.media.rgbDisplay') }}</span>
      <SingleSelect
        v-model="rgbBalance"
        :label="t('astrophotoflow.media.rgbDisplay')"
        :options="balances"
        :disabled
        size="md"
        density="compact"
      />
    </div>
    <span
      v-if="resolvedDisplay"
      class="basis-full text-muted-foreground"
      role="status"
      >{{
        t('astrophotoflow.media.currentDisplay', { mode: resolvedDisplay })
      }}</span
    >
  </div>
</template>
