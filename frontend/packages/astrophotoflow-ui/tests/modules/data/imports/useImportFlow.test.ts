import { mount,flushPromises } from '@vue/test-utils'
import { defineComponent,h,nextTick,ref } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { expect,it,vi } from 'vitest'
import { useImportFlow } from '@ui/modules/data/imports/useImportFlow'
import { libraryQueryKey } from '@ui/modules/data/library/queries'

it('clears previous workspace import intent and task tracking without carrying file choices across',async()=>{
  const workspace=ref('/first-workspace'),clear=vi.fn(),notify=vi.fn()
  let flow!:ReturnType<typeof useImportFlow>
  const wrapper=mount(defineComponent({setup(){flow=useImportFlow({workspace,clearSelection:clear,notify});return ()=>h('div')}}))
  try {
    flow.start('folder');flow.selected([{path:'synthetic.fit',name:'synthetic.fit',size:1}],'Night',true)
    flow.submitted('first-task');flow.showIssue('first-task','content')
    expect(flow.watchedTaskIds.value).toEqual(['first-task'])
    expect(flow.datasetName.value).toBe('Night')
    workspace.value='/second-workspace';await nextTick()
    expect(flow.files.value).toEqual([])
    expect(flow.watchedTaskIds.value).toEqual([])
    expect(flow.issue.value).toBeUndefined()
    expect(flow.dialogOpen.value).toBe(false)
    expect(flow.datasetName.value).toBe('')
    expect(flow.pickerMode.value).toBeUndefined()
    expect(notify).not.toHaveBeenCalled()
  }finally{wrapper.unmount()}
})

it('invalidates only the current library resource for accepted, registered and completed task events',async()=>{
  let flow!:ReturnType<typeof useImportFlow>
  let invalidate!:ReturnType<typeof vi.spyOn>
  const clear=vi.fn()
  const wrapper=mount(defineComponent({setup(){
    invalidate=vi.spyOn(useQueryClient(),'invalidateQueries')
    flow=useImportFlow({workspace:()=>'/isolated-workspace',clearSelection:clear,notify:vi.fn()})
    return ()=>h('div')
  }}))
  try {
    flow.submitted('task');flow.registered();flow.completed('task');await flushPromises()
    expect(clear).toHaveBeenCalledTimes(3)
    expect(invalidate).toHaveBeenCalledTimes(3)
    for(const [filters] of invalidate.mock.calls)expect(filters).toEqual({queryKey:libraryQueryKey('/isolated-workspace')})
    expect(flow.watchedTaskIds.value).toEqual([])
    expect(flow.refreshToken.value).toBe(1)
  }finally{wrapper.unmount()}
})
