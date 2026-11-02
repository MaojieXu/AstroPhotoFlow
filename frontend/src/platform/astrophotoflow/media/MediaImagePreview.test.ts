import { render, screen, waitFor, fireEvent } from '@testing-library/vue'
import { beforeEach, expect, it, vi } from 'vitest'
import { PlatformQueryPlugin, mediaStateSchema } from '@astrophotoflow/ui'
import MediaImagePreview from './MediaImagePreview.vue'
vi.mock('../useNativeWorkspace')
const client = vi.hoisted(() => ({
  prepare: vi.fn(),
  status: vi.fn(),
  release: vi.fn(),
  image: vi.fn()
}))
vi.mock(import('@astrophotoflow/ui'), async (original) => ({
  ...(await original()),
  createMediaClient: () => client
}))
vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key })
}))
beforeEach(() => {
  client.release.mockResolvedValue(undefined)
  client.image.mockResolvedValue(new Blob(['preview']))
  client.prepare.mockImplementation(async (base: string) =>
    mediaStateSchema.parse({
      key: base,
      status: 'available',
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
      overview_url: base + '/overview',
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
  )
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:preview')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})
it('uses the shared display consumer and opens with the actual display settings', async () => {
  const view = render(MediaImagePreview, {
    props: { base: '/checked/result', title: 'Full result' },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await screen.findByAltText('Full result')
  expect(client.prepare).toHaveBeenCalledWith(
    '/checked/result',
    expect.objectContaining({
      frame_index: 0,
      preview_max_edge: 1024,
      display_balance: null,
      consumer_id: expect.any(String)
    }),
    expect.any(AbortSignal)
  )
  await fireEvent.click(
    screen.getByRole('button', { name: 'astrophotoflow.media.open' })
  )
  expect(view.emitted().open?.[0]).toEqual([
    { preview_max_edge: 1024, display_balance: null }
  ])
  view.unmount()
  expect(client.release).toHaveBeenCalledTimes(1)
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview')
})
it('aborts the old overview on a changed checked result and ignores its late pixels', async () => {
  let finish!: (value: Blob) => void
  client.image.mockImplementationOnce(
    () => new Promise<Blob>((resolve) => (finish = resolve))
  )
  const view = render(MediaImagePreview, {
    props: { base: '/old', title: 'Result' },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await waitFor(() => expect(client.image).toHaveBeenCalledTimes(1))
  const signal = client.image.mock.calls[0]![1] as AbortSignal
  await view.rerender({ base: '/new', title: 'Result' })
  await screen.findByAltText('Result')
  expect(signal.aborted).toBe(true)
  finish(new Blob(['old']))
  await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalledTimes(1))
  expect(client.image).toHaveBeenLastCalledWith(
    '/new/overview',
    expect.any(AbortSignal)
  )
})
