<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import ImportTasks from './ImportTasks.vue'
import FixedDatasetMembers from './FixedDatasetMembers.vue'
import InlineField from './InlineField.vue'
import ParameterModeField from './ParameterModeField.vue'
import LibraryInfo from './LibraryInfo.vue'
import LibraryButton from './LibraryButton.vue'
import LibraryCheckbox from './LibraryCheckbox.vue'
import LibraryCanvasSource from './LibraryCanvasSource.vue'
import EquipmentSetupTable from './EquipmentSetupTable.vue'

export default {
  components: { FixedDatasetMembers, ImportTasks, InlineField, ParameterModeField, LibraryInfo, LibraryButton, LibraryCheckbox, LibraryCanvasSource, EquipmentSetupTable },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>
          <ImportTasks v-if="isLibraryItemsView" :refresh-token="progressRefreshToken" :watch-task-ids="watchedTaskIds" :workspace="importWorkspace" @completed="importTaskCompleted" @registered="importRegistrationCompleted" @succeeded="notifyImportSuccess" @notice="notifyImport" />
          <p v-if="capabilityError" class="apf-error" role="alert">{{ $t('apfUi.could_not_read_capability_status_value', { p0: (errorText(capabilityError)) }) }}</p>
          <p v-if="inlineSaveFailure" class="apf-error" role="alert">{{inlineSaveFailure}}</p>
          <p v-if="bulkSelectMode" class="apf-state">{{ $t('apfUi.remove_only_the_library_reference_retain_the_original_data') }}</p>
          <p v-if="managementSelectMode&&!isEquipmentManagement" class="apf-state">{{ $t('apfUi.select_projects_to_move_to_trash_they_can_be_restored_there') }}</p>
          <p v-if="bulkDeleteNotice" class="apf-state" role="status">{{bulkDeleteNotice}}</p>
          <p v-if="error" class="apf-error" role="alert">{{ errorText(error) }}<span v-if="error.requestId">{{ $t('apfUi.request_id_value', { p0: (error.requestId) }) }}</span></p>
          <p v-if="loading" class="apf-state" role="status">{{ $t('apfUi.reading_service_data') }}</p>
          <section v-if="!loading && !error && rows.length === 0" class="apf-state" role="status">
            <template v-if="activeDataset">{{ $t('apfUi.this_image_group_has_no_members') }}</template>
            <template v-else-if="isEquipmentManagement&&(store.query||equipmentKindFilter)">{{ $t('apfUi.no_matching_records_adjust_the_search_or_equipment_category') }}</template>
            <template v-else-if="isEquipmentManagement">{{store.section==='equipment-setups'?$t('apfUi.no_equipment_setups_yet'):$t('apfUi.no_equipment_yet')}}</template>
            <template v-else-if="store.query || activeFilterCount">{{ $t('apfUi.no_matching_records_adjust_the_search_or_filters') }}</template>
            <template v-else-if="activeArea==='library' && libraryCategory!=='all'">{{ $t('apfUi.no_assets_in_this_category_check_all_assets_or_import_files_for_this_f') }}</template>
            <template v-else-if="activeArea==='library'">{{ $t('apfUi.your_library_is_empty_click_import_to_select_files_or_a_folder') }}</template>
            <template v-else>{{ $t('apfUi.no_records_here_yet_use_the_create_action_above') }}</template>
          </section>

          <EquipmentSetupTable v-if="activeArea==='settings'&&store.section==='equipment-setups'" />
          <div v-else-if="!loading && (rows.length || activeArea === 'library') && isAssetTable" class="apf-table-scroll" :class="activeArea==='library'?libraryViewMode:'detail'">
            <table :class="['apf-assets-table',{'is-selecting':bulkSelectMode,'is-deleting':bulkDeleteBusy}]">
              <thead><tr>
                <th v-if="bulkSelectMode&&isLibraryItemsView"><LibraryCheckbox :label="$t('apfUi.select_current_page')" :model-value="pageAllSelected" :indeterminate="pagePartiallySelected" :disabled="rows.length===0||bulkDeleteBusy" @update:model-value="togglePageSelection" /></th>
                <th class="apf-column-preview">{{ $t('apfUi.preview') }}</th>
                <th class="apf-column-name" :aria-sort="isLibraryTableView?sortAria('name'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('name')">{{ $t('apfUi.namevalue', { p0: (sortArrow('name')) }) }}</LibraryButton><template v-else>{{ $t('apfUi.name') }}</template></th>
                <th class="apf-column-classification" :aria-sort="isLibraryTableView?sortAria('classification'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('classification')">{{ $t('apfUi.classificationvalue', { p0: (sortArrow('classification')) }) }}</LibraryButton><template v-else>{{ $t('apfUi.classification') }}</template></th>
                <th class="apf-column-camera" :aria-sort="isLibraryTableView?sortAria('camera'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('camera')">{{ $t('apfUi.cameravalue', { p0: (sortArrow('camera')) }) }}</LibraryButton><template v-else>{{ $t('apfUi.camera_dacf07') }}</template></th>
                <th class="apf-column-parameter" :aria-sort="isLibraryTableView?sortAria('parameter_mode'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('parameter_mode')">ISO／Gain{{sortArrow('parameter_mode')}}</LibraryButton><template v-else>ISO／Gain</template></th>
                <th class="apf-column-exposure" :aria-sort="isLibraryTableView?sortAria('exposure_seconds'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('exposure_seconds')">{{ $t('apfUi.exposurevalue', { p0: (sortArrow('exposure_seconds')) }) }}</LibraryButton><template v-else>{{ $t('apfUi.exposure_bc7dac') }}</template></th>
                <th class="apf-column-temperature" :aria-sort="isLibraryTableView?sortAria('sensor_temperature_c'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('sensor_temperature_c')">{{ $t('apfUi.temperaturevalue', { p0: (sortArrow('sensor_temperature_c')) }) }}</LibraryButton><template v-else>{{ $t('apfUi.temperature') }}</template></th>
                <template v-if="libraryViewMode==='detail'&&isLibraryTableView">
                  <th :aria-sort="sortAria('binning')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('binning')">Bin{{sortArrow('binning')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('cfa_pattern')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('cfa_pattern')">CFA{{sortArrow('cfa_pattern')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('optical_system')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('optical_system')">{{ $t('apfUi.imaging_systemvalue', { p0: (sortArrow('optical_system')) }) }}</LibraryButton></th>
                  <th :aria-sort="sortAria('filter')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('filter')">{{ $t('apfUi.filtervalue', { p0: (sortArrow('filter')) }) }}</LibraryButton></th>
                  <th :aria-sort="sortAria('integration_seconds')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('integration_seconds')">{{ $t('apfUi.total_exposurevalue', { p0: (sortArrow('integration_seconds')) }) }}</LibraryButton></th>
                  <th :aria-sort="sortAria('storage_mode')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('storage_mode')">{{ $t('apfUi.storagevalue', { p0: (sortArrow('storage_mode')) }) }}</LibraryButton></th>
                  <th :aria-sort="sortAria('status')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('status')">{{ $t('apfUi.statusvalue', { p0: (sortArrow('status')) }) }}</LibraryButton></th>
                  <th :aria-sort="sortAria('notes')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('notes')">{{ $t('apfUi.notesvalue', { p0: (sortArrow('notes')) }) }}</LibraryButton></th>
                </template>
                <template v-else-if="activeArea!=='library'"><th>{{ $t('apfUi.imaging_system') }}</th><th>{{ $t('apfUi.filter') }}</th><th>{{ $t('apfUi.storage') }}</th><th>{{ $t('apfUi.status') }}</th><th>{{ $t('apfUi.notes') }}</th></template></tr></thead>
              <tbody>
                <LibraryCanvasSource v-for="row in rows" :key="row.entry_type+':'+row.id" as="tr" :source="canvasSource(row)" click-target=".apf-material-name" :aria-selected="bulkSelectMode?bulkSelection.has(bulkKey(row)):selected?.id===row.id" @click="onLibraryRowClick(row,$event)" @dblclick.capture="bulkSelectMode?$event.stopPropagation():undefined">
                <td v-if="bulkSelectMode&&isLibraryItemsView"><span @click.stop><LibraryCheckbox :label="$t('apfUi.select_beb481')+itemTitle(row)" :model-value="bulkSelection.has(bulkKey(row))" :disabled="bulkDeleteBusy" @update:model-value="toggleBulkSelection(row)" /></span></td>
                <td><button type="button" class="apf-thumb" :aria-label="$t('apfUi.view') + itemTitle(row) + $t('apfUi.full_size')" @click.stop="openPhotoPreview(row)">
                  <img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" :draggable="false" />
                  <span v-else>{{ $t('apfUi.no_preview_yet') }}</span>
                </button></td>
                <td class="apf-column-name"><InlineField class="apf-material-name" :value="itemTitle(row)" :title="itemTitle(row)" :save="value=>saveRowField(row,'name',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'name'))" /><template v-if="row.entry_type==='dataset'"><button type="button" class="apf-member-open" @click.stop="openDataset(row)">{{ $t('apfUi.image_group_photos_value', { p0: (row.version?.members?.length??row.member_count??0) }) }}</button><small v-if="datasetRawValue(row,member=>member.asset?.classification?.frame_type)==='mixed'">{{ $t('apfUi.mixed_use_group_open_to_see_all_members') }}</small></template><small v-else>{{itemSubtitle(row)}}</small><small v-if="row.import_issue" class="apf-processing-issue" role="status">{{row.import_issue.includes($t('apfUi.parse'))?$t('apfUi.parsing_failed'):$t('apfUi.metadata_processing_issue')}} · {{displayLabel(row.version?.availability??row.current_version?.availability)}}<LibraryInfo :label="itemTitle(row)+$t('apfUi.processing_status')" :text="row.import_issue.replace($t('apfUi.original_files_will_continue_to_be_ingested'),$t('apfUi.use_the_current_original_readiness_status_as_the_authority'))" /></small><small v-if="isLibraryTableView" class="apf-content-state" role="status">{{materialReadiness(row)}}</small><small class="apf-compact-meta">{{parameterModeDisplay(row)}}</small></td>
                <td v-if="row.entry_type==='dataset'" class="apf-column-classification">
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_class)" :display="datasetValue(row,member=>member.asset?.classification?.frame_class,frameClassLabel)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...frameClasses.map(value=>({value,label:frameClassLabel(value)}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_type)" :display="datasetValue(row,member=>member.asset?.classification?.frame_type,frameTypeLabel)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...frameTypes.map(value=>({value,label:frameTypeLabel(value)}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td v-else class="apf-column-classification">
                  <InlineField :value="rowClassification(row).frame_class??''" :display="frameClassLabel(rowClassification(row).frame_class)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...frameClasses.map(value=>({value,label:frameClassLabel(value)}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField v-if="rowClassification(row).frame_class!=='video'" :value="rowClassification(row).frame_type??''" :display="frameTypeLabel(rowClassification(row).frame_type)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...frameTypes.map(value=>({value,label:frameTypeLabel(value)}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td class="apf-column-camera"><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.camera_id):rowParameters(row).camera_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'camera_id',Boolean(row.project_id))):materialEquipmentName(row,'camera_id')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.camera_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="value=>saveRowField(row,'camera_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'camera_id'))" /></td>
                <td class="apf-column-parameter">
                  <LibraryInfo :label="$t('apfUi.parameter_source')" :text="$t('apfUi.parameter_mode_is_not_inferred_automatically_from_file_values')+['iso','gain','offset'].filter(key=>rowAsset(row).value_sources?.[key]).map(key=>key+'：'+displayLabel(rowAsset(row).value_sources[key])).join('\n')" /><ParameterModeField :value="parameterModeValue(row)" :display="parameterModeDisplay(row)" unset-mode="standard" :save="changes=>saveParameterGroup(row,changes)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'parameter_mode'))" />
                </td>
                <td class="apf-column-exposure"><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds):rowParameters(row).exposure_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.exposure_seconds,value=>value==null?$t('apfUi.not_specified'):String(value)+' s'):captureValue(rowParameters(row).exposure_seconds)+(rowParameters(row).exposure_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'exposure_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'exposure_seconds'))" /></td>
                <td class="apf-column-temperature"><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c):rowParameters(row).sensor_temperature_c" :display="row.entry_type==='dataset'?datasetTemperature(row):rowParameters(row).sensor_temperature_c==null?$t('apfUi.not_specified'):displayTemperature(rowParameters(row).sensor_temperature_c)+' °C'" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'sensor_temperature_c',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'sensor_temperature_c'))" /></td>
                <template v-if="libraryViewMode==='detail'&&isLibraryTableView">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>binEditValue(member.asset?.parameters??{})):binEditValue(rowParameters(row))" :display="row.entry_type==='dataset'?datasetValue(row,member=>binValue(member.asset?.parameters??{}),value=>String(value??$t('apfUi.not_specified'))):binValue(rowParameters(row))??$t('apfUi.not_specified')" kind="select" :choices="row.entry_type==='dataset'?datasetBinChoices(row):binEditChoices(rowParameters(row))" :save="value=>saveBin(row,value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'binning'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.cfa_pattern):rowParameters(row).cfa_pattern??''" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.cfa_pattern,cfaLabel):cfaLabel(rowParameters(row).cfa_pattern)" kind="select" :choices="row.entry_type==='dataset'?[...cfaChoices,{value:'mixed',label:$t('apfUi.mixed'),disabled:true}]:cfaChoices" :save="value=>saveRowField(row,'cfa_pattern',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'cfa_pattern'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'optical_system_id',Boolean(row.project_id))):materialEquipmentName(row,'optical_system_id')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'filter_id',Boolean(row.project_id))):materialEquipmentName(row,'filter_id')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.filter_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds):rowParameters(row).integration_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.integration_seconds,value=>value==null?$t('apfUi.not_specified'):String(value)+' s'):captureValue(rowParameters(row).integration_seconds)+(rowParameters(row).integration_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'integration_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'integration_seconds'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode,displayLabel):displayLabel(row.version?.storage_mode??row.current_version?.storage_mode)}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" :display="displayLabel(rowAsset(row).status??'active')" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue ? $t('apfUi.metadata_processing_issue') : displayLabel(row.version?.availability??row.current_version?.availability)}}</small></td>
                  <td class="apf-note-cell"><InlineField :value="row.entry_type==='dataset'?row.dataset?.notes:rowAsset(row).notes" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
                <template v-else-if="activeArea!=='library'">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'optical_system_id',Boolean(row.project_id))):materialEquipmentName(row,'optical_system_id')" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'filter_id',Boolean(row.project_id))):materialEquipmentName(row,'filter_id')" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},{value:'mixed',label:$t('apfUi.mixed'),disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode,displayLabel):displayLabel(row.version?.storage_mode??row.current_version?.storage_mode)}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" :display="displayLabel(rowAsset(row).status??'active')" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue ? $t('apfUi.metadata_processing_issue') : displayLabel(row.version?.availability??row.current_version?.availability)}}</small></td>
                  <td><InlineField :value="rowAsset(row).notes" :display="rowAsset(row).notes??'—'" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
              </LibraryCanvasSource></tbody>
            </table>
          </div>
          <div v-else-if="!loading && rows.length && isDatasetTable" class="apf-table-scroll">
            <table class="apf-assets-table apf-dataset-table">
              <thead><tr><th>{{ $t('apfUi.cover') }}</th><th>{{ $t('apfUi.image_group') }}</th><th>{{ $t('apfUi.classification') }}</th><th>{{ $t('apfUi.member_count') }}</th><th>{{ $t('apfUi.camera_dacf07') }}</th><th>ISO／Gain</th><th>{{ $t('apfUi.exposure_bc7dac') }}</th><th>{{ $t('apfUi.temperature') }}</th><th>{{ $t('apfUi.imaging_system') }}</th><th>{{ $t('apfUi.filter') }}</th><th>{{ $t('apfUi.storage') }}</th><th>{{ $t('apfUi.status') }}</th><th>{{ $t('apfUi.notes') }}</th><th>{{ $t('apfUi.fixed_version_photos') }}</th></tr></thead>
              <tbody><tr v-for="row in rows" :key="row.id" :aria-selected="selected?.id===row.id" @click="selectRow(row)">
                <td><button type="button" class="apf-thumb" :aria-label="$t('apfUi.view') + itemTitle(row) + $t('apfUi.full_size')" @click.stop="openPhotoPreview(row)"><img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" /><span v-else>{{ $t('apfUi.no_preview_yet') }}</span></button></td>
                <td><strong>{{row.dataset?.name??row.name}}</strong><small>{{row.dataset_version_id?$t('apfUi.project_fixed_versions'):$t('apfUi.image_group')}}</small></td>
                <td>{{datasetClassification(row)}}</td>
                <td>{{row.version?.members?.length??row.member_count??'—'}}</td>
                <td>{{datasetValue(row,member=>materialEquipmentValue(member,'camera_id',Boolean(row.project_id)))}}</td>
                <td>{{parameterModeDisplay({...row,entry_type:'dataset'})}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.exposure_seconds, value=>captureValue(value)+' s')}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.sensor_temperature_c, value=>captureValue(value)+' °C')}}</td>
                <td>{{datasetValue(row,member=>materialEquipmentValue(member,'optical_system_id',Boolean(row.project_id)))}}</td>
                <td>{{datasetValue(row,member=>materialEquipmentValue(member,'filter_id',Boolean(row.project_id)))}}</td>
                <td>{{datasetValue(row, member=>member.version?.storage_mode, displayLabel)}}</td>
                <td>{{displayLabel(row.dataset?.status??row.status)}}</td><td class="apf-note-cell">{{row.dataset?.notes??row.notes??'—'}}</td>
                <td><FixedDatasetMembers :members="row.version?.members??[]" /></td>
              </tr></tbody>
            </table>
          </div>
          <section v-else-if="!loading && rows.length && !isAssetTable && !isDatasetTable" :class="['apf-records', store.layout]">
            <label v-if="managementSelectMode" class="apf-management-select-page"><LibraryCheckbox :label="$t('apfUi.select_current_page')" :model-value="managementPageAllSelected" :indeterminate="managementPagePartiallySelected" :disabled="isEquipmentManagement&&managementFilterBlocked" @update:model-value="toggleManagementPage" />{{ $t('apfUi.select_current_page') }}</label>
            <template v-for="row in rows" :key="row.id">
              <div v-if="isEquipmentManagement" class="apf-equipment-record" role="group" :aria-label="$t('apfUi.equipment_0221ba')+itemTitle(row)">
                <LibraryCheckbox v-if="managementSelectMode" :label="$t('apfUi.select_beb481')+itemTitle(row)" :model-value="managementSelection.has(store.section+':'+row.id)" :disabled="managementFilterBlocked" @update:model-value="toggleManagementSelection(row)" />
                <button type="button" :class="['apf-record', selected?.id === row.id ? 'selected' : '']" :aria-label="$t('apfUi.select_equipment')+itemTitle(row)" :aria-pressed="selected?.id===row.id" :disabled="managementSelectMode||managementFilterBlocked" @click="selectRow(row)">
                  <i :class="[equipmentKindIcons[row.kind],'size-4 shrink-0 text-muted-foreground']" aria-hidden="true" />
                  <span><strong>{{itemTitle(row)}}</strong><small>{{itemSubtitle(row)}}</small></span>
                </button>
                <span class="apf-equipment-edit-slot"><LibraryButton v-if="store.section==='equipment'&&selected?.id===row.id" type="button" :aria-label="$t('apfUi.edit_equipment_86df54')+itemTitle(row)" :disabled="managementFilterBlocked||loading" @click="editEquipment(row)">{{ $t('apfUi.edit') }}</LibraryButton></span>
              </div>
              <label v-else-if="managementSelectMode" class="apf-management-record-select" @click.stop>
                <input type="checkbox" :aria-label="$t('apfUi.select_beb481')+itemTitle(row)" :checked="managementSelection.has(store.section+':'+row.id)" @change="toggleManagementSelection(row)" />
                <span class="apf-record-icon">{{ row.kind ? '◉' : '▣' }}</span>
                <span><strong>{{ itemTitle(row) }}</strong><small>{{ itemSubtitle(row) }}</small></span>
              </label>
              <button v-else type="button" :class="['apf-record', selected?.id === row.id ? 'selected' : '']" @click="selectRow(row)">
                <span class="apf-record-icon">{{ row.asset ? '✦' : row.kind ? '◉' : row.camera_id ? '⚙' : '▣' }}</span>
                <span><strong>{{ itemTitle(row) }}</strong><small>{{ itemSubtitle(row) }}</small></span>
              </button>
            </template>
          </section>
          <footer v-if="!isEquipmentManagement||(!loading&&!error&&total>50)" class="apf-pagination">
            <span>{{ $t('apfUi.records_value', { p0: (total) }) }}</span>
            <label v-if="!isEquipmentManagement&&activeArea!=='library'">{{ $t('apfUi.show_per_page') }}<select :aria-label="$t('apfUi.number_of_items_per_page')" :value="store.pageSize" :disabled="loading||bulkDeleteBusy||setupDirty" @change="store.setPageSize(($event.target as HTMLSelectElement).value==='all'?'all':Number(($event.target as HTMLSelectElement).value) as 10|20|50)">
                <option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="all">{{ $t('apfUi.all') }}</option>
              </select>
            </label>
            <template v-if="recordPageSize!=='all'&&(activeArea!=='library'||total>recordPageSize)">
              <button type="button" :disabled="store.offset === 0 || loading || bulkDeleteBusy || setupDirty" @click="store.movePage(-recordPageSize)">{{ $t('apfUi.previous_page') }}</button>
              <button type="button" :disabled="store.offset + rows.length >= total || loading || bulkDeleteBusy || setupDirty" @click="store.movePage(recordPageSize)">{{ $t('apfUi.next_page') }}</button>
            </template>
          </footer>
          <p v-if="isAssetSection && capabilities && !capabilities.asset_preview" class="apf-disabled">{{ $t('apfUi.asset_previews_will_be_connected_in_a_later_stage') }}</p>
</template>
