<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { useToast } from '@/components/ui/toast/toastStore'

import SidebarTabTemplate from '@/components/sidebar/tabs/SidebarTabTemplate.vue'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'
import { useSettingsDialog } from '@/platform/settings/composables/useSettingsDialog'

import { Workspace } from '@astrophotoflow/ui'
import FormItem from '@/components/common/FormItem.vue'
import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'
import MultiSelect from '@/components/ui/multi-select/MultiSelect.vue'
import SearchableSingleSelect from '@/components/ui/single-select/SearchableSingleSelect.vue'
import Textarea from '@/components/ui/textarea/Textarea.vue'
import Checkbox from '@/components/ui/checkbox/Checkbox.vue'
import Menu from '@/components/ui/menu/Menu.vue'
import Tabs from '@/components/ui/tabs/Tabs.vue'
import TabsList from '@/components/ui/tabs/TabsList.vue'
import TabsTrigger from '@/components/ui/tabs/TabsTrigger.vue'
import LibraryFormDialog from './LibraryFormDialog.vue'
import LibraryCanvasSource from './LibraryCanvasSource.vue'
import MediaViewer from './MediaViewer.vue'
import { canvasDataAgentAllowed, toggleCanvasDataControl } from './useCanvasDataSession'

const toast = useToast()
const settingsDialog = useSettingsDialog()
const importToasts = new Set<ReturnType<typeof toast.success>>()

const controls = { formItem: FormItem, button: Button, input: Input, dialog: LibraryFormDialog, multiSelect: MultiSelect, select: SearchableSingleSelect, textarea: Textarea, checkbox: Checkbox, menu: Menu, tabs: Tabs, tabsList: TabsList, tabsTrigger: TabsTrigger, canvasSource: LibraryCanvasSource, mediaViewer: MediaViewer }

const workspace = ref<InstanceType<typeof Workspace>>()
const tabs = useSidebarTabStore()
const tab = tabs.sidebarTabs.find((item) => item.id === 'library')!

onMounted(() => {
  tab.canClose = () => workspace.value!.leavePage()
})
onBeforeUnmount(() => {
  tab.canClose = undefined
  for(const id of importToasts)toast.dismiss(id)
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
        :controls="controls"
        :canvas-agent-allowed="canvasDataAgentAllowed"
        @canvas-control="toggleCanvasDataControl"
        @notify-success="message => importToasts.add(toast.success(message, { duration: 4000 }))"
        @notify-import="notice => importToasts.add(toast[notice.kind](notice.title, { description: notice.description, duration: notice.kind==='success'?4000:Infinity, action: notice.kind==='success'?undefined:{label:'查看原因',onClick:()=>workspace?.showImportIssue(notice.taskId,notice.category)} }))"
        @open-workbench-settings="settingsDialog.show('workbench')"
        @manage-equipment="workspace!.selectArea('settings', 'equipment-setups')"
        @back-to-library="workspace!.selectArea('library')"
      />
    </template>
  </SidebarTabTemplate>
</template>
