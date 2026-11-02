<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { uiT } from '../../../core/i18n'
import type { DatasetOut } from '../../../generated/api/types.gen'
import { useLibrarySelectionQuery, type LibrarySelectionRequest } from './selectionQueries'
import { useCreateDataset } from '../datasets/mutations'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibraryButton from '../components/LibraryButton.vue'
import { displayLabel } from './presentation'

const props = defineProps<{ workspace: string; recordsLoading: boolean }>()
const emit = defineEmits<{ dirty: [value: boolean]; created: [dataset: DatasetOut] }>()
let active = true
const creating = ref(false), chosen = ref<string[]>([])
const name = ref(''), notes = ref(''), frameType = ref('')
const request = computed<LibrarySelectionRequest | undefined>(() => creating.value
  ? { workspaceId: props.workspace, kind: 'assets', all: true, query: { role: 'calibration', limit: 200, offset: 0 } }
  : undefined)
// Opening is an explicit read; the chooser does not initiate periodic refreshes.
const photosQuery = useLibrarySelectionQuery(request, false, false)
const creation = useCreateDataset()
const loading = photosQuery.isFetching
const saving = creation.isPending
const visiblePhotos = computed(() => photosQuery.data.value?.kind === 'assets' && !loading.value
  ? photosQuery.data.value.page.items.filter(photo => !frameType.value || photo.classification?.frame_type === frameType.value)
  : [])
const error = computed(() => {
  const cause = creation.error.value ?? photosQuery.error.value
  return cause instanceof Error ? cause.message : cause ? uiT('apfUi.could_not_read_calibration_photos') : ''
})
watch(() => Boolean(creating.value && (name.value || notes.value || chosen.value.length)), value => emit('dirty', value))
watch(() => props.workspace, () => { creating.value = false; chosen.value = []; creation.reset() })
onBeforeUnmount(() => { active = false; emit('dirty', false) })
async function begin() {
  creation.reset()
  chosen.value = []; name.value = ''; notes.value = ''; creating.value = true
  await nextTick()
  await photosQuery.refetch({ cancelRefetch: false })
}
async function create() {
  const workspaceId = props.workspace
  try {
    const created = await creation.mutateAsync({ workspaceId, body: { name: name.value, notes: notes.value || null, asset_version_ids: [...chosen.value] } })
    if (!active || props.workspace !== workspaceId) return
    creating.value = false
    emit('created', created)
  } catch {
    // The mutation preserves its error and draft; no automatic retry occurs.
  }
}
</script>
<template>
  <section class="apf-calibration-library" :aria-label="$t('apfUi.independent_calibration_library')">
    <h2>{{ $t('apfUi.calibration_library') }}<LibraryInfo :label="$t('apfUi.calibration_library')" :text="$t('apfUi.bias_dark_flat_and_dark_flat_are_shown_separately_from_light_frames_ma')" /></h2>
    <LibraryButton type="button" :disabled="saving||recordsLoading" @click="begin">{{ $t('apfUi.create_a_group_from_existing_calibration_photos') }}</LibraryButton>
    <form v-if="creating" class="apf-editor" :aria-label="$t('apfUi.create_calibration_group')" @submit.prevent="create">
      <label>{{ $t('apfUi.calibration_group_name') }}<input v-model="name" :disabled="saving" required /></label><label>{{ $t('apfUi.description') }}<textarea v-model="notes" :disabled="saving" /></label>
      <label>{{ $t('apfUi.filter_by_frame_use_when_selecting') }}<select v-model="frameType" :disabled="saving"><option value="">{{ $t('apfUi.all_calibration_types') }}</option><option v-for="type in ['bias','dark','flat','dark_flat']" :key="type" :value="type">{{displayLabel(type)}}</option></select></label>
      <p>{{ $t('apfUi.explicitly_selected_versions_value_changing_the_frame_use_filter_retai', { p0: (chosen.length) }) }}</p>
      <p v-if="loading" role="status">{{ $t('apfUi.reading_imported_calibration_photos') }}</p>
      <div class="apf-calibration-photo-list"><label v-for="photo in visiblePhotos" :key="photo.id"><input v-if="photo.current_version_id" v-model="chosen" :disabled="saving" type="checkbox" :value="photo.current_version_id" />{{photo.name}} · {{displayLabel(photo.classification?.frame_type)}} · {{displayLabel(photo.classification?.frame_class)}} · v{{photo.current_version?.version_number}}</label></div>
      <LibraryButton type="button" :disabled="saving" @click="creating=false">{{ $t('apfUi.cancel') }}</LibraryButton><LibraryButton type="submit" variant="primary" :disabled="saving||loading||chosen.length===0">{{ $t('apfUi.create_logical_calibration_group') }}</LibraryButton>
    </form>
    <p v-if="error" role="alert" class="apf-error">{{error}}</p>
    <slot name="records" />
  </section>
</template>
<style scoped>
.apf-calibration-library>p,.apf-calibration-library>button{margin:10px}.apf-calibration-photo-list{max-height:280px;overflow:auto}.apf-calibration-photo-list label{display:flex;align-items:center;gap:8px;margin:8px 0}
</style>
