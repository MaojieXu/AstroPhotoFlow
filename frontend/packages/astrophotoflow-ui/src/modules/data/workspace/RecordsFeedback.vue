<script setup lang="ts">
defineProps<{
  capabilityError?: string
  inlineError: string
  librarySelecting: boolean
  projectSelecting: boolean
  notice: string
  readError?: { message: string; requestId?: string }
  loading: boolean
  emptyMessage?: string
}>()
</script>
<template>
  <p v-if="capabilityError" class="apf-error" role="alert">{{ $t('apfUi.could_not_read_capability_status_value', { p0: capabilityError }) }}</p>
  <p v-if="inlineError" class="apf-error" role="alert">{{inlineError}}</p>
  <p v-if="librarySelecting" class="apf-state">{{ $t('apfUi.remove_only_the_library_reference_retain_the_original_data') }}</p>
  <p v-if="projectSelecting" class="apf-state">{{ $t('apfUi.select_projects_to_move_to_trash_they_can_be_restored_there') }}</p>
  <p v-if="notice" class="apf-state" role="status">{{notice}}</p>
  <p v-if="readError" class="apf-error" role="alert">{{readError.message}}<span v-if="readError.requestId">{{ $t('apfUi.request_id_value', { p0: readError.requestId }) }}</span></p>
  <p v-if="loading" class="apf-state" role="status">{{ $t('apfUi.reading_service_data') }}</p>
  <section v-if="!loading&&!readError&&emptyMessage" class="apf-state" role="status">{{emptyMessage}}</section>
</template>
