<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import LibraryFilterPanel from './LibraryFilterPanel.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'
import CalibrationLibrary from './CalibrationLibrary.vue'
import CalibrationBindingsEditor from './CalibrationBindingsEditor.vue'
import AssetContentChange from './AssetContentChange.vue'

export default {
  components: { LibraryFilterPanel, WorkspaceRecords, CalibrationLibrary, CalibrationBindingsEditor, AssetContentChange },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>
          <LibraryFilterPanel v-if="filterPanelOpen && isLibraryItemsView" :filters="activeFilters" :anchor="filterButton" @apply="applyFilters" @cancel="filterPanelOpen=false" />
  <CalibrationLibrary v-if="libraryCategory==='calibration'&&!activeDataset" />
  <WorkspaceRecords v-else />
  <aside v-if="selected && selected.entry_type !== 'dataset'" class="apf-details" :aria-label="$t('apfUi.selected_asset_files')">
    <h2>{{ itemTitle(selected) }}</h2>
    <AssetContentChange :asset-id="rowAsset(selected).id" :has-version="!!rowAsset(selected).current_version_id" @accepted="loadRecords" />
  </aside>
  <CalibrationBindingsEditor v-if="activeDataset" :key="activeDataset.id" :dataset-id="activeDataset.id" @updated="calibrationUpdated" />
</template>
