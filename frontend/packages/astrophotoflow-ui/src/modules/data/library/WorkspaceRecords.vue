<script setup lang="ts">
import type { RecordsPresentation } from '../workspace/recordsTypes'
import ImportTasks from '../imports/ImportTasks.vue'
import RecordsFeedback from '../workspace/RecordsFeedback.vue'
import RecordsPagination from '../workspace/RecordsPagination.vue'
import LibraryTable from './LibraryTable.vue'
import DatasetReferenceTable from '../datasets/DatasetReferenceTable.vue'
import ProjectCards from '../projects/ProjectCards.vue'
import EquipmentCards from '../equipment/EquipmentCards.vue'
import EquipmentSetupTable from '../equipment/EquipmentSetupTable.vue'
defineProps<{ view: RecordsPresentation }>()
</script>
<template>
  <ImportTasks v-if="view.imports" v-bind="view.imports" />
  <RecordsFeedback v-bind="view.feedback" />
  <LibraryTable v-if="view.body.kind==='library'" v-bind="view.body.props" />
  <DatasetReferenceTable v-else-if="view.body.kind==='datasets'" v-bind="view.body.props" />
  <ProjectCards v-else-if="view.body.kind==='projects'" v-bind="view.body.props" />
  <EquipmentCards v-else-if="view.body.kind==='equipment'" v-bind="view.body.props" />
  <EquipmentSetupTable v-else-if="view.body.kind==='setups'" v-bind="view.body.props" />
  <RecordsPagination v-bind="view.pagination" />
  <p v-if="view.previewUnavailable" class="apf-disabled">{{ $t('apfUi.asset_previews_will_be_connected_in_a_later_stage') }}</p>
</template>
