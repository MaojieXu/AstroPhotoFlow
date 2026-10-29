import { nextTick } from 'vue'
import { createMediaClient, mediaStateSchema } from '@astrophotoflow/ui'
import type { MediaViewerRequest } from '@astrophotoflow/ui'
import userEvent from '@testing-library/user-event'
import { fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MediaViewer from './MediaViewer.vue'
import { createImageViewport } from './mediaViewport'

vi.mock(import('@astrophotoflow/ui'), async original => ({
  ...await original(),
  createMediaClient: vi.fn()
}))
vi.mock(import('./mediaViewport'), async original => ({
  ...await original(),
  createImageViewport: vi.fn()
}))
vi.mock('vue-i18n', async original => ({ ...await original<typeof import('vue-i18n')>(), useI18n: () => ({ t: (key: string) => key }) }))

function image(name = 'first') {
  return mediaStateSchema.parse({
    key: name, status: 'available', kind: 'image', width: 6400, height: 4800, max_level: 13, tile_size: 512,
    selection: {}, arrays: [], needs_selection: false, overview_url: '/overview/' + name,
    tile_url: '/tiles/' + name + '/{level}/{x}/{y}', video_url: null, mime_type: null,
    proxy: false, frame_index: null, media_time: null, frame_count: null, duration: null, note: null, error: null
  })
}

function setup(total = 1000) {
  const prepare = vi.fn<ReturnType<typeof createMediaClient>['prepare']>(async base => image(base))
  const status = vi.fn<ReturnType<typeof createMediaClient>['status']>()
  const viewport = {
    fit: vi.fn(), actual: vi.fn(), zoomBy: vi.fn(), destroy: vi.fn(),
    snapshot: vi.fn(() => ({ width: 6400, height: 4800, center: [0.3, 0.4] as [number, number], zoom: 1 }))
  }
  vi.mocked(createMediaClient).mockReturnValue({ prepare, status })
  vi.mocked(createImageViewport).mockReturnValue(viewport)
  const member = vi.fn<MediaViewerRequest['member']>(async index => ({ title: `Frame ${index + 1}`, basePath: `/frame/${index}` }))
  const request = { index: 0, total, member }
  const view = render(MediaViewer, { props: { request } })
  return { ...view, request, prepare, status, viewport, member }
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })))
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)
})

afterEach(() => vi.useRealTimers())

