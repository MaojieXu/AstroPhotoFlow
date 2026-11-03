import { defineComponent, h, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDatasetView } from '@ui/modules/data/datasets/useDatasetView'
import type { WorkspaceRecord } from '@ui/modules/data/workspace/recordTypes'

const { getDataset, getChanges } = vi.hoisted(() => ({ getDataset: vi.fn(), getChanges: vi.fn() }))
vi.mock('@ui/modules/data/api', () => ({ datasetApi: { get: getDataset }, libraryApi: {changeState:getChanges} }))

let wrapper: ReturnType<typeof mount> | undefined
beforeEach(() => { vi.useFakeTimers(); getDataset.mockReset(); getChanges.mockReset().mockResolvedValue({revision_token:'one',thumbnail_token:'one'}) })
afterEach(() => { wrapper?.unmount(); vi.useRealTimers() })

function harness(workspace: string, followsCurrent: boolean) {
  let view!: ReturnType<typeof useDatasetView>
  const paused = ref(false)
  wrapper = mount(defineComponent({ setup() {
    view = useDatasetView({
      workspaceId: workspace, paused,
      navigation: {query:'',offset:0,pageSize:50}, sort:ref<{by:string;order:'asc'|'desc'}>({by:'name',order:'asc'}),
      mode:ref<'simple'|'detail'>('simple'), filterOpen:ref(false), records:ref<WorkspaceRecord[]>([]),
      libraryActive:true, dirty:false, calibrationDirty:false,
      waitForInlineSave:async()=>true, error:ref()
    })
    return () => h('div')
  } }))
  view.activeDataset.value = {id:'group',name:'Group',revision:1,member_count:2,current_version_id:'version-1',followsCurrent}
  return {view,paused}
}

describe('current and fixed dataset refresh', () => {
  it('adopts external publications on the next lightweight interval', async () => {
    getDataset.mockResolvedValue({id:'group',name:'Group',revision:1,member_count:2,current_version_id:'version-1'})
    const {view,paused} = harness('current-refresh', true)
    await flushPromises()
    expect(getDataset).toHaveBeenCalledTimes(1)
    getDataset.mockResolvedValue({id:'group',name:'Group',revision:2,member_count:4,current_version_id:'version-2'})
    getChanges.mockResolvedValue({revision_token:'two',thumbnail_token:'one'})
    await vi.advanceTimersByTimeAsync(10_000)
    await flushPromises()
    expect(view.activeDataset.value?.current_version_id).toBe('version-2')
    expect(view.activeDataset.value?.member_count).toBe(4)
    paused.value = true
    await flushPromises()
    const reads = getDataset.mock.calls.length
    await vi.advanceTimersByTimeAsync(10_000)
    expect(getDataset).toHaveBeenCalledTimes(reads)
  })

  it('does not retarget an explicitly fixed historical view', async () => {
    const {view} = harness('fixed-refresh', false)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(20_000)
    expect(getDataset).not.toHaveBeenCalled()
    expect(view.activeDataset.value?.current_version_id).toBe('version-1')
  })
})
