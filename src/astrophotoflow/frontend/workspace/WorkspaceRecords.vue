<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import ImportTasks from './ImportTasks.vue'
import InlineField from './InlineField.vue'
import ParameterModeField from './ParameterModeField.vue'

export default {
  components: { ImportTasks, InlineField, ParameterModeField },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>
          <p v-if="capabilityError" class="apf-error" role="alert">能力状态读取失败：{{ errorText(capabilityError) }}</p>
          <p v-if="inlineSaveFailure" class="apf-error" role="alert">{{inlineSaveFailure}}</p>
          <p v-if="bulkSelectMode" class="apf-state">只删除素材库引用，不删除原本数据。</p>
          <p v-if="bulkDeleteNotice" class="apf-state" role="status">{{bulkDeleteNotice}}</p>
          <p v-if="error" class="apf-error" role="alert">{{ errorText(error) }}<span v-if="error.requestId"> 请求 ID：{{ error.requestId }}</span></p>
          <p v-if="loading" class="apf-state" role="status">正在读取服务数据…</p>
          <p v-if="!loading && !error && rows.length === 0" class="apf-state">{{activeDataset?'此图像组当前没有成员。':activeArea==='library'?'当前没有已完成的素材。':'此处目前没有记录。'}}</p>

          <div v-if="!loading && (rows.length || activeArea === 'library') && isAssetTable" class="apf-table-scroll" :class="activeArea==='library'?libraryViewMode:'detail'">
            <table :class="['apf-assets-table',{'is-selecting':bulkSelectMode,'is-deleting':bulkDeleteBusy}]">
              <thead><tr>
                <th v-if="bulkSelectMode&&isLibraryItemsView"><input type="checkbox" aria-label="全选当前页" :checked="pageAllSelected" :indeterminate="pagePartiallySelected" :aria-checked="pagePartiallySelected?'mixed':pageAllSelected" :disabled="rows.length===0||bulkDeleteBusy" @change="togglePageSelection" /></th>
                <th>预览</th>
                <th :aria-sort="isLibraryTableView?sortAria('name'):undefined"><button v-if="isLibraryTableView" type="button" class="apf-sort-button" @click="toggleLibrarySort('name')">名称{{sortArrow('name')}}</button><template v-else>名称</template></th>
                <th :aria-sort="isLibraryTableView?sortAria('classification'):undefined"><button v-if="isLibraryTableView" type="button" class="apf-sort-button" @click="toggleLibrarySort('classification')">分类{{sortArrow('classification')}}</button><template v-else>分类</template></th>
                <th :aria-sort="isLibraryTableView?sortAria('camera'):undefined"><button v-if="isLibraryTableView" type="button" class="apf-sort-button" @click="toggleLibrarySort('camera')">相机{{sortArrow('camera')}}</button><template v-else>相机</template></th>
                <th :aria-sort="isLibraryTableView?sortAria('parameter_mode'):undefined"><button v-if="isLibraryTableView" type="button" class="apf-sort-button" @click="toggleLibrarySort('parameter_mode')">ISO／Gain{{sortArrow('parameter_mode')}}</button><template v-else>ISO／Gain</template></th>
                <th :aria-sort="isLibraryTableView?sortAria('exposure_seconds'):undefined"><button v-if="isLibraryTableView" type="button" class="apf-sort-button" @click="toggleLibrarySort('exposure_seconds')">曝光{{sortArrow('exposure_seconds')}}</button><template v-else>曝光</template></th>
                <th :aria-sort="isLibraryTableView?sortAria('sensor_temperature_c'):undefined"><button v-if="isLibraryTableView" type="button" class="apf-sort-button" @click="toggleLibrarySort('sensor_temperature_c')">温度{{sortArrow('sensor_temperature_c')}}</button><template v-else>温度</template></th>
                <template v-if="libraryViewMode==='detail'&&isLibraryTableView">
                  <th :aria-sort="sortAria('binning')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('binning')">Bin{{sortArrow('binning')}}</button></th>
                  <th :aria-sort="sortAria('cfa_pattern')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('cfa_pattern')">CFA{{sortArrow('cfa_pattern')}}</button></th>
                  <th :aria-sort="sortAria('optical_system')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('optical_system')">成像系统{{sortArrow('optical_system')}}</button></th>
                  <th :aria-sort="sortAria('filter')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('filter')">滤镜{{sortArrow('filter')}}</button></th>
                  <th :aria-sort="sortAria('integration_seconds')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('integration_seconds')">累计曝光{{sortArrow('integration_seconds')}}</button></th>
                  <th :aria-sort="sortAria('storage_mode')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('storage_mode')">存储{{sortArrow('storage_mode')}}</button></th>
                  <th :aria-sort="sortAria('status')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('status')">状态{{sortArrow('status')}}</button></th>
                  <th :aria-sort="sortAria('notes')"><button type="button" class="apf-sort-button" @click="toggleLibrarySort('notes')">备注{{sortArrow('notes')}}</button></th>
                </template>
                <template v-else-if="activeArea!=='library'"><th>成像系统</th><th>滤镜</th><th>存储</th><th>状态</th><th>备注</th></template></tr></thead>
              <tbody>
                <ImportTasks v-if="activeArea === 'library' && !viewingProjectAssets && !viewingProjectDatasets"
                  :refresh-token="progressRefreshToken" :watch-task-ids="watchedTaskIds" :upload-progress="uploadProgress" @completed="importTaskCompleted" @registered="importRegistrationCompleted" v-slot="{tasks,resume,busyTaskId,error:taskError}">
                  <tr v-if="taskError"><td :colspan="(activeArea==='library'&&libraryViewMode==='detail'?15:activeArea==='library'?7:12)+(bulkSelectMode&&isLibraryItemsView?1:0)" class="apf-error" role="alert">{{taskError}}</td></tr>
                  <tr v-for="task in tasks" :key="'task-'+task.id" class="apf-import-row" :aria-disabled="true">
                    <td :colspan="(activeArea==='library'&&libraryViewMode==='detail'?15:activeArea==='library'?7:12)+(bulkSelectMode&&isLibraryItemsView?1:0)"><div class="apf-import-row__content">
                      <strong>{{task.dataset_name || (task.report as Record<string, any>).upload_files?.[0]?.name || '素材导入'}}</strong>
                      <span>{{uploadTaskLabel(task)}}</span>
                      <button v-if="task.status==='interrupted'" type="button" :disabled="busyTaskId===task.id" @click="resume(task)">{{busyTaskId===task.id?'恢复中…':'继续导入'}}</button>
                      <progress v-if="task.status!=='failed' && task.enumeration_completed" :value="uploadTaskProgress(task)" max="100" :aria-label="uploadTaskLabel(task)" />
                      <progress v-else-if="task.status!=='failed'" max="100" :aria-label="uploadTaskLabel(task)" />
                    </div></td>
                  </tr>
                </ImportTasks>
                <tr v-for="row in rows" :key="row.entry_type+':'+row.id" :aria-selected="bulkSelectMode?bulkSelection.has(bulkKey(row)):selected?.id===row.id" @click="onLibraryRowClick(row,$event)" @dblclick.capture="bulkSelectMode?$event.stopPropagation():undefined">
                <td v-if="bulkSelectMode&&isLibraryItemsView"><input type="checkbox" :aria-label="'选择 '+itemTitle(row)" :checked="bulkSelection.has(bulkKey(row))" :disabled="bulkDeleteBusy" @click.stop @change="toggleBulkSelection(row)" /></td>
                <td><div class="apf-thumb" @click.stop>
                  <img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" />
                  <span v-else>100px</span>
                </div></td>
                <td><InlineField :value="itemTitle(row)" :save="value=>saveRowField(row,'name',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'name'))" /><template v-if="row.entry_type==='dataset'"><button type="button" class="apf-member-open" @click.stop="editDataset(row)">管理成员</button><button type="button" class="apf-member-open" @click.stop="openDataset(row)">图像组 · {{row.version?.members?.length??row.member_count??0}} 张</button></template><small v-else>{{itemSubtitle(row)}}</small></td>
                <td v-if="row.entry_type==='dataset'">
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_class)" :display="datasetValue(row,member=>member.asset?.classification?.frame_class,frameClassLabel)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameClasses.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField :value="datasetRawValue(row,member=>member.asset?.classification?.frame_type)" :display="datasetValue(row,member=>member.asset?.classification?.frame_type,frameTypeLabel)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameTypes.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td v-else>
                  <InlineField :value="rowClassification(row).frame_class??''" :display="frameClassLabel(rowClassification(row).frame_class)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameClasses.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_class',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_class'))" /><span class="apf-classification-separator" aria-hidden="true">/</span>
                  <InlineField v-if="rowClassification(row).frame_class!=='video'" :value="rowClassification(row).frame_type??''" :display="frameTypeLabel(rowClassification(row).frame_type)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...frameTypes.map(value=>({value,label:value}))]" :save="value=>saveRowField(row,'frame_type',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'frame_type'))" />
                </td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.camera_id):rowParameters(row).camera_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.camera_id,value=>equipmentName(value as string|null)):equipmentName(rowParameters(row).camera_id)" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.camera_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('camera')]" :choices-message="equipmentChoiceMessage('camera')" :save="value=>saveRowField(row,'camera_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'camera_id'))" /></td>
                <td>
                  <ParameterModeField :value="parameterModeValue(row)" :display="parameterModeDisplay(row)" unset-mode="standard" :save="changes=>saveParameterGroup(row,changes)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'parameter_mode'))" />
                </td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds):rowParameters(row).exposure_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.exposure_seconds,value=>value==null?'未指定':String(value)+' s'):captureValue(rowParameters(row).exposure_seconds)+(rowParameters(row).exposure_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.exposure_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'exposure_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'exposure_seconds'))" /></td>
                <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c):rowParameters(row).sensor_temperature_c" :display="row.entry_type==='dataset'?datasetTemperature(row):rowParameters(row).sensor_temperature_c==null?'未指定':displayTemperature(rowParameters(row).sensor_temperature_c)+' °C'" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.sensor_temperature_c)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'sensor_temperature_c',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'sensor_temperature_c'))" /></td>
                <template v-if="libraryViewMode==='detail'&&isLibraryTableView">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>binEditValue(member.asset?.parameters??{})):binEditValue(rowParameters(row))" :display="row.entry_type==='dataset'?datasetValue(row,member=>binValue(member.asset?.parameters??{}),value=>String(value??'未指定')):binValue(rowParameters(row))??'未指定'" kind="select" :choices="row.entry_type==='dataset'?datasetBinChoices(row):binEditChoices(rowParameters(row))" :save="value=>saveBin(row,value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'binning'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.cfa_pattern):rowParameters(row).cfa_pattern??''" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.cfa_pattern,cfaLabel):cfaLabel(rowParameters(row).cfa_pattern)" kind="select" :choices="row.entry_type==='dataset'?[...cfaChoices,{value:'mixed',label:'混合',disabled:true}]:cfaChoices" :save="value=>saveRowField(row,'cfa_pattern',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'cfa_pattern'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.optical_system_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).optical_system_id)" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.filter_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).filter_id)" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.filter_id)==='mixed'?'':undefined" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds):rowParameters(row).integration_seconds" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.integration_seconds,value=>value==null?'未指定':String(value)+' s'):captureValue(rowParameters(row).integration_seconds)+(rowParameters(row).integration_seconds==null?'':' s')" :edit-value="row.entry_type==='dataset'&&datasetRawValue(row,member=>member.asset?.parameters?.integration_seconds)==='mixed'?'':undefined" kind="number" :save="value=>saveRowField(row,'integration_seconds',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'integration_seconds'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode):row.version?.storage_mode??row.current_version?.storage_mode??'—'}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue??row.version?.availability??row.current_version?.availability??''}}</small></td>
                  <td class="apf-note-cell"><InlineField :value="row.entry_type==='dataset'?row.dataset?.notes:rowAsset(row).notes" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
                <template v-else-if="activeArea!=='library'">
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.optical_system_id):rowParameters(row).optical_system_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.optical_system_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).optical_system_id)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('optical_system')]" :choices-message="equipmentChoiceMessage('optical_system')" :save="value=>saveRowField(row,'optical_system_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'optical_system_id'))" /></td>
                  <td><InlineField :value="row.entry_type==='dataset'?datasetRawValue(row,member=>member.asset?.parameters?.filter_id):rowParameters(row).filter_id" :display="row.entry_type==='dataset'?datasetValue(row,member=>member.asset?.parameters?.filter_id,value=>equipmentName(typeof value==='string'?value:null)):equipmentName(rowParameters(row).filter_id)" kind="select" :choices="[{value:'',label:'未指定'},{value:'mixed',label:'混合',disabled:true},...equipmentChoices('filter')]" :choices-message="equipmentChoiceMessage('filter')" :save="value=>saveRowField(row,'filter_id',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'filter_id'))" /></td>
                  <td>{{row.entry_type==='dataset'?datasetValue(row,member=>member.version?.storage_mode):row.version?.storage_mode??row.current_version?.storage_mode??'—'}}</td>
                  <td><InlineField :value="rowAsset(row).status??'active'" kind="select" :choices="[{value:'active',label:'启用'},{value:'archived',label:'归档'}]" :save="value=>saveRowField(row,'status',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'status'))" /><small>{{row.import_issue??row.version?.availability??row.current_version?.availability??''}}</small></td>
                  <td><InlineField :value="rowAsset(row).notes" :display="rowAsset(row).notes??'—'" kind="textarea" :save="value=>saveRowField(row,'notes',value)" @cancelled="clearInlineSaveFailure(inlineFailureKey(row,'notes'))" /></td>
                </template>
              </tr></tbody>
            </table>
          </div>
          <div v-else-if="!loading && rows.length && isDatasetTable" class="apf-table-scroll">
            <table class="apf-assets-table apf-dataset-table">
              <thead><tr><th>封面</th><th>数据集</th><th>分类</th><th>成员数</th><th>相机</th><th>ISO／Gain</th><th>曝光</th><th>温度</th><th>成像系统</th><th>滤镜</th><th>存储</th><th>状态</th><th>备注</th><th>操作</th></tr></thead>
              <tbody><tr v-for="row in rows" :key="row.id" :aria-selected="selected?.id===row.id" @click="selectRow(row)">
                <td><div class="apf-thumb" @click.stop><img v-if="previewUrls[row.id]" :src="previewUrls[row.id]" alt="" /><span v-else>100px</span></div></td>
                <td><strong>{{row.dataset?.name??row.name}}</strong><small>{{row.dataset_version_id?'项目固定版本':'数据集'}}</small></td>
                <td>{{datasetClassification(row)}}</td>
                <td>{{row.version?.members?.length??row.member_count??'—'}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.camera_id, value=>equipmentName(typeof value==='string'?value:null))}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.iso)}} / {{datasetValue(row, member=>member.asset?.parameters?.gain)}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.exposure_seconds, value=>captureValue(value)+' s')}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.sensor_temperature_c, value=>captureValue(value)+' °C')}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.optical_system_id, value=>equipmentName(typeof value==='string'?value:null))}}</td>
                <td>{{datasetValue(row, member=>member.asset?.parameters?.filter_id, value=>equipmentName(typeof value==='string'?value:null))}}</td>
                <td>{{datasetValue(row, member=>member.version?.storage_mode, value=>String(value))}}</td>
                <td>{{row.dataset?.status??row.status}}</td><td class="apf-note-cell">{{row.dataset?.notes??row.notes??'—'}}</td>
                <td><button type="button" @click.stop="editDataset(row)">{{row.dataset_version_id?'编辑当前数据集':'编辑成员'}}</button></td>
              </tr></tbody>
            </table>
          </div>
          <section v-else-if="!loading && rows.length && !isAssetTable && !isDatasetTable" :class="['apf-records', store.layout]">
            <button v-for="row in rows" :key="row.id" type="button"
              :class="['apf-record', selected?.id === row.id ? 'selected' : '']" @click="selectRow(row)">
              <span class="apf-record-icon">{{ row.asset ? '✦' : row.kind ? '◉' : row.camera_id ? '⚙' : '▣' }}</span>
              <span><strong>{{ itemTitle(row) }}</strong><small>{{ itemSubtitle(row) }}</small></span>
            </button>
          </section>
          <footer class="apf-pagination">
            <span>{{ total }} 条记录</span>
            <label>每页显示
              <select aria-label="每页显示数量" :value="store.pageSize" :disabled="loading||bulkDeleteBusy||setupDirty" @change="store.setPageSize(($event.target as HTMLSelectElement).value==='all'?'all':Number(($event.target as HTMLSelectElement).value) as 10|20|50)">
                <option value="10">10</option><option value="20">20</option><option value="50">50</option><option value="all">全部</option>
              </select>
            </label>
            <template v-if="store.pageSize!=='all'">
              <button type="button" :disabled="store.offset === 0 || loading || bulkDeleteBusy || setupDirty" @click="store.movePage(-store.pageSize)">上一页</button>
              <button type="button" :disabled="store.offset + rows.length >= total || loading || bulkDeleteBusy || setupDirty" @click="store.movePage(store.pageSize)">下一页</button>
            </template>
          </footer>
          <p v-if="isAssetSection && capabilities && !capabilities.asset_preview" class="apf-disabled">资产预览将在后续阶段接入。</p>
</template>
