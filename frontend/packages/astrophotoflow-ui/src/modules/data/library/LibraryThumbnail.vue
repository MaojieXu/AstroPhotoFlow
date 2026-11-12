<script setup lang="ts">
import { computed, onMounted, onScopeDispose, useTemplateRef } from 'vue'

const { read, fallback, prioritize } = defineProps<{
  read?: () => string | undefined
  fallback?: string
  prioritize?: () => void
}>()
const url = computed(() => read?.() ?? fallback)
const element = useTemplateRef<HTMLSpanElement>('element')
let observer: IntersectionObserver | undefined
onMounted(() => {
  if (!element.value || typeof IntersectionObserver === 'undefined') return
  observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) prioritize?.()
  }, {rootMargin:'100px'})
  observer.observe(element.value)
})
onScopeDispose(() => observer?.disconnect())
</script>

<template>
  <span ref="element" class="inline-flex size-full items-center justify-center">
    <img v-if="url" :src="url" alt="" :draggable="false" />
    <span v-else>{{ $t('apfUi.no_preview_yet') }}</span>
  </span>
</template>
