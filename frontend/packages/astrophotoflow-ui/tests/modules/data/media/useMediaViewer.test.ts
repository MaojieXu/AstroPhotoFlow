import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import { useMediaViewer } from '@ui/modules/data/media/useMediaViewer'
import { mediaStateSchema } from '@ui/modules/data/api/media'
import type {
  MediaViewerRequest,
  MediaMember
} from '@ui/modules/data/api/media'
function state(key: string) {
  return mediaStateSchema.parse({
    key,
    status: 'available',
    phase: null,
    kind: 'image',
    width: 6,
    height: 4,
    max_level: 3,
    tile_size: 512,
    selection: {},
    arrays: [],
    hdus: [],
    needs_selection: false,
    overview_url: '/overview/' + key,
    tile_url: '/tiles/' + key,
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
let wrapper: ReturnType<typeof mount> | undefined
let urls: Set<string>
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
async function setup(
  index = 0,
  total = 1000,
  memberOverride?: MediaViewerRequest['member']
) {
  urls = new Set()
  let sequence = 0
  vi.stubGlobal(
    'URL',
    Object.assign(class extends URL {}, {
      createObjectURL: vi.fn(() => {
        const url = 'blob:' + ++sequence
        urls.add(url)
        return url
      }),
      revokeObjectURL: vi.fn((url: string) => urls.delete(url))
    })
  )
  const member = vi.fn<MediaViewerRequest['member']>(
    memberOverride ??
      (async (index) => ({
        title: 'Frame ' + index,
        basePath: '/member/' + index,
        selection: { hdu_index: 0 }
      }))
  )
  const request = ref<MediaViewerRequest>({ index, total, member }),
    workspace = ref<string | undefined>('/one')
  const client = {
    prepare: vi.fn().mockImplementation(async (base: string) => state(base)),
    status: vi.fn(),
    release: vi.fn().mockResolvedValue(undefined),
    image: vi.fn().mockResolvedValue(new Blob(['thumbnail']))
  }
  let viewer!: ReturnType<typeof useMediaViewer>
  wrapper = mount(
    defineComponent({
      setup() {
        viewer = useMediaViewer(workspace, request, client)
        return () => null
      }
    })
  )
  await flushPromises()
  return { viewer, request, workspace, client, member }
}
it('reads only the selected member and its immediate neighbors and prepares only the selected member', async () => {
  const { viewer, member, client } = await setup(500)
  expect(member.mock.calls.map((call) => call[0]).sort()).toEqual([
    499, 500, 501
  ])
  expect(client.prepare.mock.calls.filter(([, selection]) => !selection.prefetch)).toHaveLength(1)
  expect(client.prepare).toHaveBeenCalledWith(
    '/member/500',
    expect.objectContaining({
      hdu_index: 0,
      generation: 1,
      consumer_id: expect.any(String)
    }),
    expect.any(AbortSignal)
  )
  expect(viewer.member.value?.title).toBe('Frame 500')
  expect(urls.size).toBe(3)
  viewer.open(501, { hdu_index: 0, channel_axis: null, slices: { '0': 0 } })
  await flushPromises()
  expect(member.mock.calls.map((call) => call[0]).sort()).toEqual([
    499, 500, 501, 502
  ])
  expect(client.prepare).toHaveBeenCalledWith(
    '/member/501',
    expect.objectContaining({
      hdu_index: 0,
      channel_axis: null,
      slices: { '0': 0 },
      generation: 2
    }),
    expect.any(AbortSignal)
  )
  expect(urls.size).toBe(3)
})
it('revokes old thumbnails on a direct jump and all remaining URLs and consumers on close', async () => {
  const { viewer, client } = await setup()
  const old = [...urls]
  viewer.open(998)
  await flushPromises()
  expect(urls.size).toBe(3)
  for (const url of old) expect(urls.has(url)).toBe(false)
  expect(viewer.member.value?.title).toBe('Frame 998')
  wrapper!.unmount()
  wrapper = undefined
  expect(urls.size).toBe(0)
  for (const [base, selection] of client.prepare.mock.calls)
    expect(client.release).toHaveBeenCalledWith(base, selection.consumer_id)
})
it('aborts an old workspace member and never prepares or displays its late reply', async () => {
  let finish!: (value: MediaMember) => void
  let first = true
  const { viewer, workspace, client, member } = await setup(0, 1, async () => {
    if (first) {
      first = false
      return new Promise<MediaMember>((resolve) => (finish = resolve))
    }
    return { title: 'New workspace', basePath: '/new' }
  })
  const signal = member.mock.calls[0]![1]
  workspace.value = '/two'
  await flushPromises()
  expect(signal.aborted).toBe(true)
  finish({ title: 'Old workspace', basePath: '/old' })
  await flushPromises()
  expect(viewer.member.value?.title).toBe('New workspace')
  expect(client.prepare).toHaveBeenCalledTimes(1)
  expect(client.prepare.mock.calls[0]![0]).toBe('/new')
})
it('does not replay a failed preparation and leaves selection and group membership immutable', async () => {
  vi.useFakeTimers()
  const { viewer, client, request } = await setup(0, 1)
  const original = JSON.stringify({
    index: request.value.index,
    total: request.value.total
  })
  client.prepare.mockRejectedValue(new Error('Unknown preparation'))
  viewer.open(0, { display_range: [0, 1], frame_index: 0 })
  await flushPromises()
  await vi.advanceTimersByTimeAsync(10000)
  expect(client.prepare).toHaveBeenCalledTimes(2)
  expect(client.status).not.toHaveBeenCalled()
  expect(viewer.error.value).toMatchObject({ message: 'Unknown preparation' })
  expect(
    JSON.stringify({ index: request.value.index, total: request.value.total })
  ).toBe(original)
})
it('resets to the new request and releases the previous display state', async () => {
  const { viewer, request, client } = await setup(30)
  request.value = {
    index: 4,
    total: 6,
    member: async (index) => ({
      title: 'Replacement ' + index,
      basePath: '/replacement/' + index
    })
  }
  await flushPromises()
  expect(viewer.index.value).toBe(4)
  expect(viewer.member.value?.title).toBe('Replacement 4')
  expect(client.release).toHaveBeenCalledWith('/member/30', expect.any(String))
})

it('cancels the stale neighbor prefetch when a new selection fails', async () => {
  const { viewer, client } = await setup(0, 10)
  let oldSignal: AbortSignal | undefined
  client.prepare.mockImplementation((base: string, selection: {prefetch?: boolean}, signal: AbortSignal) => {
    if (base === '/member/2' && selection.prefetch) {
      oldSignal = signal
      return new Promise(() => {})
    }
    if (base === '/member/5') return Promise.reject(new Error('new image failed'))
    return Promise.resolve(state(base))
  })
  viewer.open(1)
  await flushPromises()
  expect(oldSignal).toBeDefined()
  viewer.open(5)
  await flushPromises()
  expect(oldSignal?.aborted).toBe(true)
  expect(viewer.error.value).toMatchObject({message:'new image failed'})
})