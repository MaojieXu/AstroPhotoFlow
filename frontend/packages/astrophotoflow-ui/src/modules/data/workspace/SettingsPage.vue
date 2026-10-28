<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import InlineField from './InlineField.vue'
import ParameterModeField from './ParameterModeField.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'
import EquipmentSetupManager from './EquipmentSetupManager.vue'
import AssetContentChange from './AssetContentChange.vue'

export default {
  components: { InlineField, ParameterModeField, WorkspaceRecords, EquipmentSetupManager, AssetContentChange },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>
  <EquipmentSetupManager v-if="store.section==='equipment-setups'" />
  <template v-else>

  <section v-if="store.section==='projects'" class="apf-details" aria-label="项目素材说明">
    <p>项目按拍摄目标或处理任务收集跨夜、跨滤镜的单图和数据集。选用时固定版本，库中后续变化不会替换已选版本。</p>
    <p v-if="viewingProjectAssets||viewingProjectDatasets">{{viewingProjectAssets?'单图':'数据集'}} · {{addingProjectAssets||addingProjectDatasets?'从素材库选择要固定的版本':'已选固定版本'}}</p>
  </section>
  <WorkspaceRecords />
          <section v-if="editorType" class="apf-editor" aria-label="记录编辑表单">
            <template v-if="editingId">
              <h2>编辑{{editorType==='project'?'项目':'设备'}}</h2>
              <button type="button" :disabled="saving||savingInline>0" @click="closeEditor">关闭</button>
              <label>名称<InlineField :value="draft.name" :save="value=>saveEditorInline('name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('name'))" /></label>
              <template v-if="editorType==='project'">
                <label>拍摄目标<InlineField :value="draft.target_name" :display="draft.target_name||'未指定'" :save="value=>saveEditorInline('target_name',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('target_name'))" /></label>
                <label>说明<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>

              </template>
              <template v-else-if="editorType==='equipment'">
                <label>设备类型<select :value="draft.kind" disabled><option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{equipmentKindLabels[kind]}}</option></select></label>
                <label>型号<InlineField :value="draft.model" :display="draft.model||'未指定'" :save="value=>saveEditorInline('model',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('model'))" /></label>
                <label>序列号<InlineField :value="draft.serial_number" :display="draft.serial_number||'未指定'" :save="value=>saveEditorInline('serial_number',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('serial_number'))" /></label>
                <label>说明<InlineField :value="draft.notes" kind="textarea" :save="value=>saveEditorInline('notes',value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('notes'))" /></label>
                <fieldset><legend>设备参数</legend>
                  <label v-for="field in specFields[draft.kind]" :key="field.key">{{field.label}}<InlineField :value="draft.specs[field.key]" :display="specDisplay(field,draft.specs[field.key])" :kind="specKind(field)" :choices="specChoices(field)" :integer="field.integer" :save="value=>saveEditorInline('specs.'+field.key,value)" @cancelled="clearInlineSaveFailure(editorInlineFailureKey('specs.'))" /></label>
                </fieldset>
              </template>

            </template>
            <form v-else @submit.prevent="saveEditor">
              <h2>{{ editingId ? '编辑' : '创建' }}{{ editorType === 'project' ? '项目' : editorType === 'equipment' ? '设备' : '拍摄配置' }}</h2>
              <label>名称<input v-model="draft.name" required /></label>
              <template v-if="editorType === 'project'">
                <label>拍摄目标<input v-model="draft.target_name" /></label>
                <label>说明<textarea v-model="draft.notes" /></label>

              </template>
              <template v-if="editorType === 'equipment'">
                <label>设备类型<select v-model="draft.kind" :disabled="!!editingId" @change="onEquipmentKindChange">
                  <option v-for="kind in equipmentKinds" :key="kind" :value="kind">{{ equipmentKindLabels[kind] }}</option>
                </select></label>
                <label>型号<input v-model="draft.model" /></label>
                <label>序列号<input v-model="draft.serial_number" /></label>
                <label>说明<input v-model="draft.notes" /></label>
                <fieldset><legend>设备参数</legend>
                  <label v-for="field in specFields[draft.kind]" :key="field.key">{{ field.label }}
                    <select v-if="field.key==='cfa_pattern'" v-model="draft.specs[field.key]">
                      <option v-for="choice in cfaChoices" :key="choice.value" :value="choice.value">{{choice.label}}</option>
                    </select>
                    <select v-else-if="field.options" v-model="draft.specs[field.key]">
                      <option value="">未填写</option><option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
                    </select>
                    <input v-else v-model="draft.specs[field.key]" :type="field.type ?? 'text'" :step="field.integer ? 1 : 'any'" />
                  </label>
                </fieldset>
              </template>

              <label v-if="editingId">状态<select v-model="draft.status"><option value="active">启用</option><option value="archived">归档</option></select></label>
              <div class="apf-form-actions">
                <button type="button" :disabled="saving" @click="closeEditor">取消</button>
                <button type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
              </div>
            </form>
          </section>
        <aside v-if="selected&&activeArea!=='library'" class="apf-details" aria-label="记录详情">
          <template v-if="selected">
            <h2>{{ itemTitle(selected) }}</h2>
            <AssetContentChange v-if="selected.scope==='shared'||selected.asset?.scope==='shared'" :asset-id="rowAsset(selected).id" :has-version="!!rowAsset(selected).current_version_id" @accepted="loadRecords" />
            <p>{{ itemSubtitle(selected) }}</p>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectAssets">查看项目资产</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openProjectDatasets">查看项目数据集</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openAvailableAssets">添加单图</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="openAvailableDatasets">添加数据集</button>
            <button v-if="store.section === 'projects' && !viewingProjectAssets && !viewingProjectDatasets" type="button" @click="editProject(selected)">编辑项目</button>
            <button v-if="store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets && selected.status!=='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="requestManagementArchive(selected)">移入回收站</button>
            <button v-if="store.section==='projects' && !viewingProjectAssets && !viewingProjectDatasets && selected.status==='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="updateManagementStatus(selected,'active')">恢复</button>
            <button v-if="store.section==='equipment'" type="button" @click="editEquipment(selected)">编辑设备</button>
            <button v-if="store.section==='equipment' && selected.status!=='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="requestManagementArchive(selected)">移入回收站</button>
            <button v-if="store.section==='equipment' && selected.status==='archived'" type="button" :disabled="managementArchiveBusy||dirty||savingInline>0" @click="updateManagementStatus(selected,'active')">恢复</button>
            <button v-if="store.section === 'projects' && viewingProjectAssets && !addingProjectAssets" type="button" @click="removeSelectedAssetReference">从项目移除</button>
            <button v-if="store.section === 'projects' && viewingProjectDatasets && !addingProjectDatasets" type="button" @click="removeSelectedDatasetReference">从项目移除数据集</button>
            <button v-if="store.section === 'projects' && addingProjectAssets" type="button" @click="addSelectedAsset">选用此资产版本</button>
            <button v-if="store.section === 'projects' && addingProjectDatasets" type="button" @click="addSelectedDataset">选用此数据集版本</button>
            <p v-if="store.section==='projects'&&(viewingProjectAssets||viewingProjectDatasets)">{{addingProjectAssets||addingProjectDatasets?'将选用版本':'固定版本'}} v{{selected.version?.version_number??selected.current_version?.version_number??'—'}} · {{selected.asset_version_id??selected.dataset_version_id??selected.current_version_id}}</p>
            <div v-if="selected.asset || selected.scope==='shared'" class="apf-detail-fields">
              <label>名称<InlineField :value="itemTitle(selected)" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>素材形态<InlineField :value="rowClassification(selected).frame_class??''" :display="frameClassLabel(rowClassification(selected).frame_class)" kind="select" :choices="[{value:'',label:'未指定'},...frameClasses.map(value=>({value,label:value}))]" :save="selectedFieldSave('frame_class')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_class'))" /></label>
              <label v-if="rowClassification(selected).frame_class!=='video'">帧用途<InlineField :value="rowClassification(selected).frame_type??''" :display="frameTypeLabel(rowClassification(selected).frame_type)" kind="select" :choices="[{value:'',label:'未指定'},...frameTypes.map(value=>({value,label:value}))]" :save="selectedFieldSave('frame_type')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'frame_type'))" /></label>
              <label>ISO／Gain<ParameterModeField :value="parameterModeValue(selected)" :display="parameterModeDisplay(selected)" unset-mode="standard" :save="selectedParameterSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'parameter_mode'))" /></label>
              <label>相机<InlineField :value="rowParameters(selected).camera_id??''" :display="materialEquipmentName(selected,'camera_id')" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="selectedFieldSave('camera_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'camera_id'))" /></label>
              <label>成像系统<InlineField :value="rowParameters(selected).optical_system_id??''" :display="materialEquipmentName(selected,'optical_system_id')" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="selectedFieldSave('optical_system_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'optical_system_id'))" /></label>
              <label>滤镜<InlineField :value="rowParameters(selected).filter_id??''" :display="materialEquipmentName(selected,'filter_id')" kind="select" :choices="[{value:'',label:'未指定'},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="selectedFieldSave('filter_id')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'filter_id'))" /></label>
              <label>单帧曝光（秒）<InlineField :value="rowParameters(selected).exposure_seconds" kind="number" :save="selectedFieldSave('exposure_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'exposure_seconds'))" /></label>
              <label>累计曝光（秒）<InlineField :value="rowParameters(selected).integration_seconds" kind="number" :save="selectedFieldSave('integration_seconds')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'integration_seconds'))" /></label>
              <label>温度（°C）<InlineField :value="rowParameters(selected).sensor_temperature_c" :display="rowParameters(selected).sensor_temperature_c==null?'未指定':displayTemperature(rowParameters(selected).sensor_temperature_c)+' °C'" kind="number" :save="selectedFieldSave('sensor_temperature_c')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'sensor_temperature_c'))" /></label>
              <label>Bin<InlineField :value="binEditValue(rowParameters(selected))" :display="binValue(rowParameters(selected))??'未指定'" kind="select" :choices="binEditChoices(rowParameters(selected))" :save="selectedBinSave()" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'binning'))" /></label>
              <label>CFA 排列<InlineField :value="rowParameters(selected).cfa_pattern??''" :display="cfaLabel(rowParameters(selected).cfa_pattern)" kind="select" :choices="cfaChoices" :save="selectedFieldSave('cfa_pattern')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'cfa_pattern'))" /></label>
              <label>状态<InlineField :value="rowAsset(selected).status??'active'" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
              <label>备注<InlineField :value="rowAsset(selected).notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>
            <div v-else-if="selected.dataset" class="apf-detail-fields">
              <label>数据集名称<InlineField :value="selected.dataset.name" :save="selectedFieldSave('name')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'name'))" /></label>
              <label>状态<InlineField :value="selected.dataset.status" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="selectedFieldSave('status')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'status'))" /></label>
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
              <label v-for="field in specFields[selected.kind]" :key="field.key">{{field.label}}<InlineField :value="selected.specs?.[field.key]" :display="specDisplay(field,selected.specs?.[field.key])" :kind="specKind(field)" :choices="specChoices(field)" :integer="field.integer" :save="selectedFieldSave('specs.'+field.key)" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'specs.'+field.key))" /></label>
              <label>备注<InlineField :value="selected.notes" kind="textarea" :save="selectedFieldSave('notes')" @cancelled="clearInlineSaveFailure(inlineFailureKey(selected,'notes'))" /></label>
            </div>

          </template>
        </aside>
  </template>
</template>
