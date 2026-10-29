import { fromPartial } from '@total-typescript/shoehorn'
import userEvent from '@testing-library/user-event'
import { fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CanvasInspect } from '@astrophotoflow/ui'
import { mediaStateSchema } from '@astrophotoflow/ui'
import { LGraphNode } from '@/lib/litegraph/src/litegraph'
import { api as nativeApi } from '@/scripts/api'
import type { ComponentWidget } from '@/scripts/domWidget'

import CanvasDataWidget from './CanvasDataWidget.vue'

const api = vi.hoisted(() => ({ prepare: vi.fn(), inspect: vi.fn(), getBlob: vi.fn(), display: vi.fn(), displayStatus: vi.fn(), mediaPrepare: vi.fn(), mediaStatus: vi.fn() }))
vi.mock(import('@astrophotoflow/ui'), async original => ({ ...await original(), createCanvasDataClient: () => api, createMediaClient: () => ({ prepare: api.mediaPrepare, status: api.mediaStatus }) }))
vi.mock('vue-i18n', async original => ({ ...await original<typeof import('vue-i18n')>(), useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/renderer/extensions/vueNodes/components/ImagePreview.vue', async () => {
  const { defineComponent } = await import('vue')
  return { default: defineComponent({ props: ['imageUrls'], emits: ['load-error'], template: '<img :src="imageUrls[0]" alt="Scientific preview" @error="$emit(\'load-error\')" />' }) }
})

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const reference = { kind: 'dataset_version', dataset_version_id: id(1), members: [2, 3].map((n, index) => ({ member_index: index, asset_version_id: id(n), selection: { kind: 'whole_file' } })) }

function item(index: number): CanvasInspect {
  return {
    title: 'Night', total: 2, member_index: index, asset_id: id(index + 10), asset_version_id: id(index + 2), name: `Frame ${index + 1}`,
    availability: 'available', parameters: { parameter_mode: 'gain', gain: 0, offset: 0, exposure_seconds: index ? 180 : 0, sensor_temperature_c: 0 },
    equipment: { camera: 'Camera', filter: index ? 'R' : 'L' }, format: 'fits', width: 6000, height: 4000, bitpix: -32, pixel_type: 'float32',
    preview_status: 'available', preview_url: `/preview/${index}`, preview_error: null
  }
}

function mountWidget() {
  const node = new LGraphNode('Night')
  node.serialize_widgets = true
  const value = JSON.stringify(reference)
  const control = node.addWidget('text', 'reference', value, () => {})
  const widget = fromPartial<ComponentWidget<string | object>>({ node, name: 'display', value: '', options: {} })
  const view = render(CanvasDataWidget, { props: { widget } })
  return { ...view, node, control, value }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
  api.inspect.mockImplementation(async (_reference, index: number) => item(index))
  api.getBlob.mockResolvedValue(new Blob(['preview']))
  api.display.mockResolvedValue({ status: 'available' })
  api.mediaPrepare.mockImplementation(async (base: string) => mediaStateSchema.parse({
    key: 'view', status: 'available', kind: 'image', width: 6000, height: 4000, max_level: 13, tile_size: 512,
    selection: {}, arrays: [], needs_selection: false, overview_url: base + '/viewer/view/overview', tile_url: '/tiles/{level}/{x}/{y}',
    video_url: null, mime_type: null, proxy: false, frame_index: null, media_time: null, frame_count: null, duration: null, note: null, error: null
  }))
  const OriginalUrl = URL
  vi.stubGlobal('URL', class extends OriginalUrl {
    static override createObjectURL() { return 'blob:scientific-preview' }
    static override revokeObjectURL() {}
  })
})

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })

