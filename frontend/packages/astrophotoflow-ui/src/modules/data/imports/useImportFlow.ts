import { ref, toValue, watch } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { LocalImportFile } from '../api/contracts'
import type { ImportNotice } from '../workspace/libraryControls'
import { workspaceQueryKey } from '../../../core/query/keys'

export interface ImportFlowOptions {
  workspace: MaybeRefOrGetter<string>
  clearSelection: () => void
  notify: (notice: ImportNotice) => void
}

export function useImportFlow(options: ImportFlowOptions) {
  const cache = useQueryClient()
  const dialogOpen = ref(false), createsDataset = ref(false)
  const files = ref<LocalImportFile[]>([]), datasetName = ref('')
  const pickerMode = ref<'files'|'folder'>()
  const issue = ref<{taskId:string;category:'content'|'preview'}>()
  const watchedTaskIds = ref<string[]>([]), refreshToken = ref(0)

  function invalidateLibrary() {
    const workspaceId=toValue(options.workspace)
    if(workspaceId)return cache.invalidateQueries({queryKey:workspaceQueryKey(workspaceId)})
  }
  function changed() { options.clearSelection(); void invalidateLibrary() }
  function start(kind:'files'|'folder', createDataset=false) { createsDataset.value=createDataset; pickerMode.value=kind }
  function selected(selectedFiles:LocalImportFile[],name:string,folder:boolean) {
    pickerMode.value=undefined;files.value=selectedFiles
    datasetName.value=folder?name:'';dialogOpen.value=true
  }
  function submitted(taskId:string) {
    dialogOpen.value=false;watchedTaskIds.value=[...watchedTaskIds.value,taskId]
    refreshToken.value++;changed()
  }
  function completed(taskId:string) { watchedTaskIds.value=watchedTaskIds.value.filter(id=>id!==taskId);changed() }
  function showIssue(taskId:string,category:'content'|'preview') { issue.value={taskId,category} }
  function refresh() { refreshToken.value++ }
  watch(()=>toValue(options.workspace),()=>{
    dialogOpen.value=false;pickerMode.value=undefined;files.value=[]
    datasetName.value='';createsDataset.value=false;issue.value=undefined;watchedTaskIds.value=[]
    refreshToken.value=0
  },{flush:'sync'})
  return {dialogOpen,files,pickerMode,createsDataset,datasetName,issue,watchedTaskIds,refreshToken,
    start,selected,submitted,registered:changed,completed,showIssue,notify:options.notify,refresh,invalidateLibrary}
}