describe('shared original-resolution media viewer', () => {
  it('opens one of a thousand frames, prefetches only adjacent thumbnails and preserves the view on switching', async () => {
    const user = userEvent.setup()
    const { member, prepare, viewport } = setup()
    await screen.findByText('Frame 1')
    await waitFor(() => expect(createImageViewport).toHaveBeenCalled())
    await waitFor(() => expect(member).toHaveBeenCalledWith(1, expect.any(AbortSignal)))
    expect(prepare).toHaveBeenCalledTimes(1)
    expect(member.mock.calls.every(([index]) => index === 0 || index === 1)).toBe(true)
    await user.click(screen.getByRole('button', { name: '100%' }))
    expect(viewport.actual).toHaveBeenCalledOnce()
    await user.click(screen.getByRole('button', { name: 'g.nextImage' }))
    await screen.findByText('Frame 2')
    await waitFor(() => expect(createImageViewport).toHaveBeenCalledTimes(2))
    expect(vi.mocked(createImageViewport).mock.calls[1]?.[2].previous).toEqual(viewport.snapshot())
    expect(prepare).toHaveBeenLastCalledWith('/frame/1', expect.objectContaining({ generation: 2 }))
  })

  it('ignores a late preparation after a direct jump and releases the viewer on closing', async () => {
    const user = userEvent.setup()
    const view = setup()
    await waitFor(() => expect(createImageViewport).toHaveBeenCalled())
    let finish: ((value: ReturnType<typeof image>) => void) | undefined
    view.prepare.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await user.click(screen.getByRole('button', { name: 'g.nextImage' }))
    const input = screen.getByRole('spinbutton', { name: 'astrophotoflow.media.memberIndex' })
    await fireEvent.update(input, '999')
    await fireEvent.change(input)
    await screen.findByText('Frame 999')
    finish?.(image('late'))
    await waitFor(() => expect(vi.mocked(createImageViewport).mock.calls.at(-1)?.[1].key).toBe('/frame/998'))
    view.unmount()
    expect(view.viewport.destroy).toHaveBeenCalled()
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/viewer/consumer/'), expect.objectContaining({ method: 'DELETE', keepalive: true }))
  })

  it('shows an explicit source error and does not create a fake low-resolution viewport', async () => {
    const view = setup(1)
    view.prepare.mockResolvedValueOnce({ ...image(), status: 'failed', error: { code: 'SOURCE_CHANGED', message: 'Original changed' } })
    await screen.findByText('Original changed')
    expect(createImageViewport).not.toHaveBeenCalled()
  })

  it('allows array and slice selection without changing group membership', async () => {
    const user = userEvent.setup()
    const view = setup(1)
    view.prepare.mockResolvedValueOnce({ ...image(), width: 0, height: 0, needs_selection: true, arrays: [{ key: 'science', shape: [2, 20, 30], dtype: 'float32', numeric: true }] })
    await screen.findByText('astrophotoflow.media.showSelection')
    await user.selectOptions(screen.getByLabelText('astrophotoflow.media.array'), 'science')
    await user.selectOptions(screen.getByLabelText('astrophotoflow.media.x_axis'), '2')
    await user.selectOptions(screen.getByLabelText('astrophotoflow.media.y_axis'), '1')
    await user.click(screen.getByRole('button', { name: 'astrophotoflow.media.showSelection' }))
    await waitFor(() => expect(view.prepare).toHaveBeenLastCalledWith('/frame/0', expect.objectContaining({ array_key: 'science', x_axis: 2, y_axis: 1 })))
    expect(view.request.total).toBe(1)
  })

  it('inspects the presented VFR timestamp and resumes the same video position', async () => {
    const user = userEvent.setup()
    const view = setup(1)
    view.prepare.mockResolvedValueOnce({ ...image('proxy'), kind: 'video', video_url: '/video/proxy', proxy: true, tile_url: null })
    const element = await screen.findByLabelText<HTMLVideoElement>('g.videoPreview')
    let frame: VideoFrameRequestCallback | undefined
    Object.defineProperty(element, 'requestVideoFrameCallback', { value: (callback: VideoFrameRequestCallback) => { frame = callback; return 1 } })
    Object.defineProperty(element, 'cancelVideoFrameCallback', { value: vi.fn() })
    await fireEvent.loadedMetadata(element)
    const presented = frame
    if (!presented) return expect.fail('Video did not subscribe to presented frames')
    presented(0, { mediaTime: .147, expectedDisplayTime: 0, presentationTime: 0, presentedFrames: 1, width: 1920, height: 1080, processingDuration: 0 })
    element.currentTime = .15
    await user.click(screen.getByRole('button', { name: 'astrophotoflow.media.inspectFrame' }))
    await waitFor(() => expect(view.prepare).toHaveBeenLastCalledWith('/frame/0', expect.objectContaining({ media_time: .147, playback_key: 'proxy' })))
    expect(view.request.total).toBe(1)
    await user.click(screen.getByRole('button', { name: 'astrophotoflow.media.backToVideo' }))
    expect(view.prepare.mock.calls.at(-1)?.[1].media_time).toBeUndefined()
  })

  it('shows the current thumbnail while queued, polls once per second and replaces it with the overview', async () => {
    vi.useFakeTimers()
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:current-thumbnail')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new Blob(['thumb']))))
    const view = setup(1)
    view.prepare.mockResolvedValueOnce({ ...image(), status: 'generating', phase: 'queued', overview_url: null, tile_url: null })
    view.status.mockResolvedValueOnce({ ...image(), status: 'generating', phase: 'preparing', overview_url: null, tile_url: null }).mockResolvedValueOnce(image())
    await vi.advanceTimersByTimeAsync(0)
    expect(screen.getByAltText('Frame 1').getAttribute('src')).toBe('blob:current-thumbnail')
    expect(screen.getByRole('status')).toHaveTextContent('astrophotoflow.media.queued')
    expect(createImageViewport).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(999)
    expect(view.status).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(view.status).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('status')).toHaveTextContent('astrophotoflow.media.preparing')
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(0)
    expect(screen.getByAltText('Frame 1').getAttribute('src')).toBe('/overview/first')
    expect(createImageViewport).toHaveBeenCalledOnce()
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:current-thumbnail')
  })

  it('stops polling and offers retry on a status request failure', async () => {
    vi.useFakeTimers()
    const view = setup(1)
    view.prepare.mockResolvedValueOnce({ ...image(), status: 'generating', phase: 'queued', overview_url: null, tile_url: null })
    view.status.mockRejectedValueOnce(new Error('Status request failed'))
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(1000)
    expect(screen.getByRole('alert')).toHaveTextContent('Status request failed')
    expect(screen.getByRole('button', { name: 'astrophotoflow.retryPreview' })).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(5000)
    expect(view.status).toHaveBeenCalledTimes(1)
    view.unmount()
  })


  it('moves and scales the overview with the viewport and discards bounds from the previous member', async () => {
    const user = userEvent.setup()
    const view = setup(2)
    await waitFor(() => expect(createImageViewport).toHaveBeenCalledOnce())
    const first = vi.mocked(createImageViewport).mock.calls[0]?.[2]
    if (!first) return expect.fail('Image viewport was not created')
    first.bounds({ left: 180, top: 120, width: 640, height: 480 })
    await nextTick()
    const overview = screen.getByAltText('Frame 1')
    expect(overview).toHaveStyle({ left: '180px', top: '120px', width: '640px', height: '480px' })
    expect(overview).not.toHaveClass('object-contain')
    view.viewport.zoomBy.mockImplementation(() => first.bounds({ left: 230, top: 160, width: 320, height: 240 }))
    await user.click(screen.getByRole('button', { name: 'astrophotoflow.media.zoomOut' }))
    expect(overview).toHaveStyle({ left: '230px', top: '160px', width: '320px', height: '240px' })
    first.bounds({ left: -100, top: -200, width: 1600, height: 1200 })
    await nextTick()
    expect(overview).toHaveStyle({ left: '-100px', top: '-200px', width: '1600px', height: '1200px' })
    expect(overview).toHaveClass('max-w-none')
    await user.click(screen.getByRole('button', { name: 'g.nextImage' }))
    await waitFor(() => expect(createImageViewport).toHaveBeenCalledTimes(2))
    first.bounds({ left: 999, top: 999, width: 999, height: 999 })
    await nextTick()
    const current = screen.getByAltText('Frame 2')
    expect(current).toHaveClass('object-contain')
    expect(current).not.toHaveStyle({ left: '999px' })
    view.unmount()
  })

})
