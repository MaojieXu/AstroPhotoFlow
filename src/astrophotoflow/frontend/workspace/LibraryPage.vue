<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import LibraryFilterPanel from './LibraryFilterPanel.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'
import CalibrationLibrary from './CalibrationLibrary.vue'
import CalibrationBindingsEditor from './CalibrationBindingsEditor.vue'

export default {
  components: { LibraryFilterPanel, WorkspaceRecords, CalibrationLibrary, CalibrationBindingsEditor },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>
          <LibraryFilterPanel v-if="filterPanelOpen && isLibraryItemsView" :filters="activeFilters" :anchor="filterButton" @apply="applyFilters" @cancel="filterPanelOpen=false" />
          <input ref="filePicker" type="file" multiple accept=".fits,.fit,.fts,.fits.fz,.fit.fz,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp,.heic,.heif,.hif,.cr2,.cr3,.nef,.arw,.dng,.raf,.orf,.rw2,.pef,.srw,.xisf,.ser,.mp4,.mov,.avi,.mkv" hidden @change="filesChosen" />
          <input ref="folderPicker" type="file" webkitdirectory directory multiple hidden @change="foldersChosen" />
  <CalibrationLibrary v-if="libraryCategory==='calibration'&&!activeDataset" />
  <WorkspaceRecords v-else />
  <CalibrationBindingsEditor v-if="activeDataset" :key="activeDataset.id" :dataset-id="activeDataset.id" @updated="calibrationUpdated" />
</template>
