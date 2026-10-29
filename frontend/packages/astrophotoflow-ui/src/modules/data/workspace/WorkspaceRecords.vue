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
          <p v-if="capabilityError" class="apf-error" role="alert">能力状态读取失败：{{ errorText(capabilityError) }}</p>
          <p v-if="inlineSaveFailure" class="apf-error" role="alert">{{inlineSaveFailure}}</p>
          <p v-if="bulkSelectMode" class="apf-state">只删除素材库引用，不删除原本数据。</p>
          <p v-if="managementSelectMode&&!isEquipmentManagement" class="apf-state">选择要移入回收站的项目；回收站中可恢复。</p>
          <p v-if="bulkDeleteNotice" class="apf-state" role="status">{{bulkDeleteNotice}}</p>
          <p v-if="error" class="apf-error" role="alert">{{ errorText(error) }}<span v-if="error.requestId"> 请求 ID：{{ error.requestId }}</span></p>
          <p v-if="loading" class="apf-state" role="status">正在读取服务数据…</p>
          <section v-if="!loading && !error && rows.length === 0" class="apf-state" role="status">
            <template v-if="activeDataset">此图像组当前没有成员。</template>
            <template v-else-if="isEquipmentManagement&&(store.query||equipmentKindFilter)">没有匹配的记录，请调整搜索或设备类别。</template>
            <template v-else-if="isEquipmentManagement">{{store.section==='equipment-setups'?'暂无设备组合':'暂无设备'}}</template>
            <template v-else-if="store.query || activeFilterCount">没有匹配的记录。请调整搜索或筛选。</template>
            <template v-else-if="activeArea==='library' && libraryCategory!=='all'">当前分类没有素材。可在“全部素材”查看其他素材，或导入相应用途的文件。</template>
            <template v-else-if="activeArea==='library'">素材库还是空的。点击“导入”选择文件或文件夹开始。</template>
            <template v-else>此处目前没有记录，可使用上方创建操作。</template>
          </section>

          <EquipmentSetupTable v-if="activeArea==='settings'&&store.section==='equipment-setups'" />
          <div v-else-if="!loading && (rows.length || activeArea === 'library') && isAssetTable" class="apf-table-scroll" :class="activeArea==='library'?libraryViewMode:'detail'">
            <table :class="['apf-assets-table',{'is-selecting':bulkSelectMode,'is-deleting':bulkDeleteBusy}]">
              <thead><tr>
                <th v-if="bulkSelectMode&&isLibraryItemsView"><LibraryCheckbox label="全选当前页" :model-value="pageAllSelected" :indeterminate="pagePartiallySelected" :disabled="rows.length===0||bulkDeleteBusy" @update:model-value="togglePageSelection" /></th>
                <th class="apf-column-preview">预览</th>
                <th :aria-sort="isLibraryTableView?sortAria('name'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('name')">名称{{sortArrow('name')}}</LibraryButton><template v-else>名称</template></th>
                <th class="apf-column-classification" :aria-sort="isLibraryTableView?sortAria('classification'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('classification')">分类{{sortArrow('classification')}}</LibraryButton><template v-else>分类</template></th>
                <th class="apf-column-camera" :aria-sort="isLibraryTableView?sortAria('camera'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('camera')">相机{{sortArrow('camera')}}</LibraryButton><template v-else>相机</template></th>
                <th class="apf-column-parameter" :aria-sort="isLibraryTableView?sortAria('parameter_mode'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('parameter_mode')">ISO／Gain{{sortArrow('parameter_mode')}}</LibraryButton><template v-else>ISO／Gain</template></th>
                <th class="apf-column-exposure" :aria-sort="isLibraryTableView?sortAria('exposure_seconds'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('exposure_seconds')">曝光{{sortArrow('exposure_seconds')}}</LibraryButton><template v-else>曝光</template></th>
                <th class="apf-column-temperature" :aria-sort="isLibraryTableView?sortAria('sensor_temperature_c'):undefined"><LibraryButton v-if="isLibraryTableView" variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('sensor_temperature_c')">温度{{sortArrow('sensor_temperature_c')}}</LibraryButton><template v-else>温度</template></th>
                <template v-if="libraryViewMode==='detail'&&isLibraryTableView">
                  <th :aria-sort="sortAria('binning')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('binning')">Bin{{sortArrow('binning')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('cfa_pattern')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('cfa_pattern')">CFA{{sortArrow('cfa_pattern')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('optical_system')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('optical_system')">成像系统{{sortArrow('optical_system')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('filter')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('filter')">滤镜{{sortArrow('filter')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('integration_seconds')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('integration_seconds')">累计曝光{{sortArrow('integration_seconds')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('storage_mode')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('storage_mode')">存储{{sortArrow('storage_mode')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('status')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('status')">状态{{sortArrow('status')}}</LibraryButton></th>
                  <th :aria-sort="sortAria('notes')"><LibraryButton variant="textonly" class="apf-sort-button" @click="toggleLibrarySort('notes')">备注{{sortArrow('notes')}}</LibraryButton></th>
                </template>
                <template v-else-if="activeArea!=='library'"><th>成像系统</th><th>滤镜</th><th>存储</th><th>状态</th><th>备注</th></template><th v-if="isLibraryTableView&&!bulkSelectMode" class="apf-column-action" aria-label="画布操作" /></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.entry_type+':'+row.id" :aria-selected="bulkSelectMode?bulkSelection.has(bulkKey(row)):selected?.id===row.id" @click="onLibraryRowClick(row,$event)" @dblclick.capture="bulkSelectMode?$event.stopPropagation():undefined">
                <td v-if="bulkSelectMode&&isLibraryItemsView"><span @click.stop><LibraryCheckbox :label="'选择 '+itemTitle(row)" :model-value="bulkSelection.has(bulkKey(row))" :disabled="bulkDeleteBusy" @update:model-value="toggleBulkSelection(row)" /></span></td>
                <td><LibraryCanvasSource :source="canvasSource(row)"><button type="button" class="apf-thumb" :aria-label="'查看 ' + itemTitle(row) + ' 大图'" @click.stop="openPhotoPreview(row)">
                  <img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" :draggable="false" />
                  <span v-else>暂无预览</span>
                </button></LibraryCanvasSource></td>
                <td><InlineField :value="itemTitle(row)" :save="value=>saveRowField(row,'name',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'name'))" /><template v-if="row.entry_type==='dataset'"><button type="button" class="apf-member-open" @click.stop="openDataset(row)">图像组 · {{row.version?.members?.length??row.member_count??0}} 张</button><small v-if="datasetRawValue(row,member=>member.asset?.classification?.frame_type)==='mixed'">混合用途组；打开后显示全部成员</small></template><small v-else>{{itemSubtitle(row)}}</small><small v-if="row.import_issue" class="apf-processing-issue" role="status">{{row.import_issue.includes('解析')?'解析失败':'资料处理异常'}} · {{displayLabel(row.version?.availability??row.current_version?.availability)}}<LibraryInfo :label="itemTitle(row)+'处理状态'" :text="row.import_issue.replace('原始文件仍将继续内容入库','请以当前原件状态为准')" /></small><small v-if="isLibraryTableView" class="apf-content-state" role="status">{{materialReadiness(row)}}</small><small class="apf-compact-meta">{{parameterModeDisplay(row)}}</small></td>
                <td v-if="row.entry_type==='dataset'">
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_class)" :display="datasetValue(row,member=>member.asset?.classification?.frame_class,frameClassLabel)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameClasses.map(value=>({value,label:frameClassLabel(value)}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_type)" :display="datasetValue(row,member=>member.asset?.classification?.frame_type,frameTypeLabel)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameTypes.map(value=>({value,label:frameTypeLabel(value)}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td v-else>
                  <InlineField :value="rowClassification(row).frame_class??''" :display="frameClassLabel(rowClassification(row).frame_class)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameClasses.map(value=>({value,label:frameClassLabel(value)}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField v-if="rowClassification(row).frame_class!=='video'" :value="rowClassification(row).frame_type??''" :display="frameTypeLabel(rowClassification(row).frame_type)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameTypes.map(value=>({value,label:frameTypeLabel(value)}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td class="apf-column-camera"><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.camera_id):rowParameters(row).camera_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'camera_id',Boolean(row.project_id))):materialEquipmentName(row,'camera_id')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.camera_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="value=>saveRowField(row,'camera_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'camera_id'))" /></td>
                <td class="apf-column-parameter">
                  <LibraryInfo label="参数来源" :text="'参数模式不会根据文件数值自动推断。\n'+['iso','gain','offset'].filter(key=>rowAsset(row).value_sources?.[key]).map(key=>key+'：'+displayLabel(rowAsset(row).value_sources[key])).join('\n')" /><ParameterModeField :value="parameterModeValue(row)" :display="parameterModeDisplay(row)" unset-mode="standard" :save="changes=>saveParameterGroup(row,changes)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'parameter_mode'))" />
                </td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds):rowParameters(row).exposure_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.exposure_seconds,value=>value==null?'未指定':String(value)+' s'):captureValue(rowParameters(row).exposure_seconds)+(rowParameters(row).exposure_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'exposure_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'exposure_seconds'))" /></td>
                <td class="apf-column-temperature"><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c):rowParameters(row).sensor_temperature_c" :display="row.entry_type==='dataset'?datasetTemperature(row):rowParameters(row).sensor_temperature_c==null?'未指定':displayTemperature(rowParameters(row).sensor_temperature_c)+' °C'" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'sensor_temperature_c',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'sensor_temperature_c'))" /></td>
                <template v-if="libraryViewMode==='detail'&&isLibraryTableView">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>binEditValue(member.asset?.parameters??{})):binEditValue(rowParameters(row))" :display="row.entry_type==='dataset'?datasetValue(row,member=>binValue(member.asset?.parameters??{}),value=>String(value??'未指定')):binValue(rowParameters(row))??'未指定'" kind="select" :choices="row.entry_type==='dataset'?datasetBinChoices(row):binEditChoices(rowParameters(row))" :save="value=>saveBin(row,value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'binning'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.cfa_pattern):rowParameters(row).cfa_pattern??''" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.cfa_pattern,cfaLabel):cfaLabel(rowParameters(row).cfa_pattern)" kind="select" :choices="row.entry_type==='dataset'?[...cfaChoices,{value:'mixed',label:'混合',disabled:true}]:cfaChoices" :save="value=>saveRowField(row,'cfa_pattern',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'cfa_pattern'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'optical_system_id',Boolean(row.project_id))):materialEquipmentName(row,'optical_system_id')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'filter_id',Boolean(row.project_id))):materialEquipmentName(row,'filter_id')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.filter_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds):rowParameters(row).integration_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.integration_seconds,value=>value==null?'未指定':String(value)+' s'):captureValue(rowParameters(row).integration_seconds)+(rowParameters(row).integration_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'integration_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'integration_seconds'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode,displayLabel):displayLabel(row.version?.storage_mode??row.current_version?.storage_mode)}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" :display="displayLabel(rowAsset(row).status??'active')" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue ? '资料处理异常' : displayLabel(row.version?.availability??row.current_version?.availability)}}</small></td>
                  <td class="apf-note-cell"><InlineField :value="row.entry_type==='dataset'?row.dataset?.notes:rowAsset(row).notes" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
                <template v-else-if="activeArea!=='library'">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'optical_system_id',Boolean(row.project_id))):materialEquipmentName(row,'optical_system_id')" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>materialEquipmentValue(member,'filter_id',Boolean(row.project_id))):materialEquipmentName(row,'filter_id')" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode,displayLabel):displayLabel(row.version?.storage_mode??row.current_version?.storage_mode)}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" :display="displayLabel(rowAsset(row).status??'active')" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue ? '资料处理异常' : displayLabel(row.version?.availability??row.current_version?.availability)}}</small></td>
                  <td><InlineField :value="rowAsset(row).notes" :display="rowAsset(row).notes??'—'" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
                <td v-if="isLibraryTableView&&!bulkSelectMode" class="apf-canvas-action-cell"><LibraryButton class="apf-canvas-action" variant="textonly" :aria-label="'将 '+itemTitle(row)+' 加入画布'" :disabled="!canvasSource(row)" :tooltip="canvasSource(row)?'加入画布；也可拖动预览':'原件就绪后可加入画布'" @click.stop="addRowToCanvas(row)"><i class="icon-[lucide--plus] size-4" aria-hidden="true" /></LibraryButton></td>
              </tr></tbody>
            </table>
          </div>
          <div v-else-if="!loading && rows.length && isDatasetTable" class="apf-table-scroll">
            <table class="apf-assets-table apf-dataset-table">
              <thead><tr><th>封面</th><th>图像组</th><th>分类</th><th>成员数</th><th>相机</th><th>ISO／Gain</th><th>曝光</th><th>温度</th><th>成像系统</th><th>滤镜</th><th>存储</th><th>状态</th><th>备注</th><th>固定版本照片</th></tr></thead>
              <tbody><tr v-for="row in rows" :key="row.id" :aria-selected="selected?.id===row.id" @click="selectRow(row)">
                <td><button type="button" class="apf-thumb" :aria-label="'查看 ' + itemTitle(row) + ' 大图'" @click.stop="openPhotoPreview(row)"><img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" /><span v-else>暂无预览</span></button></td>
                <td><strong>{{row.dataset?.name??row.name}}</strong><small>{{row.dataset_version_id?'项目固定版本':'图像组'}}</small></td>
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
            <label v-if="managementSelectMode" class="apf-management-select-page"><LibraryCheckbox label="全选当前页" :model-value="managementPageAllSelected" :indeterminate="managementPagePartiallySelected" :disabled="isEquipmentManagement&&managementFilterBlocked" @update:model-value="toggleManagementPage" />全选当前页</label>
            <template v-for="row in rows" :key="row.id">
              <div v-if="isEquipmentManagement" class="apf-equipment-record" role="group" :aria-label="'设备 '+itemTitle(row)">
                <LibraryCheckbox v-if="managementSelectMode" :label="'选择 '+itemTitle(row)" :model-value="managementSelection.has(store.section+':'+row.id)" :disabled="managementFilterBlocked" @update:model-value="toggleManagementSelection(row)" />
                <button type="button" :class="['apf-record', selected?.id === row.id ? 'selected' : '']" :aria-label="'选择设备 '+itemTitle(row)" :aria-pressed="selected?.id===row.id" :disabled="managementSelectMode||managementFilterBlocked" @click="selectRow(row)">
                  <i :class="[equipmentKindIcons[row.kind],'size-4 shrink-0 text-muted-foreground']" aria-hidden="true" />
                  <span><strong>{{itemTitle(row)}}</strong><small>{{itemSubtitle(row)}}</small></span>
                </button>
                <span class="apf-equipment-edit-slot"><LibraryButton v-if="store.section==='equipment'&&selected?.id===row.id" type="button" :aria-label="'编辑设备 '+itemTitle(row)" :disabled="managementFilterBlocked||loading" @click="editEquipment(row)">编辑</LibraryButton></span>
              </div>
              <label v-else-if="managementSelectMode" class="apf-management-record-select" @click.stop>
                <input type="checkbox" :aria-label="'选择 '+itemTitle(row)" :checked="managementSelection.has(store.section+':'+row.id)" @change="toggleManagementSelection(row)" />
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
            <span>{{ total }} 条记录</span>
            <label v-if="!isEquipmentManagement&&activeArea!=='library'">每页显示
              <select aria-label="每页显示数量" :value="store.pageSize" :disabled="loading||bulkDeleteBusy||setupDirty" @change="store.setPageSize(($event.target as HTMLSelectElement).value==='all'?'all':Number(($event.target as HTMLSelectElement).value) as 10|20|50)">
                <option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="all">全部</option>
              </select>
            </label>
            <template v-if="recordPageSize!=='all'&&(activeArea!=='library'||total>recordPageSize)">
              <button type="button" :disabled="store.offset === 0 || loading || bulkDeleteBusy || setupDirty" @click="store.movePage(-recordPageSize)">上一页</button>
              <button type="button" :disabled="store.offset + rows.length >= total || loading || bulkDeleteBusy || setupDirty" @click="store.movePage(recordPageSize)">下一页</button>
            </template>
          </footer>
          <p v-if="isAssetSection && capabilities && !capabilities.asset_preview" class="apf-disabled">素材预览将在后续阶段接入。</p>
</template>
