<script setup lang="ts">
import { computed, ref } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import { uiT } from '../../../core/i18n'
import { useQueryAvailability } from '../../../core/query/availability'
import { workspaceQueryKey } from '../../../core/query/keys'
import type { LibraryLocationOut, LibraryOrganizePlan, LibraryOrganizeReceipt } from '../../../generated/api/types.gen'
import { datasetApi, libraryApi } from '../api'
import LibraryButton from '../components/LibraryButton.vue'
import { displayLabel } from './presentation'

const props = defineProps<{ workspaceId: string; entryType: LibraryLocationOut['entry_type']; entryId: string; revision: number }>()
const expanded = ref(false)
const plan = ref<LibraryOrganizePlan>()
const receipt = ref<LibraryOrganizeReceipt>()
const requestId = ref<string>()
const cache = useQueryClient()
const available = useQueryAvailability()
const location = useQuery({
  queryKey: computed(() => [...workspaceQueryKey(props.workspaceId), 'library-location', props.entryType, props.entryId, props.revision]),
  enabled: computed(() => expanded.value && available.value),
  queryFn: ({ signal }) => libraryApi.location(props.entryType, props.entryId, signal)
})
const action = useMutation({
  retry: false,
  mutationFn: async (kind: 'open' | 'rebuild' | 'plan' | 'organize' | 'status' | {kind:'up'|'down'|'remove'; assetId:string}) => {
    if (typeof kind === 'object') {
      const current = location.data.value
      if (!current || props.entryType !== 'dataset') return
      const ids = current.files.map(file => file.asset_id)
      const index = ids.indexOf(kind.assetId)
      if (index < 0) return
      if (kind.kind === 'remove') ids.splice(index, 1)
      else {
        const next = index + (kind.kind === 'up' ? -1 : 1)
        if (next < 0 || next >= ids.length) return
        const moved = ids.splice(index, 1)[0]
        if (moved === undefined) return
        ids.splice(next, 0, moved)
      }
      try { await datasetApi.replaceMembers(props.entryId, {base_revision:current.revision, asset_ids:ids}) }
      finally { await cache.invalidateQueries({queryKey:workspaceQueryKey(props.workspaceId)}) }
      return
    }
    if (kind === 'open') {
      await libraryApi.openDirectory(props.entryType, props.entryId)
    } else if (kind === 'rebuild') {
      await libraryApi.rebuildManifest(props.entryId, props.revision)
    } else if (kind === 'plan') {
      receipt.value = undefined
      plan.value = await libraryApi.planOrganization({ entry_type: props.entryType, id: props.entryId, base_revision: props.revision })
    } else if (kind === 'status') {
      if (requestId.value) receipt.value = await libraryApi.organization(requestId.value)
    } else if (plan.value) {
      requestId.value = crypto.randomUUID()
      try {
        receipt.value = await libraryApi.organize({
          request_id: requestId.value, entry_type: props.entryType, id: props.entryId,
          base_revision: plan.value.base_revision, plan_token: plan.value.token
        })
      } catch (cause) {
        // Query an uncertain result using the same identity. Never replay it.
        try { receipt.value = await libraryApi.organization(requestId.value) }
        catch { throw cause }
      }
      plan.value = undefined
    }
    if (kind === 'organize' || kind === 'rebuild') {
      await cache.invalidateQueries({ queryKey: workspaceQueryKey(props.workspaceId) })
    }
  }
})
const failure = computed(() => {
  const cause = action.error.value ?? location.error.value
  return cause instanceof Error ? cause.message : cause ? uiT('apfUi.request_failed') : ''
})
function toggle(event: Event) {
  if (event.currentTarget instanceof HTMLDetailsElement) expanded.value = event.currentTarget.open
}
</script>

