<script setup lang="ts">
import { computed, provide, ref, shallowRef, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { ServiceCapabilities } from '../../../generated/api/types.gen'
import { queryAvailabilityKey } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import { libraryError, libraryErrorText } from '../library/errors'
import { useLibraryBootstrap } from '../library/queries'
import type { ImportNotice, LibraryControls } from './libraryControls'
import { useWorkspaceStore } from './store'
import WorkspacePage from './WorkspacePage.vue'

const props = withDefaults(
  defineProps<{
    native?: boolean
    sidebar?: boolean
    initialSection?: 'library' | 'projects'
    controls?: LibraryControls
    connectionEpoch?: number
    connected?: boolean
  }>(),
  { connected: true }
)
const emit = defineEmits<{
  'manage-equipment': []
  'back-to-library': []
  'notify-success': [message: string]
  'notify-import': [notice: ImportNotice]
  'workspace-changed': [workspaceId: string]
}>()
const cache = useQueryClient()
const store = useWorkspaceStore()
const bootstrap = useLibraryBootstrap(
  () => props.connectionEpoch ?? 0,
  () => props.connected !== false
)
const ready = computed(
  () =>
    props.connected !== false &&
    bootstrap.isSuccess.value &&
    bootstrap.isFetchedAfterMount.value
)
provide(queryAvailabilityKey, ready)
const failure = computed(() =>
  bootstrap.error.value
    ? libraryErrorText(libraryError(bootstrap.error.value))
    : ''
)
// Retain only the confirmed connection checkpoint while the next identity is read.
// Business records stay in Query; page instances own their unsaved drafts.
const confirmed = shallowRef<{
  workspaceId: string
  capabilities: ServiceCapabilities
}>()
const page = ref<InstanceType<typeof WorkspacePage>>()
watch(
  ready,
  (available) => {
    if (!available && confirmed.value)
      void cache.cancelQueries({
        queryKey: workspaceQueryKey(confirmed.value.workspaceId)
      })
  },
  { flush: 'sync' }
)
watch(
  [ready, bootstrap.data],
  ([available, data]) => {
    if (!available || !data) return
    const previous = confirmed.value?.workspaceId
    const workspaceId = data.health.workspace
    if (previous && previous !== workspaceId) {
      // Abort before removing: late reads cannot repopulate the previous identity.
      void cache.cancelQueries({ queryKey: workspaceQueryKey(previous) })
      cache.removeQueries({ queryKey: workspaceQueryKey(previous) })
      store.activeProjectId = null
      store.activeProjectRevision = null
      store.offset = 0
      emit('workspace-changed', workspaceId)
    }
    confirmed.value = { workspaceId, capabilities: data.capabilities }
  },
  { immediate: true, flush: 'sync' }
)

function selectArea(
  ...args: Parameters<InstanceType<typeof WorkspacePage>['selectArea']>
) {
  if (!ready.value || !page.value) return Promise.resolve(false)
  return page.value.selectArea(...args)
}
function leavePage() {
  return page.value?.leavePage() ?? Promise.resolve(true)
}
function showImportIssue(
  ...args: Parameters<InstanceType<typeof WorkspacePage>['showImportIssue']>
) {
  if (ready.value) page.value?.showImportIssue(...args)
}
const activeArea = computed(
  () =>
    page.value?.activeArea ??
    (props.initialSection === 'projects' ? 'settings' : 'library')
)
defineExpose({ selectArea, leavePage, showImportIssue, activeArea })
</script>

<template>
  <div
    class="apf-workspace-connection" :aria-busy="!ready"
    @pointerdown.stop @pointerup.stop @mousedown.stop @mouseup.stop
    @click.stop @contextmenu.stop @keydown.stop @keyup.stop>
    <p v-if="connected === false" role="status">
      {{ $t('apfUi.reconnecting_workbench') }}
    </p>
    <p v-else-if="!confirmed && bootstrap.isFetching.value" role="status">
      {{ $t('apfUi.reading_service_data') }}
    </p>
    <div v-else-if="bootstrap.isError.value" role="alert">
      {{ failure }}
      <button type="button" @click="bootstrap.refetch()">
        {{ $t('apfUi.retry') }}
      </button>
    </div>
    <WorkspacePage
      v-if="confirmed"
      v-show="ready"
      :key="confirmed.workspaceId"
      ref="page"
      :inert="!ready"
      :workspace-id="confirmed.workspaceId"
      :capabilities="confirmed.capabilities"
      :native="native"
      :sidebar="sidebar"
      :initial-section="initialSection"
      :controls="controls"
      @manage-equipment="ready && emit('manage-equipment')"
      @back-to-library="ready && emit('back-to-library')"
      @notify-success="(message) => ready && emit('notify-success', message)"
      @notify-import="(notice) => ready && emit('notify-import', notice)"
    />
  </div>
</template>

<style scoped>
.apf-workspace-connection {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
