<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ComponentWidget } from '@/scripts/domWidget'
import { bundleNodeIssue } from '../sidebar/bundleCatalog'

const { widget } = defineProps<{ widget: ComponentWidget<string> }>()
const { t } = useI18n()
const issue = computed(() => bundleNodeIssue(widget.node))
</script>

<template>
  <p v-if="issue" role="status" class="px-2 py-1 text-xs text-error">
    {{ t(issue) }}
  </p>
</template>
