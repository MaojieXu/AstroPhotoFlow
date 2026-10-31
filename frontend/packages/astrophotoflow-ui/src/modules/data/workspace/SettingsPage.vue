<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import InlineField from './InlineField.vue'
import ParameterModeField from './ParameterModeField.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'
import AssetContentChange from './AssetContentChange.vue'
import LibraryInfo from './LibraryInfo.vue'
import LibraryButton from './LibraryButton.vue'
import LibraryTextField from './LibraryTextField.vue'
import LibraryDialog from './LibraryDialog.vue'
import LibrarySelect from './LibrarySelect.vue'
import EquipmentFields from './EquipmentFields.vue'
import type { EquipmentDraft } from './EquipmentFields.vue'

export default {
  components: { InlineField, ParameterModeField, WorkspaceRecords, AssetContentChange, LibraryInfo, LibraryButton, LibraryTextField, LibraryDialog, LibrarySelect, EquipmentFields },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>

  <section v-if="store.section==='projects'" class="apf-project-intro" :aria-label="$t('apfUi.project_asset_description')">
    <h2>{{ $t('apfUi.project') }}<LibraryInfo :label="$t('apfUi.project')" :text="$t('apfUi.projects_collect_single_images_and_image_groups_across_nights_and_filt')" /></h2>
    <p v-if="viewingProjectAssets||viewingProjectDatasets">{{viewingProjectAssets?$t('apfUi.single_image'):$t('apfUi.image_group')}} · {{addingProjectAssets||addingProjectDatasets?$t('apfUi.select_fixed_versions_from_the_library'):$t('apfUi.selected_fixed_versions')}}</p>
  </section>
  <WorkspaceRecords />
    <component :is="editorType==='equipment'?'LibraryDialog':'section'" v-if="editorType" :open="Boolean(editorType)" :title="editingId?$t('apfUi.edit_equipment'):$t('apfUi.new_equipment')" :label="$t('apfUi.record_editor')" :busy="saving||savingInline>0" @close="closeEditor">
      <form class="apf-editor" :aria-label="$t('apfUi.record_editor')" @submit.prevent="saveEditor">
        <div class="apf-equipment-dialog-body">
          <h2 v-if="editorType==='project'">{{editingId?$t('apfUi.edit_project'):$t('apfUi.create_project')}}</h2>
          <EquipmentFields v-if="editorType==='equipment'" :model-value="draft as EquipmentDraft" kind-editable :kind-disabled="Boolean(editingId)" :name-label="$t('apfUi.name')" @update:model-value="draft=$event" />
          <template v-else-if="editingId">
            <label class="apf-field-row">{{ $t('apfUi.name') }}<InlineField :value="draft.name" :save="value=>saveEditorInline('name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('name'))" /></label>
            <label v-if="editorType==='project'" class="apf-field-row">{{ $t('apfUi.target') }}<InlineField :value="draft.target_name" :display="draft.target_name||$t('apfUi.not_specified')" :save="value=>saveEditorInline('target_name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('target_name'))" /></label>
            <label class="apf-field-row">{{ $t('apfUi.description_4262c4') }}<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>
          </template>
          <template v-else>
              <LibraryTextField id="project-name" v-model="draft.name" :name="$t('apfUi.name')" required />
              <label>{{ $t('apfUi.target') }}<input v-model="draft.target_name" /></label>
              <label>{{ $t('apfUi.description_4262c4') }}<textarea v-model="draft.notes" /></label>
          </template>
          <p v-if="error" role="alert">{{errorText(error)}}</p>
          <p v-if="inlineSaveFailure" role="alert">{{inlineSaveFailure}}</p>
        </div>
        <footer class="apf-equipment-dialog-footer apf-form-actions">
          <LibraryButton type="button" :disabled="saving||savingInline>0" @click="closeEditor">{{editingId&&editorType!=='equipment'?$t('apfUi.close'):$t('apfUi.cancel')}}</LibraryButton>
          <LibraryButton v-if="!editingId||editorType==='equipment'" type="submit" variant="primary" :disabled="saving">{{saving?$t('apfUi.saving'):$t('apfUi.save')}}</LibraryButton>
        </footer>
      </form>
    </component>
        <aside v-if="selected&&activeArea!=='library'&&!isEquipmentManagement" class="apf-details" :aria-label="$t('apfUi.record_details')">
          <template v-if="selected">
            <h2>{{ itemTitle(selected) }}</h2>
            <AssetContentChange v-if="selected.scope==='shared'||selected.asset?.scope==='shared'" :asset-id="rowAsset(selected).id" :has-version="!!rowAsset(selected).current_version_id" @accepted="loadRecords" />
            <p>{{ itemSubtitle(selected) }}</p>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectAssets">{{ $t('apfUi.view_project_assets') }}</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectDatasets">{{ $t('apfUi.view_project_image_groups') }}</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openAvailableAssets">{{ $t('apfUi.add_single_image') }}</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openAvailableDatasets">{{ $t('apfUi.add_image_group') }}</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="editProject(selected)">{{ $t('apfUi.edit_project') }}</button>
            <button v-if="store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets && selected.status!=='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="requestManagementArchive(selected)">{{ $t('apfUi.move_to_trash') }}</button>
            <button v-if="store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets && selected.status==='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="updateManagementStatus(selected,'active')">{{ $t('apfUi.restore') }}</button>
            <button v-if="store.section==='equipment'" type="button" @click="editEquipment(selected)">{{ $t('apfUi.edit_equipment') }}</button>
            <LibraryButton v-if="store.section==='equipment'" type="button" :disabled="dirty||savingInline>0" @click="requestEquipmentDelete(selected)">{{ $t('apfUi.delete_equipment') }}</LibraryButton>
            <button v-if="store.section === 'projects' && viewingProjectAssets && !addingProjectAssets" type="button" @click="removeSelectedAssetReference">{{ $t('apfUi.remove_from_project') }}</button>
            <button v-if="store.section === 'projects' && viewingProjectDatasets && !addingProjectDatasets" type="button" @click="removeSelectedDatasetReference">{{ $t('apfUi.remove_image_group_from_project') }}</button>
            <button v-if="store.section === 'projects' && addingProjectAssets" type="button" @click="addSelectedAsset">{{ $t('apfUi.use_this_asset_version') }}</button>
            <button v-if="store.section === 'projects' && addingProjectDatasets" type="button" @click="addSelectedDataset">{{ $t('apfUi.use_this_image_group_version') }}</button>
            <p v-if="store.section==='projects'&&(viewingProjectAssets||viewingProjectDatasets)">{{addingProjectAssets||addingProjectDatasets?$t('apfUi.version_to_use'):$t('apfUi.fixed_version')}} v{{selected.version?.version_number??selected.current_version?.version_number??'—'}}<LibraryInfo :label="$t('apfUi.fixed_version')" :text="selected.asset_version_id??selected.dataset_version_id??selected.current_version_id??''" /></p>
            <div v-if="selected.asset || selected.scope==='shared'" class="apf-detail-fields">
              <label>{{ $t('apfUi.name') }}<InlineField :value="itemTitle(selected)" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>{{ $t('apfUi.asset_form') }}<InlineField :value="rowClassification(selected).frame_class??''" :display="frameClassLabel(rowClassification(selected).frame_class)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...frameClasses.map(value=>({value,label:frameClassLabel(value)}))]" :save="selectedFieldSave('frame_class')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_class'))" /></label>
              <label v-if="rowClassification(selected).frame_class!=='video'">{{ $t('apfUi.frame_use') }}<InlineField :value="rowClassification(selected).frame_type??''" :display="frameTypeLabel(rowClassification(selected).frame_type)" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...frameTypes.map(value=>({value,label:frameTypeLabel(value)}))]" :save="selectedFieldSave('frame_type')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_type'))" /></label>
              <label>ISO／Gain<ParameterModeField :value="parameterModeValue(selected)" :display="parameterModeDisplay(selected)" unset-mode="standard" :save="selectedParameterSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'parameter_mode'))" /></label>
              <label>{{ $t('apfUi.camera_dacf07') }}<InlineField :value="rowParameters(selected).camera_id??''" :display="materialEquipmentName(selected,'camera_id')" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="selectedFieldSave('camera_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'camera_id'))" /></label>
              <label>{{ $t('apfUi.imaging_system') }}<InlineField :value="rowParameters(selected).optical_system_id??''" :display="materialEquipmentName(selected,'optical_system_id')" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="selectedFieldSave('optical_system_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'optical_system_id'))" /></label>
              <label>{{ $t('apfUi.filter') }}<InlineField :value="rowParameters(selected).filter_id??''" :display="materialEquipmentName(selected,'filter_id')" kind="select" :choices="[{value:'',label:$t('apfUi.not_specified')},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="selectedFieldSave('filter_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'filter_id'))" /></label>
              <label>{{ $t('apfUi.exposure_per_frame_seconds') }}<InlineField :value="rowParameters(selected).exposure_seconds" kind="number" :save="selectedFieldSave('exposure_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'exposure_seconds'))" /></label>
              <label>{{ $t('apfUi.total_exposure_seconds') }}<InlineField :value="rowParameters(selected).integration_seconds" kind="number" :save="selectedFieldSave('integration_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'integration_seconds'))" /></label>
              <label>{{ $t('apfUi.temperature_c') }}<InlineField :value="rowParameters(selected).sensor_temperature_c" :display="rowParameters(selected).sensor_temperature_c==null?$t('apfUi.not_specified'):displayTemperature(rowParameters(selected).sensor_temperature_c)+' °C'" kind="number" :save="selectedFieldSave('sensor_temperature_c')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'sensor_temperature_c'))" /></label>
              <label>Bin<InlineField :value="binEditValue(rowParameters(selected))" :display="binValue(rowParameters(selected))??$t('apfUi.not_specified')" kind="select" :choices="binEditChoices(rowParameters(selected))" :save="selectedBinSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'binning'))" /></label>
              <label>{{ $t('apfUi.cfa_pattern') }}<InlineField :value="rowParameters(selected).cfa_pattern??''" :display="cfaLabel(rowParameters(selected).cfa_pattern)" kind="select" :choices="cfaChoices" :save="selectedFieldSave('cfa_pattern')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'cfa_pattern'))" /></label>
              <label>{{ $t('apfUi.status') }}<InlineField :value="rowAsset(selected).status??'active'" :display="displayLabel(rowAsset(selected).status)" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>{{ $t('apfUi.notes') }}<InlineField :value="rowAsset(selected).notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="selected.dataset" class="apf-detail-fields">
              <label>{{ $t('apfUi.image_group_name') }}<InlineField :value="selected.dataset.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>{{ $t('apfUi.status') }}<InlineField :value="selected.dataset.status" :display="displayLabel(rowAsset(selected).status)" kind="select" :choices="[{value:'active',label:$t('apfUi.active')},{value:'archived',label:$t('apfUi.archive')}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>{{ $t('apfUi.notes') }}<InlineField :value="selected.dataset.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="store.section==='projects'" class="apf-detail-fields">
              <label>{{ $t('apfUi.name') }}<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>{{ $t('apfUi.target') }}<InlineField :value="selected.target_name" :save="selectedFieldSave('target_name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'target_name'))" /></label>
              <label>{{ $t('apfUi.notes') }}<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>

            </div>
            <div v-else-if="store.section==='equipment'" class="apf-detail-fields">
              <label>{{ $t('apfUi.name') }}<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>{{ $t('apfUi.model') }}<InlineField :value="selected.model" :display="selected.model??$t('apfUi.not_specified')" :save="selectedFieldSave('model')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'model'))" /></label>
              <label>{{ $t('apfUi.serial_number') }}<InlineField :value="selected.serial_number" :display="selected.serial_number??$t('apfUi.not_specified')" :save="selectedFieldSave('serial_number')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'serial_number'))" /></label>
              <label v-for="field in specFields[selected.kind]" :key="field.key">{{field.label}}<InlineField :value="textInput(specValue(field,selected.specs))" :display="specDisplay(field,specValue(field,selected.specs))" :kind="specKind(field)" :choices="specChoices(field)" :integer="field.integer" :save="selectedFieldSave('specs.'+field.key)" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'specs.'+field.key))" /></label>
              <label>{{ $t('apfUi.notes') }}<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>

          </template>
        </aside>
</template>
