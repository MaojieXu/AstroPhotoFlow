<script setup lang="ts">
import type { MediaSelection } from '@astrophotoflow/ui'
import { useI18n } from 'vue-i18n'

const maxEdge = defineModel<MediaSelection['preview_max_edge']>('maxEdge', { default: 1024 })
const balance = defineModel<MediaSelection['display_balance']>('balance', { default: null })
const { disabled = false } = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ change: [] }>()
const { t } = useI18n()
</script>

<template>
  <div class="flex flex-wrap items-center gap-2 text-xs" @pointerdown.stop @keydown.stop @wheel.stop>
    <label class="flex items-center gap-1">{{ t('astrophotoflow.media.previewResolution') }}<select v-model="maxEdge" :disabled class="rounded-sm border border-border-default bg-base-background p-1" @change="emit('change')"><option v-for="edge in [512, 1024, 2048]" :key="edge" :value="edge">{{ edge }} px</option><option :value="null">{{ t('astrophotoflow.media.originalResolution') }}</option></select></label>
    <label class="flex items-center gap-1">{{ t('astrophotoflow.media.rgbDisplay') }}<select v-model="balance" :disabled class="rounded-sm border border-border-default bg-base-background p-1" @change="emit('change')"><option :value="null">{{ t('astrophotoflow.media.defaultDisplay') }}</option><option value="auto">{{ t('astrophotoflow.media.balanceRgb') }}</option><option value="preserve">{{ t('astrophotoflow.media.preserveRgb') }}</option></select></label>
  </div>
</template>
