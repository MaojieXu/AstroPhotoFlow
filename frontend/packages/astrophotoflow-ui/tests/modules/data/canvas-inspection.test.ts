import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import { useCanvasInspection } from '@ui/modules/data/assets/canvasQueries'
import type { CanvasInspectionRequest } from '@ui/modules/data/assets/canvasQueries'
import type { CanvasInspect } from '@ui/modules/data/api/canvas'
const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
function item(index = 0): CanvasInspect {
  return {
    title: 'Night',
    name: 'Frame ' + index,
    total: 2,
    member_index: index,
    asset_id: id(index + 10),
    asset_version_id: id(index + 2),
    view_base: '/server/member/' + index,
    availability: 'available',
    parameters: { gain: 0 },
    equipment: {},
    format: 'fits',
    width: 6000,
    height: 4000,
    bitpix: -32,
    pixel_type: 'float32',
    preview_status: 'available',
    preview_url: '/thumbnail/' + index,
    preview_error: null
  }
}
let wrapper: ReturnType<typeof mount> | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
})
async function setup() {
  const client = { inspect: vi.fn().mockResolvedValue(item()) }
  const request = ref<CanvasInspectionRequest>({
    workspaceId: '/one',
    reference: {
      kind: 'dataset_version',
      dataset_version_id: id(1),
      members: [0, 1].map((index) => ({
        member_index: index,
        asset_version_id: id(index + 2),
        selection: { kind: 'whole_file' }
      }))
    },
    memberIndex: 0
  })
  let query!: ReturnType<typeof useCanvasInspection>
  wrapper = mount(
    defineComponent({
      setup() {
        query = useCanvasInspection(request, client)
        return () => null
      }
    })
  )
  await flushPromises()
  return { query, request, client }
}
it('observes pending metadata after content becomes available and stops once the thumbnail is settled', async () => {
  vi.useFakeTimers()
  const { query, request, client } = await setup()
  client.inspect
    .mockResolvedValueOnce({
      ...item(1),
      preview_status: 'pending',
      preview_url: null
    })
    .mockResolvedValueOnce(item(1))
  request.value = { ...request.value, memberIndex: 1 }
  await flushPromises()
  expect(query.data.value?.availability).toBe('available')
  expect(query.data.value?.preview_status).toBe('pending')
  await vi.advanceTimersByTimeAsync(1500)
  await flushPromises()
  expect(query.data.value?.preview_status).toBe('available')
  await vi.advanceTimersByTimeAsync(10000)
  expect(client.inspect).toHaveBeenCalledTimes(3)
})
it('aborts the old member read and never uses its late metadata in another workspace', async () => {
  const { query, request, client } = await setup()
  let late!: (value: CanvasInspect) => void
  client.inspect.mockImplementationOnce(
    () => new Promise<CanvasInspect>((resolve) => (late = resolve))
  )
  request.value = { ...request.value, memberIndex: 1 }
  await flushPromises()
  const signal = client.inspect.mock.calls[1]![2] as AbortSignal
  client.inspect.mockResolvedValue(item(1))
  request.value = { ...request.value, workspaceId: '/two' }
  await flushPromises()
  expect(signal.aborted).toBe(true)
  late(item(1))
  await flushPromises()
  expect(query.data.value?.view_base).toBe('/server/member/1')
  expect(query.error.value).toBeNull()
})
it('rejects metadata that names another fixed asset version', async () => {
  const { query, request, client } = await setup()
  client.inspect.mockResolvedValue({ ...item(1), asset_version_id: id(99) })
  request.value = { ...request.value, memberIndex: 1 }
  await flushPromises()
  expect(query.error.value).toMatchObject({ kind: 'contract' })
  expect(query.data.value).toBeUndefined()
})