<template>
  <details class="mt-3 space-y-2 text-xs" @toggle="toggle">
    <summary class="cursor-pointer">{{ $t('apfUi.library_location') }}</summary>
    <p v-if="location.isPending.value" role="status">{{ $t('apfUi.library_location_loading') }}</p>
    <template v-if="location.data.value">
      <p class="break-all">{{ location.data.value.directory }}</p>
      <div class="flex flex-wrap gap-2">
        <LibraryButton :disabled="action.isPending.value || !location.data.value.directory" @click="action.mutate('open')">{{ $t('apfUi.open_directory') }}</LibraryButton>
        <LibraryButton v-if="entryType === 'dataset'" :disabled="action.isPending.value" @click="action.mutate('rebuild')">{{ $t('apfUi.rebuild_dataset_json') }}</LibraryButton>
        <LibraryButton :disabled="action.isPending.value" @click="action.mutate('plan')">{{ $t('apfUi.preflight_directory_organization') }}</LibraryButton>
      </div>
      <p v-if="location.data.value.manifest_path" class="break-all">{{ location.data.value.manifest_path }} · {{ location.data.value.manifest_status }}</p>
      <p v-if="location.data.value.manifest_error" role="alert">{{ location.data.value.manifest_error }}</p>
      <ul class="max-h-48 overflow-auto">
        <li v-for="(file, index) in location.data.value.files" :key="file.asset_id" class="break-all">
          {{ file.library_relative_path ?? file.path }} · {{ displayLabel(file.calibration_status) }} · {{ displayLabel(file.availability) }}
          <span v-if="entryType === 'dataset'" class="inline-flex gap-1">
            <LibraryButton :disabled="action.isPending.value || index === 0" @click="action.mutate({kind:'up',assetId:file.asset_id})">{{ $t('apfUi.member_move_up') }}</LibraryButton>
            <LibraryButton :disabled="action.isPending.value || index + 1 === location.data.value.files.length" @click="action.mutate({kind:'down',assetId:file.asset_id})">{{ $t('apfUi.member_move_down') }}</LibraryButton>
            <LibraryButton :disabled="action.isPending.value" @click="action.mutate({kind:'remove',assetId:file.asset_id})">{{ $t('apfUi.remove_dataset_member') }}</LibraryButton>
          </span>
          <details v-if="Object.keys(file.calibration_evidence ?? {}).length"><summary>{{ $t('apfUi.calibration_reason') }}</summary><pre class="whitespace-pre-wrap">{{ JSON.stringify(file.calibration_evidence, null, 2) }}</pre></details>
          <details v-if="file.processing_calibration || file.processing_provenance"><summary>{{ $t('apfUi.executed_calibration_facts') }}</summary><pre class="whitespace-pre-wrap">{{ JSON.stringify({calibration:file.processing_calibration, source:file.processing_provenance}, null, 2) }}</pre></details>
        </li>
      </ul>
    </template>
    <section v-if="plan" class="space-y-2">
      <p class="break-all">{{ plan.source_directory }} → {{ plan.destination_directory }}</p>
      <ul><li v-for="blocker in plan.blockers" :key="blocker" role="alert">{{ blocker }}</li></ul>
      <ul class="max-h-48 overflow-auto"><li v-for="move in plan.moves" :key="move.asset_id" class="break-all">{{ move.source }} → {{ move.destination }}</li></ul>
      <LibraryButton :disabled="action.isPending.value || plan.blockers.length > 0" @click="action.mutate('organize')">{{ $t('apfUi.organize_directories') }}</LibraryButton>
    </section>
    <section v-if="receipt" class="space-y-1" role="status">
      <p>{{ receipt.request_id }} · {{ receipt.state }}</p>
      <p v-if="receipt.error">{{ receipt.error }}</p>
      <ul class="max-h-48 overflow-auto"><li v-for="move in receipt.plan.moves" :key="move.asset_id" class="break-all">{{ move.asset_id }} · {{ move.state }} · {{ move.error }}</li></ul>
    </section>
    <LibraryButton v-if="requestId" :disabled="action.isPending.value" @click="action.mutate('status')">{{ $t('apfUi.query_organization_receipt') }}</LibraryButton>
    <p v-if="failure" role="alert">{{ failure }}</p>
  </details>
</template>
