import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import type { QueryClient } from '@tanstack/vue-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import Workspace from '@ui/modules/data/workspace/Workspace.vue'
import WorkspacePage from '@ui/modules/data/workspace/WorkspacePage.vue'
import { useWorkspaceStore } from '@ui/modules/data/workspace/store'
import { workspaceQueryKey } from '@ui/core/query/keys'
import { ApiClientError } from '@ui/core/api/errors'

const { get, send, health } = vi.hoisted(() => ({
  get: vi.fn(),
  send: vi.fn(),
  health: vi.fn()
}))
vi.mock('@ui/modules/data/api/index', async () => {
  const fixture = await import('../../../fixtures/library-api')
  return {
    catalogApi: { ...fixture.createCatalogApiFixture(get), health },
    libraryApi: fixture.createLibraryApiFixture(get),
    mutationApi: fixture.createMutationApiFixture(send),
    trashApi: fixture.createTrashApiFixture(get, send),
    datasetApi: fixture.createDatasetApiFixture(get, send),
    importApi: fixture.createImportApiFixture(get, send),
    assetApi: { get, send }
  }
})
const capabilities = {
  stage: 'ingestion',
  shared_library_read: true,
  project_assets_read: true,
  project_management: true,
  equipment_management: true,
  asset_import: true,
  asset_reference_write: true,
  asset_preview: false,
  asset_metadata_edit: true,
  dataset_management: true,
  asset_task_management: true,
  calibration_matching: false,
  asset_publish: false
}
const identity = (workspace: string) => ({
  status: 'ok',
  api_version: 'v1',
  database: 'ready',
  schema_revision: '0001',
  workspace
})
let wrapper: ReturnType<typeof mount>, cache: QueryClient
beforeEach(() => {
  health.mockReset().mockResolvedValue(identity('/one'))
  get
    .mockReset()
    .mockImplementation(async (path: string) =>
      path.endsWith('/capabilities')
        ? capabilities
        : { items: [], total: 0, limit: 200, offset: 0 }
    )
  send.mockReset()
})
afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
})
async function open() {
  wrapper = mount(
    defineComponent({
      props: {
        epoch: { default: 0 },
        visible: { default: true },
        connected: { default: true }
      },
      setup(props) {
        cache = useQueryClient()
        return () =>
          props.visible
            ? h(Workspace, {
                connectionEpoch: props.epoch,
                connected: props.connected
              })
            : null
      }
    }),
    { global: { plugins: [createPinia()] } }
  )
  await flushPromises()
}
async function draft() {
  await wrapper
    .getComponent(Workspace)
    .vm.selectArea('settings', 'equipment-setups')
  await flushPromises()
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '新建设备组合')!
    .trigger('click')
  await flushPromises()
  await wrapper.get('#setup-name').setValue('Unsaved original workspace rig')
}

it('pauses owner reads and hides teleported dialogs during verification, then restores same-workspace drafts', async () => {
  vi.useFakeTimers()
  await open()
  await draft()
  const page = wrapper.getComponent(WorkspacePage).vm.$.uid
  let finish!: (value: ReturnType<typeof identity>) => void
  health.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      })
  )
  await wrapper.setProps({ epoch: 1 })
  await flushPromises()
  expect(wrapper.find('#setup-name').exists()).toBe(false)
  expect(wrapper.getComponent(WorkspacePage).vm.$.uid).toBe(page)
  const reads = get.mock.calls.length
  await vi.advanceTimersByTimeAsync(11_000)
  await flushPromises()
  expect(get).toHaveBeenCalledTimes(reads)
  expect(send).not.toHaveBeenCalled()
  finish(identity('/one'))
  await flushPromises()
  expect(wrapper.getComponent(WorkspacePage).vm.$.uid).toBe(page)
  expect(wrapper.get<HTMLInputElement>('#setup-name').element.value).toBe(
    'Unsaved original workspace rig'
  )
})

