<script setup lang="ts">
import { WorkbenchSettings, createWorkbenchClient } from '@astrophotoflow/ui'

import SidebarTabTemplate from '@/components/sidebar/tabs/SidebarTabTemplate.vue'

const client = createWorkbenchClient((path, init) => fetch(path, init))
</script>

<template>
  <SidebarTabTemplate
    :title="$t('apfWorkbench.title')"
    data-testid="workbench-sidebar"
  >
    <template #body>
      <WorkbenchSettings :client="client" :translate="$t" />
    </template>
  </SidebarTabTemplate>
</template>
