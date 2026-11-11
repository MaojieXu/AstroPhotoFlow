<script setup lang="ts">
import type { DatasetOut } from '../../../generated/api/types.gen'
import InlineField from '../components/InlineField.vue'
import { displayLabel } from '../library/presentation'
type SaveField = InstanceType<typeof InlineField>['$props']['save']
defineProps<{ dataset: DatasetOut; recordId: string; saveName: SaveField; saveStatus: SaveField; saveNotes: SaveField }>()
const emit = defineEmits<{ 'cancel-field': [field: 'name' | 'status' | 'notes', recordId: string] }>()
</script>
<template>
  <div class="apf-detail-fields">
    <p v-if="dataset.in_trash" role="status">{{ $t('apfUi.object_in_trash') }}</p>
    <section v-if="dataset.referencing_projects?.length">
      <p>{{ $t('apfUi.dataset_shared_projects') }}</p>
      <ul><li v-for="project in dataset.referencing_projects" :key="project.id">{{ project.name }}</li></ul>
    </section>
    <section v-if="dataset.capture_diagnostics?.warnings?.length" role="status">
      <p>{{ $t('apfUi.capture_differences_warning') }}</p>
      <ul><li v-for="warning in dataset.capture_diagnostics?.warnings" :key="warning.field">
        {{ warning.field }}
        <ul><li v-for="member in warning.members" :key="member.asset_id">{{ member.asset_id }} · {{ member.value }}</li></ul>
      </li></ul>
    </section>
    <details><summary>{{ $t('apfUi.capture_unknown_counts') }}</summary>
      <ul><li v-for="(count,field) in dataset.capture_diagnostics?.unknown_counts" :key="field">{{ field }} · {{ count }}</li></ul>
    </details>
    <label>{{ $t('apfUi.calibration_status') }}<output>{{ displayLabel(dataset.calibration_status) }}</output></label>
    <p>{{ $t('apfUi.calibration_counts', {uncalibrated:dataset.calibration_counts.UnCalibrated,calibrated:dataset.calibration_counts.Calibrated,unknown:dataset.calibration_counts.Unknown}) }}</p>
    <label>{{ $t('apfUi.image_group_name') }}<InlineField :value="dataset.name" :save="saveName" @cancelled="emit('cancel-field','name',recordId)" /></label>
    <label>{{ $t('apfUi.status') }}<InlineField :value="dataset.status" :display="displayLabel(dataset.status)" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="saveStatus" @cancelled="emit('cancel-field','status',recordId)" /></label>
    <label>{{ $t('apfUi.notes') }}<InlineField :value="dataset.notes" kind="textarea" :save="saveNotes" @cancelled="emit('cancel-field','notes',recordId)" /></label>
  </div>
</template>
