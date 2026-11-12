<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { isEqual } from 'es-toolkit'

import Button from '@/components/ui/button/Button.vue'
import type { ComponentWidget } from '@/scripts/domWidget'
import {
  nodeParameterDefaults,
  resetNodeParameters
} from './resetNodeParameters'

const { widget } = defineProps<{ widget: ComponentWidget<string | object> }>()
const { t } = useI18n()
const changed = computed(() =>
  nodeParameterDefaults(widget.node).some(
    (item) => !isEqual(item.widget.value, item.value)
  )
)
</script>

<template>
  <div class="flex h-7 items-center justify-end" @pointerdown.stop>
    <Button
      variant="textonly"
      size="icon-sm"
      :disabled="!changed"
      :aria-label="t('astrophotoflow.nodeUi.resetParameters')"
      :title="t('astrophotoflow.nodeUi.resetParameters')"
      @click="resetNodeParameters(widget.node)"
    >
      <i class="icon-[lucide--rotate-ccw] size-3.5" aria-hidden="true" />
    </Button>
  </div>
</template>
