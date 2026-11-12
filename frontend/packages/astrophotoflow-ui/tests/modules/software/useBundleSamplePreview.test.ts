import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'
import { useBundleSamplePreview } from '@ui/modules/software/previews/useBundleSamplePreview'
import type { BundleSampleRequest } from '@ui/modules/software/previews/useBundleSamplePreview'
let wrapper: ReturnType<typeof mount> | undefined
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
async function setup() {
  vi.useFakeTimers({ shouldAdvanceTime: false })
  let seq = 0
  vi.stubGlobal(
    'URL',
    Object.assign(class extends URL {}, {
      createObjectURL: vi.fn(() => `blob:${++seq}`),
      revokeObjectURL: vi.fn()
    })
  )
  const client = {
    render: vi.fn().mockResolvedValue(new Blob(['png'])),
    release: vi.fn().mockResolvedValue(undefined)
  }
  const request = ref<BundleSampleRequest | undefined>({
    workspaceId: '/one',
    sourceKey: 'fixed-member',
    identity: 'first',
    body: {
      reference: {
        kind: 'asset',
        asset_id: '00000000-0000-4000-8000-000000000001',
        selection: { kind: 'whole_file' }
      },
      member_index: 0,
      parameters: { gain: 0 },
      package_id: 'siril',
      operation_id: 'autostretch'
    }
  })
  let preview!: ReturnType<typeof useBundleSamplePreview>
  wrapper = mount(
    defineComponent({
      setup() {
        preview = useBundleSamplePreview(request, client)
        return () => null
      }
    })
  )
  await flushPromises()
  return { preview, request, client }
}
it('debounces actual execution and preserves zero without automatically retrying an uncertain result', async () => {
  const { preview, request, client } = await setup()
  request.value = {
    ...request.value!,
    identity: 'second',
    body: { ...request.value!.body, parameters: { gain: 0, linked: false } }
  }
  await vi.advanceTimersByTimeAsync(349)
  expect(client.render).not.toHaveBeenCalled()
  client.render.mockRejectedValue(new Error('Unknown acceptance'))
  await vi.advanceTimersByTimeAsync(1)
  await flushPromises()
  expect(client.render).toHaveBeenCalledTimes(1)
  expect(client.render.mock.calls[0]![0].parameters).toEqual({
    gain: 0,
    linked: false
  })
  await vi.advanceTimersByTimeAsync(10000)
  expect(client.render).toHaveBeenCalledTimes(1)
  expect(preview.error.value).toMatchObject({ message: 'Unknown acceptance' })
})
it('keeps an explicitly stale preview while editing the same source, but clears it for a different workspace', async () => {
  const { preview, request } = await setup()
  await vi.advanceTimersByTimeAsync(350)
  expect(preview.image.value).toBe('blob:1')
  request.value = { ...request.value!, identity: 'new parameters' }
  expect(preview.waiting.value).toBe(true)
  expect(preview.image.value).toBe('blob:1')
  request.value = { ...request.value!, workspaceId: '/two' }
  expect(preview.image.value).toBe('')
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:1')
})
it('aborts and releases a started sample when collapsed and ignores a late result', async () => {
  const { preview, request, client } = await setup()
  let finish!: (value: Blob) => void
  client.render.mockImplementationOnce(
    () => new Promise<Blob>((resolve) => (finish = resolve))
  )
  await vi.advanceTimersByTimeAsync(350)
  const signal = client.render.mock.calls[0]![1] as AbortSignal
  request.value = undefined
  expect(signal.aborted).toBe(true)
  expect(client.release).toHaveBeenCalledTimes(1)
  finish(new Blob(['late']))
  await flushPromises()
  expect(preview.image.value).toBe('')
  expect(URL.createObjectURL).not.toHaveBeenCalled()
})
it('does not execute or release a consumer whose debounce never started', async () => {
  const { request, client } = await setup()
  request.value = undefined
  await vi.advanceTimersByTimeAsync(1000)
  expect(client.render).not.toHaveBeenCalled()
  expect(client.release).not.toHaveBeenCalled()
})
