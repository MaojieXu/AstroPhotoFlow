<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import Button from '@/components/ui/button/Button.vue'
import LibraryFormDialog from './LibraryFormDialog.vue'

import SidebarTabTemplate from '@/components/sidebar/tabs/SidebarTabTemplate.vue'
import { api } from '@/scripts/api'
import { confirmSoftware } from './workflowBridge'
import { SoftwarePanel, createSoftwareClient } from '@astrophotoflow/ui'

const route = useRoute()
const client = createSoftwareClient((path, init) => fetch(path, init))
const packageId = computed(() => typeof route.query.package_id === 'string' ? route.query.package_id : undefined)
const operationId = computed(() => typeof route.query.operation_id === 'string' ? route.query.operation_id : undefined)
const confirmationAvailable = computed(() => api.serverSupportsFeature('apf_page'))
</script>

<template>
  <SidebarTabTemplate :title="$t('apfSoftware.title')" data-testid="software-sidebar">
    <template #body>
      <SoftwarePanel
        :client="client"
        :confirm-software="confirmSoftware"
        :confirmation-available="confirmationAvailable"
        :package-id="packageId"
        :operation-id="operationId"
        :translate="$t"
        :controls="{ button: Button, dialog: LibraryFormDialog }"
      />
    </template>
  </SidebarTabTemplate>
</template>
