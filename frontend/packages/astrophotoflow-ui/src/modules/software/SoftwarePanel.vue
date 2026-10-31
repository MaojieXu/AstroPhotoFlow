<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { Component } from 'vue'

import type { SoftwareClient } from './api/client'
import type { SoftwareConfirmationResult, SoftwarePackage } from './api/contracts'
import SoftwarePackageRow from './SoftwarePackageRow.vue'

const props = defineProps<{
  client: SoftwareClient
  confirmSoftware: (operationId: string) => Promise<SoftwareConfirmationResult>
  confirmationAvailable: boolean
  translate: (key: string, values?: Record<string, unknown>) => string
  controls?: { button: Component; dialog: Component; select?: Component }
  packageId?: string
  operationId?: string
}>()

const packages = ref<SoftwarePackage[]>([])
const loading = ref(true)
const failure = ref('')
const visiblePackages = computed(() => props.packageId ? packages.value.filter(value => value.package_id === props.packageId) : packages.value)
let disposed = false

async function load() {
  loading.value = true
  failure.value = ''
  try {
    const values = await props.client.listPackages()
    if (!disposed) packages.value = values
  } catch (error) {
    if (!disposed) failure.value = error instanceof Error ? error.message : props.translate('apfSoftware.loadError')
  } finally {
    if (!disposed) loading.value = false
  }
}

onMounted(() => void load())
onBeforeUnmount(() => { disposed = true })
</script>

<template>
  <section class="flex flex-col gap-2" data-testid="software-panel">
    <p v-if="loading" role="status" class="p-3">{{ translate('apfSoftware.loading') }}</p>
    <div v-else-if="failure" role="alert" class="p-3">
      {{ failure }}
      <component :is="controls?.button ?? 'button'" type="button" size="sm" @click="load">{{ translate('apfSoftware.reload') }}</component>
    </div>
    <p v-else-if="!visiblePackages.length" class="p-3">{{ translate('apfSoftware.noPackages') }}</p>
    <SoftwarePackageRow v-for="entry in visiblePackages" v-else :key="entry.package_id"
      :client="client" :package-id="entry.package_id" :operation-id="operationId"
      :confirm-software="confirmSoftware" :confirmation-available="confirmationAvailable"
      :translate="translate" :controls="controls" />
  </section>
</template>