it('drops old workspace identifiers and aborts/removes its cached reads before mounting another workspace', async () => {
  await open()
  await draft()
  const page = wrapper.getComponent(WorkspacePage).vm.$.uid
  const store = useWorkspaceStore()
  store.activeProjectId = 'old-project'
  store.activeProjectRevision = 9
  cache.setQueryData([...workspaceQueryKey('/one'), 'library', 'proof'], {
    old: true
  })
  cache.setQueryData([...workspaceQueryKey('/unrelated'), 'library'], {
    retained: true
  })
  let signal!: AbortSignal, finish!: (value: unknown) => void
  const pending = cache
    .fetchQuery({
      queryKey: [...workspaceQueryKey('/one'), 'late-read'],
      queryFn: ({ signal: requestSignal }) => {
        signal = requestSignal
        return new Promise((resolve) => {
          finish = resolve
        })
      }
    })
    .catch(() => undefined)
  health.mockResolvedValueOnce(identity('/two'))
  await wrapper.setProps({ epoch: 1 })
  await flushPromises()
  expect(signal.aborted).toBe(true)
  finish({ old: true })
  await pending
  await flushPromises()
  expect(wrapper.getComponent(WorkspacePage).vm.$.uid).not.toBe(page)
  expect(wrapper.getComponent(WorkspacePage).props('workspaceId')).toBe('/two')
  expect(wrapper.find('#setup-name').exists()).toBe(false)
  expect(store.activeProjectId).toBeNull()
  expect(store.activeProjectRevision).toBeNull()
  expect(cache.getQueriesData({ queryKey: workspaceQueryKey('/one') })).toEqual(
    []
  )
  expect(
    cache.getQueryData([...workspaceQueryKey('/unrelated'), 'library'])
  ).toEqual({ retained: true })
  expect(wrapper.getComponent(Workspace).emitted('workspace-changed')).toEqual([
    ['/two']
  ])
  expect(send).not.toHaveBeenCalled()
})

it('keeps an unverified draft after connection failure and retries only on explicit request', async () => {
  await open()
  await draft()
  const page = wrapper.getComponent(WorkspacePage).vm.$.uid
  health.mockRejectedValueOnce(
    new ApiClientError('Unavailable', 'service', 503, 'SERVICE_UNAVAILABLE')
  )
  await wrapper.setProps({ epoch: 1 })
  await flushPromises()
  expect(wrapper.text()).toContain('资产服务当前不可用')
  expect(wrapper.find('#setup-name').exists()).toBe(false)
  expect(health).toHaveBeenCalledTimes(2)
  health.mockResolvedValueOnce(identity('/one'))
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '重试')!
    .trigger('click')
  await flushPromises()
  expect(health).toHaveBeenCalledTimes(3)
  expect(wrapper.getComponent(WorkspacePage).vm.$.uid).toBe(page)
  expect(wrapper.get<HTMLInputElement>('#setup-name').element.value).toBe(
    'Unsaved original workspace rig'
  )
  expect(send).not.toHaveBeenCalled()
})

it('does not mount from cached identity when a new tab must verify a potentially different workspace', async () => {
  await open()
  await wrapper.setProps({ visible: false })
  await flushPromises()
  let finish!: (value: ReturnType<typeof identity>) => void
  health.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      })
  )
  await wrapper.setProps({ visible: true })
  await flushPromises()
  expect(wrapper.findComponent(WorkspacePage).exists()).toBe(false)
  finish(identity('/two'))
  await flushPromises()
  expect(wrapper.getComponent(WorkspacePage).props('workspaceId')).toBe('/two')
  expect(health).toHaveBeenCalledTimes(2)
})

it('aborts an identity read on disconnect and ignores its late result after the next real connection', async () => {
  await open()
  await draft()
  let finish!: (value: ReturnType<typeof identity>) => void
  health.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      })
  )
  await wrapper.setProps({ epoch: 1 })
  await flushPromises()
  const signal = health.mock.calls[1][0] as AbortSignal
  await wrapper.setProps({ connected: false })
  await flushPromises()
  expect(signal.aborted).toBe(true)
  expect(wrapper.text()).toContain('正在重新连接工作台')
  const calls = health.mock.calls.length
  await flushPromises()
  expect(health).toHaveBeenCalledTimes(calls)
  health.mockResolvedValueOnce(identity('/one'))
  await wrapper.setProps({ connected: true, epoch: 2 })
  await flushPromises()
  finish(identity('/obsolete'))
  await flushPromises()
  expect(wrapper.getComponent(WorkspacePage).props('workspaceId')).toBe('/one')
  expect(wrapper.get<HTMLInputElement>('#setup-name').element.value).toBe(
    'Unsaved original workspace rig'
  )
})
