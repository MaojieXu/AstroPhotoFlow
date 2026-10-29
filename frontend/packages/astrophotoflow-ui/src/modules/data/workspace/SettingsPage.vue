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

  <section v-if="store.section==='projects'" class="apf-project-intro" aria-label="项目素材说明">
    <h2>项目<LibraryInfo label="项目" text="项目按拍摄目标或处理任务收集跨夜、跨滤镜的单图和图像组。选用时固定版本，库中后续变化不会替换已选版本。" /></h2>
    <p v-if="viewingProjectAssets||viewingProjectDatasets">{{viewingProjectAssets?'单图':'图像组'}} · {{addingProjectAssets||addingProjectDatasets?'从素材库选择要固定的版本':'已选固定版本'}}</p>
  </section>
  <WorkspaceRecords />
    <component :is="editorType==='equipment'?'LibraryDialog':'section'" v-if="editorType" :open="Boolean(editorType)" :title="editingId?'编辑设备':'新建设备'" label="记录编辑表单" :busy="saving||savingInline>0" @close="closeEditor">
      <form class="apf-editor" aria-label="记录编辑表单" @submit.prevent="saveEditor">
        <div class="apf-equipment-dialog-body">
          <h2 v-if="editorType==='project'">{{editingId?'编辑项目':'创建项目'}}</h2>
          <EquipmentFields v-if="editorType==='equipment'" :model-value="draft as EquipmentDraft" kind-editable :kind-disabled="Boolean(editingId)" name-label="名称" @update:model-value="draft=$event" />
          <template v-else-if="editingId">
            <label class="apf-field-row">名称<InlineField :value="draft.name" :save="value=>saveEditorInline('name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('name'))" /></label>
            <label v-if="editorType==='project'" class="apf-field-row">拍摄目标<InlineField :value="draft.target_name" :display="draft.target_name||'未指定'" :save="value=>saveEditorInline('target_name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('target_name'))" /></label>
            <label class="apf-field-row">说明<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>
          </template>
          <template v-else>
              <LibraryTextField id="project-name" v-model="draft.name" name="名称" required />
              <label>拍摄目标<input v-model="draft.target_name" /></label>
              <label>说明<textarea v-model="draft.notes" /></label>
          </template>
          <p v-if="error" role="alert">{{errorText(error)}}</p>
          <p v-if="inlineSaveFailure" role="alert">{{inlineSaveFailure}}</p>
        </div>
        <footer class="apf-equipment-dialog-footer apf-form-actions">
          <LibraryButton type="button" :disabled="saving||savingInline>0" @click="closeEditor">{{editingId&&editorType!=='equipment'?'关闭':'取消'}}</LibraryButton>
          <LibraryButton v-if="!editingId||editorType==='equipment'" type="submit" variant="primary" :disabled="saving">{{saving?'保存中…':'保存'}}</LibraryButton>
        </footer>
      </form>
    </component>
        <aside v-if="selected&&activeArea!=='library'&&!isEquipmentManagement" class="apf-details" aria-label="记录详情">
          <template v-if="selected">
            <h2>{{ itemTitle(selected) }}</h2>
            <AssetContentChange v-if="selected.scope==='shared'||selected.asset?.scope==='shared'" :asset-id="rowAsset(selected).id" :has-version="!!rowAsset(selected).current_version_id" @accepted="loadRecords" />
            <p>{{ itemSubtitle(selected) }}</p>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectAssets">查看项目素材</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectDatasets">查看项目图像组</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openAvailableAssets">添加单图</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openAvailableDatasets">添加图像组</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="editProject(selected)">编辑项目</button>
            <button v-if="store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets && selected.status!=='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="requestManagementArchive(selected)">移入回收站</button>
            <button v-if="store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets && selected.status==='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="updateManagementStatus(selected,'active')">恢复</button>
            <button v-if="store.section==='equipment'" type="button" @click="editEquipment(selected)">编辑设备</button>
            <LibraryButton v-if="store.section==='equipment'" type="button" :disabled="dirty||savingInline>0" @click="requestEquipmentDelete(selected)">删除设备</LibraryButton>
            <button v-if="store.section === 'projects' && viewingProjectAssets && !addingProjectAssets" type="button" @click="removeSelectedAssetReference">从项目移除</button>
            <button v-if="store.section === 'projects' && viewingProjectDatasets && !addingProjectDatasets" type="button" @click="removeSelectedDatasetReference">从项目移除图像组</button>
            <button v-if="store.section === 'projects' && addingProjectAssets" type="button" @click="addSelectedAsset">选用此素材版本</button>
            <button v-if="store.section === 'projects' && addingProjectDatasets" type="button" @click="addSelectedDataset">选用此图像组版本</button>
            <p v-if="store.section==='projects'&&(viewingProjectAssets||viewingProjectDatasets)">{{addingProjectAssets||addingProjectDatasets?'将选用版本':'固定版本'}} v{{selected.version?.version_number??selected.current_version?.version_number??'—'}}<LibraryInfo label="固定版本" :text="selected.asset_version_id??selected.dataset_version_id??selected.current_version_id??''" /></p>
            <div v-if="selected.asset || selected.scope==='shared'" class="apf-detail-fields">
              <label>名称<InlineField :value="itemTitle(selected)" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>素材形态<InlineField :value="rowClassification(selected).frame_class??''" :display="frameClassLabel(rowClassification(selected).frame_class)" kind="select" :choices="[{value:'',label:'未指定'},...frameClasses.map(value=>({value,label:frameClassLabel(value)}))]" :save="selectedFieldSave('frame_class')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_class'))" /></label>
              <label v-if="rowClassification(selected).frame_class!=='video'">帧用途<InlineField :value="rowClassification(selected).frame_type??''" :display="frameTypeLabel(rowClassification(selected).frame_type)" kind="select" :choices="[{value:'',label:'未指定'},...frameTypes.map(value=>({value,label:frameTypeLabel(value)}))]" :save="selectedFieldSave('frame_type')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_type'))" /></label>
              <label>ISO／Gain<ParameterModeField :value="parameterModeValue(selected)" :display="parameterModeDisplay(selected)" unset-mode="standard" :save="selectedParameterSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'parameter_mode'))" /></label>
              <label>相机<InlineField :value="rowParameters(selected).camera_id??''" :display="materialEquipmentName(selected,'camera_id')" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="selectedFieldSave('camera_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'camera_id'))" /></label>
              <label>成像系统<InlineField :value="rowParameters(selected).optical_system_id??''" :display="materialEquipmentName(selected,'optical_system_id')" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="selectedFieldSave('optical_system_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'optical_system_id'))" /></label>
              <label>滤镜<InlineField :value="rowParameters(selected).filter_id??''" :display="materialEquipmentName(selected,'filter_id')" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="selectedFieldSave('filter_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'filter_id'))" /></label>
              <label>单帧曝光（秒）<InlineField :value="rowParameters(selected).exposure_seconds" kind="number" :save="selectedFieldSave('exposure_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'exposure_seconds'))" /></label>
              <label>累计曝光（秒）<InlineField :value="rowParameters(selected).integration_seconds" kind="number" :save="selectedFieldSave('integration_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'integration_seconds'))" /></label>
              <label>温度（°C）<InlineField :value="rowParameters(selected).sensor_temperature_c" :display="rowParameters(selected).sensor_temperature_c==null?'未指定':displayTemperature(rowParameters(selected).sensor_temperature_c)+' °C'" kind="number" :save="selectedFieldSave('sensor_temperature_c')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'sensor_temperature_c'))" /></label>
              <label>Bin<InlineField :value="binEditValue(rowParameters(selected))" :display="binValue(rowParameters(selected))??'未指定'" kind="select" :choices="binEditChoices(rowParameters(selected))" :save="selectedBinSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'binning'))" /></label>
              <label>CFA 排列<InlineField :value="rowParameters(selected).cfa_pattern??''" :display="cfaLabel(rowParameters(selected).cfa_pattern)" kind="select" :choices="cfaChoices" :save="selectedFieldSave('cfa_pattern')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'cfa_pattern'))" /></label>
              <label>状态<InlineField :value="rowAsset(selected).status??'active'" :display="displayLabel(rowAsset(selected).status)" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>备注<InlineField :value="rowAsset(selected).notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="selected.dataset" class="apf-detail-fields">
              <label>图像组名称<InlineField :value="selected.dataset.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>状态<InlineField :value="selected.dataset.status" :display="displayLabel(rowAsset(selected).status)" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>备注<InlineField :value="selected.dataset.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="store.section==='projects'" class="apf-detail-fields">
              <label>名称<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>拍摄目标<InlineField :value="selected.target_name" :save="selectedFieldSave('target_name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'target_name'))" /></label>
              <label>备注<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>

            </div>
            <div v-else-if="store.section==='equipment'" class="apf-detail-fields">
              <label>名称<InlineField :value="selected.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>型号<InlineField :value="selected.model" :display="selected.model??'未指定'" :save="selectedFieldSave('model')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'model'))" /></label>
              <label>序列号<InlineField :value="selected.serial_number" :display="selected.serial_number??'未指定'" :save="selectedFieldSave('serial_number')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'serial_number'))" /></label>
              <label v-for="field in specFields[selected.kind]" :key="field.key">{{field.label}}<InlineField :value="textInput(specValue(field,selected.specs))" :display="specDisplay(field,specValue(field,selected.specs))" :kind="specKind(field)" :choices="specChoices(field)" :integer="field.integer" :save="selectedFieldSave('specs.'+field.key)" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'specs.'+field.key))" /></label>
              <label>备注<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>

          </template>
        </aside>
</template>
