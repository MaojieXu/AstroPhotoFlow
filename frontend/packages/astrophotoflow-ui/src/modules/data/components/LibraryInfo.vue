<script setup lang="ts">
import LibraryButton from './LibraryButton.vue'

const { text, label } = defineProps<{ text: string; label: string }>()
</script>

<template>
  <LibraryButton :tooltip="text" :aria-label="label + $t('apfUi.description_4262c4')" variant="textonly" class="apf-info" @click.stop.prevent><i class="pi pi-info-circle" aria-hidden="true" /></LibraryButton>
</template>
