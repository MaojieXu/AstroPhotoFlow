<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import SidebarTabTemplate from '@/components/sidebar/tabs/SidebarTabTemplate.vue'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

import { Workspace } from '@astrophotoflow/ui'

const workspace = ref<InstanceType<typeof Workspace>>()
const tabs = useSidebarTabStore()
const tab = tabs.sidebarTabs.find((item) => item.id === 'library')!

onMounted(() => {
  tab.canClose = () => workspace.value!.leavePage()
})
onBeforeUnmount(() => {
  tab.canClose = undefined
})
</script>

<template>
  <SidebarTabTemplate
    :title="$t('astrophotoflow.library')"
    data-testid="library-sidebar"
  >
    <template #body>
      <Workspace
        ref="workspace"
        native
        sidebar
        @manage-equipment="workspace!.selectArea('settings', 'equipment')"
        @back-to-library="workspace!.selectArea('library')"
      />
    </template>
  </SidebarTabTemplate>
</template>