describe('scientific image component widget', () => {
  it('loads only the current member, shows zero and updates metadata while leaving the reference untouched', async () => {
    const user = userEvent.setup()
    const { node, value } = mountWidget()
    await screen.findByAltText('Scientific preview')
    expect(api.inspect).toHaveBeenCalledTimes(1)
    expect(api.getBlob).toHaveBeenCalledWith(expect.stringContaining('/viewer/view/overview'))
    expect(screen.getByText('0 s')).toBeInTheDocument()
    expect(screen.getByText('0 °C')).toBeInTheDocument()
    expect(screen.getByText('6000 × 4000')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'g.nextImage' }))
    await screen.findByText('Frame 2')
    expect(screen.getByText('180 s')).toBeInTheDocument()
    expect(api.getBlob).toHaveBeenLastCalledWith(expect.stringContaining('/' + id(3) + '/previews/viewer/view/overview'))
    await user.click(screen.getByRole('button', { name: 'astrophotoflow.imageDetails' }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Camera')).toBeInTheDocument()
    expect(screen.getByText('Offset')).toBeInTheDocument()
    expect(node.serialize().widgets_values).toEqual([value])
  })

  it('ignores a late response after the fixed reference changes', async () => {
    let first: ((value: CanvasInspect) => void) | undefined
    api.inspect.mockImplementationOnce(() => new Promise<CanvasInspect>(resolve => { first = resolve }))
    const { control } = mountWidget()
    await waitFor(() => expect(api.inspect).toHaveBeenCalledTimes(1))
    control.value = JSON.stringify({ kind: 'asset_version', asset_version_id: id(3), selection: { kind: 'whole_file' } })
    api.inspect.mockResolvedValueOnce({ ...item(1), total: 1, member_index: 0 })
    nativeApi.dispatchCustomEvent('graphChanged', null)
    await screen.findByText('Frame 2')
    first?.(item(0))
    await waitFor(() => expect(screen.queryByText('Frame 1')).not.toBeInTheDocument())
    expect(api.getBlob).not.toHaveBeenCalledWith('/preview/0')
  })

  it('retains the fixed scientific reference when retrying the high resolution overview', async () => {
    const user = userEvent.setup()
    const { node, value } = mountWidget()
    const image = await screen.findByAltText('Scientific preview')
    await fireEvent.error(image)
    expect(await screen.findByText('astrophotoflow.previewUnavailable')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'astrophotoflow.retryPreview' }))
    await waitFor(() => expect(api.mediaPrepare).toHaveBeenCalledTimes(2))
    await screen.findByAltText('Scientific preview')
    expect(node.serialize().widgets_values).toEqual([value])
  })

  it('shows unknown values without inventing dimensions from the thumbnail', async () => {
    api.inspect.mockResolvedValue({ ...item(0), availability: 'missing', width: null, height: null, parameters: {}, equipment: {}, preview_status: 'not_ready', preview_url: null })
    mountWidget()
    await screen.findByText('Frame 1')
    expect(screen.getAllByText('astrophotoflow.unspecified').length).toBeGreaterThan(0)
    expect(screen.queryByText('6000 × 4000')).not.toBeInTheDocument()
    expect(api.display).not.toHaveBeenCalled()
    expect(api.mediaPrepare).not.toHaveBeenCalled()
  })

  it('keeps the thumbnail visible while high resolution is queued and preserves the scientific reference', async () => {
    vi.useFakeTimers()
    const state = mediaStateSchema.parse({
      key: 'queued', status: 'generating', phase: 'queued', kind: 'image', width: 0, height: 0, max_level: 0, tile_size: 512,
      selection: {}, arrays: [], needs_selection: false, overview_url: null, tile_url: null,
      video_url: null, mime_type: null, proxy: false, frame_index: null, media_time: null, frame_count: null, duration: null, note: null, error: null
    })
    api.mediaPrepare.mockResolvedValueOnce(state)
    api.mediaStatus.mockResolvedValueOnce({ ...state, status: 'available', phase: null, width: 6000, height: 4000, overview_url: '/high-resolution' })
    const { node, value, unmount } = mountWidget()
    await vi.advanceTimersByTimeAsync(0)
    expect(screen.getByAltText('Scientific preview')).toBeInTheDocument()
    expect(screen.getAllByRole('status').some(element => element.textContent?.includes('astrophotoflow.media.queued'))).toBe(true)
    await vi.advanceTimersByTimeAsync(999)
    expect(api.mediaStatus).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    await vi.advanceTimersByTimeAsync(0)
    expect(api.getBlob).toHaveBeenCalledWith('/high-resolution')
    expect(screen.queryByText('astrophotoflow.media.queued')).not.toBeInTheDocument()
    expect(node.serialize().widgets_values).toEqual([value])
    unmount()
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/viewer/consumer/'), expect.objectContaining({ method: 'DELETE' }))
  })

})
