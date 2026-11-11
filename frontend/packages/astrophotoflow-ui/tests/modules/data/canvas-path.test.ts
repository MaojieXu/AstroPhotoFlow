import { afterEach, expect, it, vi } from 'vitest'
import { createCanvasDataClient } from '@ui/modules/data/api/canvas'
import { createImportClient } from '@ui/modules/data/api/imports'
import { useCanvasPathImport } from '@ui/modules/data/imports/useCanvasPathImport'
import { defineComponent, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
let wrapper: ReturnType<typeof mount> | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
})
function setup(fetch: Parameters<typeof createCanvasDataClient>[0]) {
  const workspace = ref<string | undefined>('/one')
  let flow!: ReturnType<typeof useCanvasPathImport>
  wrapper = mount(
    defineComponent({
      setup() {
        flow = useCanvasPathImport(
          workspace,
          createImportClient(fetch),
          createCanvasDataClient(fetch)
        )
        return () => null
      }
    })
  )
  return { flow, workspace }
}

const id = (value: number) =>
  `00000000-0000-4000-8000-${String(value).padStart(12, '0')}`
const timestamp = '2026-10-30T00:00:00Z'
const task = {
  id: id(1),
  status: 'running',
  sources: [],
  storage_mode: 'managed',
  classification: {},
  parameters: {},
  notes: null,
  dataset_name: null,
  target_dataset_id: null,
  dataset_base_revision: null,
  dataset_id: null,
  enumeration_completed: true,
  retry_of_task_id: null,
  report: {},
  error: null,
  created_at: timestamp,
  updated_at: timestamp,
  items_total: 1,
  items_completed: 0,
  items_limit: 20,
  items_offset: 0,
  items: [
    {
      id: id(2),
      task_id: id(1),
      root_item_id: id(2),
      retry_of_item_id: null,
      root_id: '',
      source_path: 'C:/Images/source.fit',
      position: 0,
      status: 'running',
      content_status: 'available',
      metadata_status: 'pending',
      preview_status: 'pending',
      asset_id: id(3),
      error: null,
      created_at: timestamp,
      updated_at: timestamp
    }
  ]
}

it('binds the imported registered asset before preview generation finishes', async () => {
  const prepared = {
    native_type: 'APF_DATA_REFERENCE',
    title: 'source.fit',
    reference: {
                 kind: 'asset',
                 asset_id: id(3),
                 selection: { kind: 'whole_file' }
               }
  }
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockResolvedValueOnce(Response.json(task))
    .mockResolvedValueOnce(Response.json(prepared))
  const { flow } = setup(fetch)
  expect(await flow.start('C:/Images/source.fit')).toEqual(prepared)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    sources: [{ path: 'C:/Images/source.fit' }],
    storage_mode: 'managed'
  })
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({
                                                            entry_type: 'asset',
                                                            id: id(3)
                                                          })
})

it('reports an import failure without submitting another import', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockResolvedValueOnce(
      Response.json({
        ...task,
        status: 'failed',
        items: [],
        error: { message: 'Source unavailable' }
      })
    )
  const { flow } = setup(fetch)
  expect(await flow.start('C:/Images/missing.fit')).toBeUndefined()
  expect(flow.error.value).toBe('Source unavailable')
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('never automatically repeats an import whose acceptance is unknown, including an explicit same-path retry', async () => {
  const fetch = vi.fn().mockRejectedValue(new TypeError('Offline'))
  const { flow } = setup(fetch)
  expect(await flow.start('C:/Images/unknown.fit')).toBeUndefined()
  expect(flow.unknown.value).toBe(true)
  await flow.start('C:/Images/unknown.fit')
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('observes only the original task until content is ready and stops before preview completion', async () => {
  vi.useFakeTimers()
  const prepared = {
    native_type: 'APF_DATA_REFERENCE',
    title: 'source.fit',
    reference: {
                 kind: 'asset',
                 asset_id: id(3),
                 selection: { kind: 'whole_file' }
               }
  }
  const waiting = {
    ...task,
    items: [
      {
        ...task.items[0],
        content_status: 'pending',
        asset_id: null
      }
    ]
  }
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockResolvedValueOnce(Response.json(waiting))
    .mockResolvedValueOnce(Response.json(task))
    .mockResolvedValueOnce(Response.json(prepared))
  const { flow } = setup(fetch)
  const complete = flow.start('C:/Images/source.fit')
  await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(2)
  await vi.advanceTimersByTimeAsync(1500)
  await flushPromises()
  expect(await complete).toEqual(prepared)
  await vi.advanceTimersByTimeAsync(10000)
  expect(fetch).toHaveBeenCalledTimes(4)
  expect(
    fetch.mock.calls.filter((call) => String(call[0]).endsWith('/imports'))
  ).toHaveLength(1)
  expect(flow.taskId.value).toBe(id(1))
})
it('recovers a failed observation by reading the original task, not submitting another import', async () => {
  const prepared = {
    native_type: 'APF_DATA_REFERENCE',
    title: 'source.fit',
    reference: {
                 kind: 'asset',
                 asset_id: id(3),
                 selection: { kind: 'whole_file' }
               }
  }
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockRejectedValueOnce(new TypeError('Disconnected'))
  const { flow } = setup(fetch)
  expect(await flow.start('C:/Images/source.fit')).toBeUndefined()
  fetch
    .mockResolvedValueOnce(Response.json(task))
    .mockResolvedValueOnce(Response.json(prepared))
  expect(await flow.start('C:/Images/source.fit')).toEqual(prepared)
  expect(
    fetch.mock.calls.filter((call) => String(call[0]).endsWith('/imports'))
  ).toHaveLength(1)
})
it('cancels local observation across workspaces and ignores a late old task response', async () => {
  let resolve!: (value: Response) => void
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockImplementationOnce(
      () => new Promise<Response>((done) => (resolve = done))
    )
  const { flow, workspace } = setup(fetch)
  const complete = flow.start('C:/Images/source.fit')
  await flushPromises()
  const signal = fetch.mock.calls[1]![1].signal as AbortSignal
  workspace.value = '/two'
  expect(await complete).toBeUndefined()
  await flushPromises()
  expect(signal.aborted).toBe(true)
  resolve(Response.json(task))
  await flushPromises()
  expect(fetch).toHaveBeenCalledTimes(2)
})

it('records unknown acceptance synchronously on disconnect and never resubmits before the late receipt arrives', async () => {
  let accept!: (value: Response) => void
  const fetch = vi
    .fn()
    .mockImplementationOnce(
      () => new Promise<Response>((done) => (accept = done))
    )
  const { flow, workspace } = setup(fetch)
  const completion = flow.start('C:/Images/source.fit')
  await flushPromises()
  workspace.value = undefined
  expect(await completion).toBeUndefined()
  workspace.value = '/one'
  await flow.start('C:/Images/source.fit')
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(flow.unknown.value).toBe(true)
  fetch.mockResolvedValue(
    Response.json({
      ...task,
      status: 'failed',
      items: [],
      error: { message: 'Receipt recovered' }
    })
  )
  accept(Response.json({ task_id: id(1), status: 'queued' }))
  await flushPromises()
  expect(flow.taskId.value).toBe(id(1))
  expect(
    fetch.mock.calls.filter((call) => String(call[0]).endsWith('/imports'))
  ).toHaveLength(1)
})
