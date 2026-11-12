import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import { useMediaView } from '@ui/modules/data/media/useMediaView'
import type { MediaViewRequest } from '@ui/modules/data/media/useMediaView'
import { useMediaOverview } from '@ui/modules/data/media/useMediaOverview'
import { mediaStateSchema } from '@ui/modules/data/api/media'

function state(
  key = 'view',
  status: 'generating' | 'available' | 'failed' = 'available'
) {
  return mediaStateSchema.parse({
    key,
    status,
    phase: null,
    kind: 'image',
    width: 5,
    height: 4,
    max_level: 3,
    tile_size: 512,
    selection: {},
    arrays: [],
    hdus: [],
    needs_selection: false,
    overview_url: null,
    tile_url: null,
    video_url: null,
    mime_type: null,
    proxy: false,
    frame_index: null,
    media_time: null,
    frame_count: null,
    duration: null,
    note: null,
    display_recipe: null,
    error: null
  })
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => (resolve = done))
  return { promise, resolve }
}
let wrapper: ReturnType<typeof mount> | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
async function setup(initial = state()) {
  const client = {
    prepare: vi.fn().mockResolvedValue(initial),
    status: vi.fn(),
    release: vi.fn().mockResolvedValue(undefined),
    image: vi.fn()
  }
  const request = ref<MediaViewRequest | undefined>({
    workspaceId: '/one',
    basePath: '/member',
    selection: { hdu_index: 0, frame_index: null }
  })
  let view!: ReturnType<typeof useMediaView>
  wrapper = mount(
    defineComponent({
      setup() {
        view = useMediaView(request, client)
        return () => null
      }
    })
  )
  await flushPromises()
  return { view, client, request }
}
it('prepares once with a real consumer and protocol generation, preserving null and zero', async () => {
  const { view, client } = await setup()
  expect(client.prepare).toHaveBeenCalledTimes(1)
  expect(client.prepare).toHaveBeenCalledWith(
    '/member',
    expect.objectContaining({
      hdu_index: 0,
      frame_index: null,
      consumer_id: expect.any(String),
      generation: 1
    }),
    expect.any(AbortSignal)
  )
  expect(view.state.value?.status).toBe('available')
  expect(client.status).not.toHaveBeenCalled()
})
it('polls only the original prepared key and stops at a terminal state without replaying preparation', async () => {
  vi.useFakeTimers()
  const { view, client } = await setup(state('view', 'generating'))
  client.status
    .mockResolvedValueOnce(state('view', 'generating'))
    .mockResolvedValue(state('view'))
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(view.state.value?.status).toBe('available')
  await vi.advanceTimersByTimeAsync(10000)
  expect(client.status).toHaveBeenCalledTimes(2)
  expect(client.status).toHaveBeenCalledWith(
    '/member',
    'view',
    expect.any(AbortSignal)
  )
  expect(client.prepare).toHaveBeenCalledTimes(1)
})
it('aborts an old prepare and ignores its late result after selection changes', async () => {
  const { view, client, request } = await setup()
  const old = deferred<ReturnType<typeof state>>()
  client.prepare
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(state('new'))
  request.value = { ...request.value!, selection: { hdu_index: 1 } }
  await flushPromises()
  const signal = client.prepare.mock.calls[1]![2] as AbortSignal
  const consumer = client.prepare.mock.calls[1]![1].consumer_id
  request.value = { ...request.value!, selection: { hdu_index: 2 } }
  await flushPromises()
  expect(signal.aborted).toBe(true)
  expect(client.release).toHaveBeenCalledWith('/member', consumer)
  old.resolve(state('old'))
  await flushPromises()
  expect(view.state.value?.key).toBe('new')
  expect(client.prepare.mock.calls[2]![1].generation).toBe(3)
})
it('hides the previous workspace immediately and never adopts its late status', async () => {
  vi.useFakeTimers()
  const { view, client, request } = await setup(state('old', 'generating'))
  const old = deferred<ReturnType<typeof state>>()
  client.status.mockReturnValue(old.promise)
  await vi.advanceTimersByTimeAsync(1000)
  const signal = client.status.mock.calls[0]![2] as AbortSignal
  const next = deferred<ReturnType<typeof state>>()
  client.prepare.mockReturnValue(next.promise)
  request.value = { ...request.value!, workspaceId: '/two' }
  expect(view.state.value).toBeUndefined()
  await flushPromises()
  expect(signal.aborted).toBe(true)
  old.resolve(state('old'))
  next.resolve(state('new'))
  await flushPromises()
  expect(view.state.value?.key).toBe('new')
})
it('releases the consumer and aborts a live status read on close', async () => {
  vi.useFakeTimers()
  const { client } = await setup(state('view', 'generating'))
  client.status.mockReturnValue(new Promise(() => {}))
  await vi.advanceTimersByTimeAsync(1000)
  const signal = client.status.mock.calls[0]![2] as AbortSignal
  const selection = client.prepare.mock.calls[0]![1]
  wrapper!.unmount()
  wrapper = undefined
  expect(signal.aborted).toBe(true)
  expect(client.release).toHaveBeenCalledExactlyOnceWith(
    '/member',
    selection.consumer_id
  )
})
it('rejects a status for a different view and stops polling', async () => {
  vi.useFakeTimers()
  const { view, client } = await setup(state('view', 'generating'))
  client.status.mockResolvedValue(state('another'))
  await vi.advanceTimersByTimeAsync(1000)
  await flushPromises()
  expect(view.error.value).toMatchObject({ kind: 'contract' })
  expect(view.state.value?.key).toBe('view')
  await vi.advanceTimersByTimeAsync(5000)
  expect(client.status).toHaveBeenCalledTimes(1)
  expect(client.prepare).toHaveBeenCalledTimes(1)
})
it('does not automatically replay a prepare with unknown acceptance', async () => {
  vi.useFakeTimers()
  const { view, client, request } = await setup()
  client.prepare.mockRejectedValue(new Error('Unknown acceptance'))
  request.value = { ...request.value!, basePath: '/other' }
  await flushPromises()
  await vi.advanceTimersByTimeAsync(60000)
  expect(client.prepare).toHaveBeenCalledTimes(2)
  expect(client.status).not.toHaveBeenCalled()
  expect(view.error.value).toMatchObject({ message: 'Unknown acceptance' })
})
it('keeps a failed display state and its reason instead of presenting an old preview', async () => {
  const failed = {
    ...state('failed', 'failed'),
    error: { code: 'READ_FAILED', message: 'Output changed' }
  }
  const { view } = await setup(failed)
  expect(view.state.value?.status).toBe('failed')
  expect(view.error.value).toBe('Output changed')
  expect(view.loading.value).toBe(false)
})
it('cancels obsolete overview reads and revokes each displayed object URL', async () => {
  const create = vi
      .fn()
      .mockReturnValueOnce('blob:first')
      .mockReturnValueOnce('blob:second'),
    revoke = vi.fn()
  vi.stubGlobal(
    'URL',
    Object.assign(class extends URL {}, {
      createObjectURL: create,
      revokeObjectURL: revoke
    })
  )
  const first = new Blob(['first']),
    second = new Blob(['second']),
    late = deferred<Blob>()
  const client = {
    prepare: vi.fn(),
    status: vi.fn(),
    release: vi.fn(),
    image: vi
      .fn()
      .mockResolvedValueOnce(first)
      .mockReturnValueOnce(late.promise)
      .mockResolvedValueOnce(second)
  }
  const request = ref({ workspaceId: '/one', url: '/first', viewKey: 'first' })
  let overview!: ReturnType<typeof useMediaOverview>
  wrapper = mount(
    defineComponent({
      setup() {
        overview = useMediaOverview(request, client)
        return () => null
      }
    })
  )
  await flushPromises()
  expect(overview.imageUrl.value).toBe('blob:first')
  request.value = { workspaceId: '/one', url: '/late', viewKey: 'late' }
  await flushPromises()
  expect(revoke).toHaveBeenCalledWith('blob:first')
  const signal = client.image.mock.calls[1]![1] as AbortSignal
  request.value = { workspaceId: '/two', url: '/second', viewKey: 'second' }
  await flushPromises()
  expect(signal.aborted).toBe(true)
  late.resolve(new Blob(['late']))
  await flushPromises()
  expect(overview.imageUrl.value).toBe('blob:second')
  expect(create).toHaveBeenCalledTimes(2)
  wrapper.unmount()
  wrapper = undefined
  expect(revoke).toHaveBeenCalledWith('blob:second')
})
