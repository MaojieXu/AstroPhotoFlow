<script setup lang="ts">
import { computed, watch } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { softwareQueryKey, useSoftwareCatalog } from './queries'
import type { Component } from 'vue'

import type { SoftwareClient } from './api/client'
import type { SoftwareConfirmationResult } from './api/contracts'
import SoftwarePackageRow from './SoftwarePackageRow.vue'

const props = defineProps<{
  workspaceId: string
  client: SoftwareClient
  confirmSoftware: (operationId: string) => Promise<SoftwareConfirmationResult>
  confirmationAvailable: boolean
  translate: (key: string, values?: Record<string, unknown>) => string
  controls?: { button: Component; dialog: Component; select?: Component }
  packageId?: string
  operationId?: string
  refreshKey?: number
}>()

const cache = useQueryClient()
const query = useSoftwareCatalog(() => ({workspaceId:props.workspaceId,client:props.client}))
const packages = computed(() => query.data.value ?? [])
const loading = query.isPending
const failure = computed(() => query.error.value instanceof Error ? query.error.value.message : query.isError.value ? props.translate('apfSoftware.loadError') : '')
const visiblePackages = computed(() => props.packageId ? packages.value.filter(value => value.package_id === props.packageId) : packages.value)
function load() { return query.refetch() }
watch(() => props.refreshKey, () => {
  const key=softwareQueryKey(props.workspaceId)
  void cache.invalidateQueries({queryKey:[...key,'catalog']})
  void cache.invalidateQueries({queryKey:[...key,'details']})
})
</script>

<template>
  <section class="flex flex-col gap-2" data-testid="software-panel">
    <p v-if="loading" role="status" class="p-3">{{ translate('apfSoftware.loading') }}</p>
    <div v-else-if="failure" role="alert" class="p-3">
      {{ failure }}
      <component :is="controls?.button ?? 'button'" type="button" size="sm" @click="load">{{ translate('apfSoftware.reload') }}</component>
    </div>
    <p v-else-if="!visiblePackages.length" class="p-3">{{ translate('apfSoftware.noPackages') }}</p>
    <template v-else>
      <SoftwarePackageRow
        v-for="entry in visiblePackages" :key="entry.package_id"
        :client="client" :workspace-id="workspaceId" :package-id="entry.package_id" :operation-id="operationId"
        :confirm-software="confirmSoftware" :confirmation-available="confirmationAvailable"
        :translate="translate" :controls="controls" />
    </template>
  </section>
</template>
