<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRoute } from 'vue-router'

import Button from '@/components/ui/button/Button.vue'
import SingleSelect from '@/components/ui/single-select/SingleSelect.vue'
import LibraryFormDialog from './LibraryFormDialog.vue'

import SidebarTabTemplate from '@/components/sidebar/tabs/SidebarTabTemplate.vue'
import { api } from '@/scripts/api'
import { confirmSoftware } from '../software/confirmation'
import { SoftwarePanel, createSoftwareClient, useSoftwareWorkspace } from '@astrophotoflow/ui'

const route = useRoute()
const connectionEpoch = ref(0)
const bundleRevision = ref(0)
function bundleChanged() { bundleRevision.value++ }
function reconnected() { connectionEpoch.value++ }
onMounted(() => api.addEventListener('reconnected', reconnected))
onBeforeUnmount(() => api.removeEventListener('reconnected', reconnected))
onMounted(() => api.addEventListener('apf.bundles_changed', bundleChanged))
onBeforeUnmount(() => api.removeEventListener('apf.bundles_changed', bundleChanged))
const fetchApi = (path: string, init?: RequestInit) => fetch(path, init)
const client = createSoftwareClient(fetchApi)
const workspace = useSoftwareWorkspace(fetchApi, connectionEpoch)
const packageId = computed(() => typeof route.query.package_id === 'string' ? route.query.package_id : undefined)
const operationId = computed(() => connectionEpoch.value === 0 && typeof route.query.operation_id === 'string' ? route.query.operation_id : undefined)
const confirmationAvailable = computed(() => api.serverSupportsFeature('apf_page'))
</script>

<template>
  <SidebarTabTemplate :title="$t('apfSoftware.title')" data-testid="software-sidebar">
    <template #body>
      <p v-if="workspace.isFetching.value" role="status">{{ $t('apfSoftware.loading') }}</p>
      <div v-else-if="workspace.isError.value" role="alert">
        {{ workspace.error.value?.message }}
        <Button @click="workspace.refetch()">{{ $t('apfSoftware.reload') }}</Button>
      </div>
      <SoftwarePanel v-else-if="workspace.data.value"
        :workspace-id="workspace.data.value.workspace"
        :key="connectionEpoch"
        :refresh-key="bundleRevision"
        :client="client"
        :confirm-software="confirmSoftware"
        :confirmation-available="confirmationAvailable"
        :package-id="packageId"
        :operation-id="operationId"
        :translate="$t"
        :controls="{ button: Button, dialog: LibraryFormDialog, select: SingleSelect }"
      />
    </template>
  </SidebarTabTemplate>
</template>
