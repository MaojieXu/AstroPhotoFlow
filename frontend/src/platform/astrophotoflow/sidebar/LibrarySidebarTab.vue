<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { useToast } from '@/components/ui/toast/toastStore'

import SidebarTabTemplate from '@/components/sidebar/tabs/SidebarTabTemplate.vue'
import { useSidebarTabStore } from '@/stores/workspace/sidebarTabStore'

import { api } from '@/scripts/api'
import { Workspace } from '@astrophotoflow/ui'
import FormItem from '@/components/common/FormItem.vue'
import Button from '@/components/ui/button/Button.vue'
import Input from '@/components/ui/input/Input.vue'
import MultiSelect from '@/components/ui/multi-select/MultiSelect.vue'
import SingleSelect from '@/components/ui/single-select/SingleSelect.vue'
import Textarea from '@/components/ui/textarea/Textarea.vue'
import Checkbox from '@/components/ui/checkbox/Checkbox.vue'
import Menu from '@/components/ui/menu/Menu.vue'
import Tabs from '@/components/ui/tabs/Tabs.vue'
import TabsList from '@/components/ui/tabs/TabsList.vue'
import TabsTrigger from '@/components/ui/tabs/TabsTrigger.vue'
import LibraryFormDialog from './LibraryFormDialog.vue'
import LibraryCanvasSource from '../canvas/LibraryCanvasSource.vue'
import MediaViewer from '../media/MediaViewer.vue'

const toast = useToast()
const props = defineProps<{ project?: boolean }>()
const importToasts = new Set<ReturnType<typeof toast.success>>()
const connectionEpoch = ref(0)
const connected = ref(true)
function reconnecting() { connected.value=false }
function reconnected() { connected.value=true; connectionEpoch.value++ }
function clearImportToasts() { for (const id of importToasts) toast.dismiss(id); importToasts.clear() }

const controls = { formItem: FormItem, button: Button, input: Input, dialog: LibraryFormDialog, multiSelect: MultiSelect, select: SingleSelect, textarea: Textarea, checkbox: Checkbox, menu: Menu, tabs: Tabs, tabsList: TabsList, tabsTrigger: TabsTrigger, canvasSource: LibraryCanvasSource, mediaViewer: MediaViewer }

const workspace = ref<InstanceType<typeof Workspace>>()
const tabs = useSidebarTabStore()
const tab = tabs.sidebarTabs.find((item) => item.id === (props.project ? 'projects' : 'library'))!

onMounted(() => {
  api.addEventListener('reconnected', reconnected)
  api.addEventListener('reconnecting', reconnecting)
  tab.canClose = () => workspace.value!.leavePage()
})
onBeforeUnmount(() => {
  tab.canClose = undefined
  api.removeEventListener('reconnected', reconnected)
  api.removeEventListener('reconnecting', reconnecting)
  clearImportToasts()
})
</script>

<template>
  <SidebarTabTemplate
    :title="$t(props.project ? 'apfUi.project' : 'astrophotoflow.library')"
    :data-testid="props.project ? 'projects-sidebar' : 'library-sidebar'"
  >
    <template #body>
      <Workspace
        ref="workspace"
        native
        sidebar
        :initial-section="props.project ? 'projects' : 'library'"
        :controls="controls"
        :connection-epoch="connectionEpoch"
        :connected="connected"
        @workspace-changed="clearImportToasts"
        @notify-success="message => importToasts.add(toast.success(message, { duration: 4000 }))"
        @notify-import="notice => importToasts.add(toast[notice.kind](notice.title, { description: notice.description, duration: notice.kind==='success'?4000:Infinity, action: notice.kind==='success'?undefined:{label:$t('apfUi.view_reason'),onClick:()=>workspace?.showImportIssue(notice.taskId,notice.category)} }))"
        @manage-equipment="workspace!.selectArea('settings', 'equipment-setups')"
        @back-to-library="workspace!.selectArea('library')"
      />
    </template>
  </SidebarTabTemplate>
</template>
