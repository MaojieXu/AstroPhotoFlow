<script lang="ts">
import { inject } from 'vue'
import type { WorkspaceContext } from './Workspace.vue'
import LibraryFilterPanel from './LibraryFilterPanel.vue'
import WorkspaceRecords from './WorkspaceRecords.vue'

export default {
  components: { LibraryFilterPanel, WorkspaceRecords },
  setup() { return inject<WorkspaceContext>('workspace')! }
}
</script>

<template>
          <LibraryFilterPanel v-if="filterPanelOpen && isLibraryItemsView" :filters="activeFilters" :anchor="filterButton" @apply="applyFilters" @cancel="filterPanelOpen=false" />
          <input ref="filePicker" type="file" multiple accept=".fits,.fit,.fts,.fits.fz,.fit.fz,.jpg,.jpeg,.png,.tif,.tiff,.bmp,.webp,.heic,.heif,.hif,.cr2,.cr3,.nef,.arw,.dng,.raf,.orf,.rw2,.pef,.srw,.xisf,.ser,.mp4,.mov,.avi,.mkv" hidden @change="filesChosen" />
          <input ref="folderPicker" type="file" webkitdirectory directory multiple hidden @change="foldersChosen" />
  <WorkspaceRecords />
</template>