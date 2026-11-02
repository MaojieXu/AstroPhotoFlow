<script setup lang="ts">
import { computed } from 'vue'
import { uiT } from '../../../core/i18n'
import type { LibraryTableRow } from './tableTypes'
import InlineField from '../components/InlineField.vue'
import ParameterModeField from '../equipment/ParameterModeField.vue'
import LibraryInfo from '../components/LibraryInfo.vue'
import LibraryButton from '../components/LibraryButton.vue'
import LibraryCheckbox from '../components/LibraryCheckbox.vue'
import LibraryCanvasSource from './LibraryCanvasSource.vue'
const props = defineProps<{
  rows: readonly LibraryTableRow[]
  library: boolean
  viewMode: 'simple' | 'detail'
  sortable: boolean
  sort: { by: string; order: 'asc' | 'desc' }
  selectMode: boolean
  selectionAllowed: boolean
  deleting: boolean
  allSelected: boolean
  partiallySelected: boolean
}>()
const emit = defineEmits<{
  sort: [field: string]
  'row-click': [recordKey: string, event: MouseEvent]
  preview: [recordKey: string]
  'open-dataset': [recordKey: string]
  toggle: [recordKey: string]
  'toggle-page': [selected: boolean]
}>()
const columns = computed(() => {
  const base = [
    {key:'name',label:uiT('apfUi.name'),className:'apf-column-name'},
    {key:'classification',label:uiT('apfUi.classification'),className:'apf-column-classification'},
    {key:'camera',label:uiT('apfUi.camera_dacf07'),className:'apf-column-camera'},
    {key:'parameter_mode',label:'ISO／Gain',className:'apf-column-parameter'},
    {key:'exposure_seconds',label:uiT('apfUi.exposure_bc7dac'),className:'apf-column-exposure'},
    {key:'sensor_temperature_c',label:uiT('apfUi.temperature'),className:'apf-column-temperature'}
  ].map(column=>({...column,sortable:props.sortable}))
  const extras = props.viewMode==='detail'&&props.sortable
    ? [['binning','Bin'],['cfa_pattern','CFA'],['optical_system',uiT('apfUi.imaging_system')],['filter',uiT('apfUi.filter')],['integration_seconds',uiT('apfUi.total_exposurevalue',{p0:''})],['storage_mode',uiT('apfUi.storage')],['status',uiT('apfUi.status')],['notes',uiT('apfUi.notes')]]
    : !props.library ? [['optical_system',uiT('apfUi.imaging_system')],['filter',uiT('apfUi.filter')],['storage_mode',uiT('apfUi.storage')],['status',uiT('apfUi.status')],['notes',uiT('apfUi.notes')]] : []
  return [...base,...extras.map(([key,label])=>({key,label,className:'',sortable:props.sortable}))]
})
function aria(field:string) { return props.sort.by===field?(props.sort.order==='asc'?'ascending':'descending'):undefined }
function arrow(field:string) { return props.sort.by===field?(props.sort.order==='asc'?' ▲':' ▼'):'' }
</script>
<template>
  <div class="apf-table-scroll" :class="library?viewMode:'detail'">
    <table :class="['apf-assets-table',{'is-selecting':selectMode,'is-deleting':deleting}]">
      <thead><tr>
        <th v-if="selectMode&&selectionAllowed"><LibraryCheckbox :label="$t('apfUi.select_current_page')" :model-value="allSelected" :indeterminate="partiallySelected" :disabled="!rows.length||deleting" @update:model-value="emit('toggle-page',$event)" /></th>
        <th class="apf-column-preview">{{ $t('apfUi.preview') }}</th>
        <th v-for="column in columns" :key="column.key" :class="column.className" :aria-sort="column.sortable?aria(column.key):undefined">
          <LibraryButton v-if="column.sortable" variant="textonly" class="apf-sort-button" @click="emit('sort',column.key)">{{column.label}}{{arrow(column.key)}}</LibraryButton><template v-else>{{column.label}}</template>
        </th>
      </tr></thead>
              <tbody>
                <LibraryCanvasSource v-for="row in rows" :key="row.key" as="tr" :source="row.source" click-target=".apf-material-name" :aria-selected="row.selected" @click="emit('row-click',row.key,$event)" @dblclick.capture="selectMode?$event.stopPropagation():undefined">
                <td v-if="selectMode&&selectionAllowed"><span @click.stop><LibraryCheckbox :label="$t('apfUi.select_beb481')+row.title" :model-value="row.selected" :disabled="deleting" @update:model-value="emit('toggle',row.key)" /></span></td>
                <td><button type="button" class="apf-thumb" :aria-label="$t('apfUi.view') + row.title + $t('apfUi.full_size')" @click.stop="emit('preview',row.key)">
                  <img v-if="row.thumbnail" :src="row.thumbnail" alt="" :draggable="false" />
                  <span v-else>{{ $t('apfUi.no_preview_yet') }}</span>
                </button></td>
                <td class="apf-column-name"><InlineField class="apf-material-name" v-bind="row.fields.name" /><template v-if="row.dataset"><button type="button" class="apf-member-open" @click.stop="emit('open-dataset',row.key)">{{ $t('apfUi.image_group_photos_value', { p0: (row.memberCount) }) }}</button><small v-if="row.mixedUse">{{ $t('apfUi.mixed_use_group_open_to_see_all_members') }}</small></template><small v-else>{{row.subtitle}}</small><small v-if="row.issue" class="apf-processing-issue" role="status">{{row.issue.label}} · {{row.issue.availability}}<LibraryInfo :label="row.title+$t('apfUi.processing_status')" :text="row.issue.text" /></small><small v-if="sortable" class="apf-content-state" role="status">{{row.readiness}}</small><small class="apf-compact-meta">{{row.parametersDisplay}}</small></td>
                <td v-if="row.dataset" class="apf-column-classification">
                  <InlineField v-bind="row.fields.groupClass" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField v-bind="row.fields.groupType" />
                </td>
                <td v-else class="apf-column-classification">
                  <InlineField v-bind="row.fields.assetClass" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField v-if="!row.video" v-bind="row.fields.assetType" />
                </td>
                <td class="apf-column-camera"><InlineField v-bind="row.fields.camera" /></td>
                <td class="apf-column-parameter">
                  <LibraryInfo :label="$t('apfUi.parameter_source')" :text="row.parameterSource" /><ParameterModeField v-bind="row.fields.parameters" />
                </td>
                <td class="apf-column-exposure"><InlineField v-bind="row.fields.exposure" /></td>
                <td class="apf-column-temperature"><InlineField v-bind="row.fields.temperature" /></td>
                <template v-if="viewMode==='detail'&&sortable">
                  <td><InlineField v-bind="row.fields.binning" /></td>
                  <td><InlineField v-bind="row.fields.cfa" /></td>
                  <td><InlineField v-bind="row.fields.opticalSystem" /></td>
                  <td><InlineField v-bind="row.fields.filter" /></td>
                  <td><InlineField v-bind="row.fields.integration" /></td>
                  <td>{{row.storage}}</td>
                  <td><InlineField v-bind="row.fields.status" /><small>{{row.availability}}</small></td>
                  <td class="apf-note-cell"><InlineField v-bind="row.fields.notes" /></td>
                </template>
                <template v-else-if="!library">
                  <td><InlineField v-bind="row.fields.opticalSystemReference" /></td>
                  <td><InlineField v-bind="row.fields.filterReference" /></td>
                  <td>{{row.storage}}</td>
                  <td><InlineField v-bind="row.fields.statusReference" /><small>{{row.availability}}</small></td>
                  <td><InlineField v-bind="row.fields.notesReference" /></td>
                </template>
              </LibraryCanvasSource></tbody>
    </table>
  </div>
</template>
