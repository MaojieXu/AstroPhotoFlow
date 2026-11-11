import { fromPartial } from '@total-typescript/shoehorn'
import userEvent from '@testing-library/user-event'
import { fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CanvasInspect } from '@astrophotoflow/ui'
import { mediaStateSchema, PlatformQueryPlugin } from '@astrophotoflow/ui'
import {
  LGraph,
  LGraphNode,
  LGraphEventMode
} from '@/lib/litegraph/src/litegraph'
import { api as nativeApi } from '@/scripts/api'
import type { ComponentWidget } from '@/scripts/domWidget'

import CanvasDataWidget from './CanvasDataWidget.vue'
vi.mock('../useNativeWorkspace')
import { nativeWorkspace } from '../__mocks__/useNativeWorkspace'

const graphState = vi.hoisted(() => ({ root: undefined as unknown }))
const api = vi.hoisted(() => ({
  importSubmit: vi.fn(),
  importGet: vi.fn(),
  select: vi.fn(),
  mediaRelease: vi.fn(),
  prepare: vi.fn(),
  inspect: vi.fn(),
  mediaImage: vi.fn(),
  display: vi.fn(),
  displayStatus: vi.fn(),
  mediaPrepare: vi.fn(),
  mediaStatus: vi.fn()
}))
vi.mock('@/scripts/appInstance', () => ({
  useApp: () => ({
    rootGraph: graphState.root,
    canvas: {
      emitBeforeChange: vi.fn(),
      emitAfterChange: vi.fn(),
      setDirty: vi.fn()
    }
  })
}))
vi.mock('../results/DataRunWidget.vue', async () => {
  const { defineComponent } = await import('vue')
  return {
    default: defineComponent({
      props: { bindings: { type: Object, required: true } },
      template:
        '<output data-testid="data-bindings">{{ JSON.stringify(bindings) }}</output>'
    })
  }
})
vi.mock('@/stores/nodeOutputStore', () => ({
  useNodeOutputStore: () => ({ getNodeOutputs: () => undefined })
}))
vi.mock(import('@astrophotoflow/ui'), async (original) => ({
  ...(await original()),
  createCanvasDataClient: () => api,
  createImportClient: () => ({
    request: vi.fn(),
    recoverOrganization: vi.fn(),
    submit: api.importSubmit,
    get: api.importGet,
    list: vi.fn(),
    select: api.select,
    resume: vi.fn(),
    retry: vi.fn()
  }),
  createMediaClient: () => ({
    prepare: api.mediaPrepare,
    status: api.mediaStatus,
    release: api.mediaRelease,
    image: api.mediaImage
  })
}))
vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key })
}))
vi.mock(
  '@/renderer/extensions/vueNodes/components/ImagePreview.vue',
  async () => {
    const { defineComponent } = await import('vue')
    return {
      default: defineComponent({
        props: ['imageUrls'],
        emits: ['load-error'],
        template:
          '<img :src="imageUrls[0]" alt="Scientific preview" @error="$emit(\'load-error\')" />'
      })
    }
  }
)

const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const reference = {
  kind: 'dataset',
  dataset_id: id(1),
  asset_ids: [id(10), id(11)],
  selection: { kind: 'whole_file' }
}

function item(index: number): CanvasInspect {
  return {
    title: 'Night',
    member_count: 2,
    member_index: index,
    asset_id: id(index + 10),
    view_base: `/astrophotoflow/api/v1/library/assets/${id(index + 10)}/previews`,
    name: `Frame ${index + 1}`,
    availability: 'available',
    parameters: {
      parameter_mode: 'gain',
      gain: 0,
      offset: 0,
      exposure_seconds: index ? 180 : 0,
      sensor_temperature_c: 0
    },
    equipment: { camera: 'Camera', filter: index ? 'R' : 'L' },
    format: 'fits',
    width: 6000,
    height: 4000,
    bitpix: -32,
    pixel_type: 'float32',
    preview_status: 'available',
    preview_url: `/preview/${index}`,
    preview_error: null
  }
}

function mountWidget() {
  const node = new LGraphNode('Night')
  node.serialize_widgets = true
  const value = JSON.stringify(reference)
  const control = node.addWidget('text', 'reference', value, () => {})
  const widget = fromPartial<ComponentWidget<string | object>>({
    node,
    name: 'display',
    value: '',
    options: {}
  })
  const graph = new LGraph()
  graph.add(node)
  graphState.root = graph
  const view = render(CanvasDataWidget, {
    props: { widget },
    global: { plugins: [PlatformQueryPlugin] }
  })
  return { ...view, node, control, value }
}

beforeEach(() => {
  vi.clearAllMocks()
  nativeWorkspace.workspaceId.value = '/test-workspace'
  nativeWorkspace.ready.value = true
  api.mediaRelease.mockResolvedValue(undefined)
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 204 }))
  )
  api.inspect.mockImplementation(async (reference, index: number) => ({
    ...item(index),
    asset_id:
      reference.kind === 'asset'
        ? reference.asset_id
        : item(index).asset_id
  }))
  api.mediaImage.mockResolvedValue(new Blob(['preview']))
  api.display.mockResolvedValue({ status: 'available' })
  api.mediaPrepare.mockImplementation(async (base: string) =>
    mediaStateSchema.parse({
      key: 'view',
      status: 'available',
      phase: null,
      kind: 'image',
      width: 6000,
      height: 4000,
      max_level: 13,
      tile_size: 512,
      selection: {},
      arrays: [],
      hdus: [],
      display_recipe: null,
      needs_selection: false,
      overview_url: base + '/viewer/view/overview',
      tile_url: '/tiles/{level}/{x}/{y}',
      video_url: null,
      mime_type: null,
      proxy: false,
      frame_index: null,
      media_time: null,
      frame_count: null,
      duration: null,
      note: null,
      error: null
    })
  )
  const OriginalUrl = URL
  vi.stubGlobal(
    'URL',
    class extends OriginalUrl {
      static override createObjectURL() {
        return 'blob:scientific-preview'
      }
      static override revokeObjectURL() {}
    }
  )
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('scientific image component widget', () => {
  it('opens the shared chooser, imports its actual path and preserves an authored title', async () => {
    const prepared = { native_type: 'APF_DATA_REFERENCE', title: 'Selected file',
      reference: { kind: 'asset', asset_id: id(49), selection: { kind: 'whole_file' } } }
    api.select.mockResolvedValue({ cancelled: false, files: [{ path: 'C:/Images/selected.fit', name: 'selected.fit', size: 4096 }] })
    api.prepare.mockResolvedValue(prepared)
    api.importSubmit.mockResolvedValue({ task_id: id(90), status: 'queued' })
    api.importGet.mockResolvedValue({ id: id(90), status: 'running', items_total: 1,
      items: [{ content_status: 'available', asset_id: id(49) }] })
    const { node, control } = mountWidget()
    node.title = 'My authored title'
    await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.nodeUi.replaceFile' }))
    await waitFor(() => expect(control.value).toBe(JSON.stringify(prepared.reference)))
    expect(api.select).toHaveBeenCalledWith({ mode: 'files' }, expect.any(AbortSignal))
    expect(api.importSubmit).toHaveBeenCalledWith({ sources: [{ path: 'C:/Images/selected.fit' }], storage_mode: 'managed' }, expect.any(AbortSignal))
    expect(node.title).toBe('My authored title')
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('retains its binding when the chooser is cancelled or returns after a graph edit', async () => {
    const { control, value } = mountWidget()
    api.select.mockResolvedValueOnce({ cancelled: true, files: [] })
    await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.nodeUi.replaceFile' }))
    await waitFor(() => expect(api.select).toHaveBeenCalledTimes(1))
    expect(control.value).toBe(value)
    let finish!: (value: unknown) => void
    api.select.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.nodeUi.replaceFile' }))
    control.value = JSON.stringify({ kind: 'asset', asset_id: id(3), selection: { kind: 'whole_file' } })
    nativeApi.dispatchCustomEvent('graphChanged', null)
    finish({ cancelled: false, files: [{ path: 'C:/late.fit' }] })
    await screen.findByText('astrophotoflow.canvasChanged')
    expect(api.importSubmit).not.toHaveBeenCalled()
  })

  it('imports an image path into the current node as a fixed reference', async () => {
    const prepared = {
      native_type: 'APF_DATA_REFERENCE',
      title: 'Imported image',
      reference: {
        kind: 'asset',
        asset_id: id(49),
        selection: { kind: 'whole_file' }
      }
    }
    api.prepare.mockResolvedValue(prepared)
    api.importSubmit.mockResolvedValue({ task_id: id(90), status: 'queued' })
    api.importGet.mockResolvedValue({
      id: id(90),
      status: 'running',
      items_total: 1,
      items: [
        {
          content_status: 'available',
          asset_id: id(49)
        }
      ]
    })
    const { node, control } = mountWidget()
    await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.nodeUi.manualPath' }))
    await fireEvent.update(
      screen.getByRole('textbox', { name: 'astrophotoflow.imagePath' }),
      'C:/Images/source.fit'
    )
    await fireEvent.click(
      screen.getByRole('button', { name: 'astrophotoflow.importImage' })
    )
    await waitFor(() =>
      expect(control.value).toBe(JSON.stringify(prepared.reference))
    )
    expect(api.importSubmit).toHaveBeenCalledWith(
      { sources: [{ path: 'C:/Images/source.fit' }], storage_mode: 'managed' },
      expect.any(AbortSignal)
    )
    expect(node.title).toBe('Imported image')
  })

  it('loads only the current member, shows zero and updates metadata while leaving the reference untouched', async () => {
    const user = userEvent.setup()
    const { node, value } = mountWidget()
    await screen.findByAltText('Frame 1')
    expect(api.inspect).toHaveBeenCalledTimes(1)
    await waitFor(() =>
      expect(api.mediaImage).toHaveBeenCalledWith(
        expect.stringContaining('/viewer/view/overview'),
        expect.any(AbortSignal)
      )
    )
    expect(screen.getByText(/0 s/)).toBeInTheDocument()
    expect(screen.getByText(/6000 × 4000/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'g.nextImage' }))
    await screen.findByText('Frame 2')
    expect(screen.getByText(/180 s/)).toBeInTheDocument()
    await waitFor(() =>
      expect(api.mediaImage).toHaveBeenCalledWith(
        expect.stringContaining('/' + id(11) + '/previews/viewer/view/overview'),
        expect.any(AbortSignal)
      )
    )
    await user.click(
      screen.getByRole('button', { name: 'astrophotoflow.imageDetails' })
    )
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Camera')).toBeInTheDocument()
    expect(screen.getByText('Offset')).toBeInTheDocument()
    expect(screen.getByText('0 °C')).toBeInTheDocument()
    expect(node.serialize().widgets_values).toEqual([value])
  })

  it('ignores a late response after the fixed reference changes', async () => {
    let first: ((value: CanvasInspect) => void) | undefined
    api.inspect.mockImplementationOnce(
      () =>
        new Promise<CanvasInspect>((resolve) => {
          first = resolve
        })
    )
    const { control } = mountWidget()
    await waitFor(() => expect(api.inspect).toHaveBeenCalledTimes(1))
    control.value = JSON.stringify({
      kind: 'asset',
      asset_id: id(3),
      selection: { kind: 'whole_file' }
    })
    api.inspect.mockResolvedValueOnce({ ...item(1), asset_id: id(3), member_count: 1, member_index: 0 })
    nativeApi.dispatchCustomEvent('graphChanged', null)
    await screen.findByAltText('Frame 2')
    first?.(item(0))
    await waitFor(() =>
      expect(screen.queryByAltText('Frame 1')).not.toBeInTheDocument()
    )
    expect(api.mediaImage).not.toHaveBeenCalledWith(
      '/preview/0',
      expect.any(AbortSignal)
    )
  })

  it('retains the fixed scientific reference when retrying the high resolution overview', async () => {
    const user = userEvent.setup()
    const { node, value } = mountWidget()
    const image = await screen.findByAltText('Frame 1')
    await fireEvent.error(image)
    expect(
      await screen.findByText('astrophotoflow.previewUnavailable')
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: 'astrophotoflow.retryPreview' })
    )
    await waitFor(() => expect(api.mediaPrepare).toHaveBeenCalledTimes(2))
    await screen.findByAltText('Frame 1')
    expect(node.serialize().widgets_values).toEqual([value])
  })

  it('shows unknown values without inventing dimensions from the thumbnail', async () => {
    api.inspect.mockResolvedValue({
      ...item(0),
      availability: 'missing',
      width: null,
      height: null,
      parameters: {},
      equipment: {},
      preview_status: 'not_ready',
      preview_url: null
    })
    mountWidget()
    await screen.findByText('Frame 1')
    await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.imageDetails' }))
    expect(
      screen.getAllByText('astrophotoflow.unspecified').length
    ).toBeGreaterThan(0)
    expect(screen.queryByText('6000 × 4000')).not.toBeInTheDocument()
    expect(api.display).not.toHaveBeenCalled()
    expect(api.mediaPrepare).not.toHaveBeenCalled()
  })

  it('keeps the thumbnail visible while high resolution is queued and preserves the scientific reference', async () => {
    vi.useFakeTimers()
    const state = mediaStateSchema.parse({
      key: 'queued',
      status: 'generating',
      phase: 'queued',
      kind: 'image',
      width: 0,
      height: 0,
      max_level: 0,
      tile_size: 512,
      selection: {},
      arrays: [],
      hdus: [],
      display_recipe: null,
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
      error: null
    })
    api.mediaPrepare.mockResolvedValueOnce(state)
    let finishStatus!: (value: typeof state) => void
    api.mediaStatus.mockImplementationOnce(() => new Promise(resolve => { finishStatus = resolve }))
    const available = {
      ...state,
      status: 'available' as const,
      phase: null,
      width: 6000,
      height: 4000,
      overview_url: '/high-resolution'
    }
    const { node, value, unmount } = mountWidget()
    await vi.advanceTimersByTimeAsync(0)
    expect(screen.getByAltText('Frame 1')).toBeInTheDocument()
    expect(
      screen
        .getAllByRole('status')
        .some((element) =>
          element.textContent?.includes('astrophotoflow.media.queued')
        )
    ).toBe(true)
    await vi.advanceTimersByTimeAsync(1000)
    expect(api.mediaStatus).toHaveBeenCalledTimes(1)
    expect(screen.getByAltText('Frame 1')).toBeInTheDocument()
    finishStatus(available)
    await vi.advanceTimersByTimeAsync(0)
    expect(api.mediaImage).toHaveBeenCalledWith(
      '/high-resolution',
      expect.any(AbortSignal)
    )
    expect(
      screen.queryByText('astrophotoflow.media.queued')
    ).not.toBeInTheDocument()
    expect(node.serialize().widgets_values).toEqual([value])
    unmount()
    expect(api.mediaRelease).toHaveBeenCalledWith(
      expect.stringContaining('/previews'),
      expect.any(String)
    )
  })
})

it('matches native resolved IMAGE bindings through bypass and hides results after rewiring', async () => {
  const graph = new LGraph()
  graphState.root = graph
  const source = new LGraphNode('Source')
  source.addOutput('IMAGE', 'IMAGE')
  const bypass = new LGraphNode('Bypass')
  bypass.addInput('images', 'IMAGE')
  bypass.addOutput('IMAGE', 'IMAGE')
  bypass.mode = LGraphEventMode.BYPASS
  const data = new LGraphNode('Data')
  data.comfyClass = 'APF_DATA_REFERENCE'
  data.addInput('images', 'IMAGE')
  for (const node of [source, bypass, data]) graph.add(node)
  source.connect(0, bypass, 0)
  bypass.connect(0, data, 0)
  const before = graph.serialize()
  const widget = fromPartial<ComponentWidget<string | object>>({
    node: data,
    name: 'display',
    value: '',
    options: {}
  })
  const view = render(CanvasDataWidget, {
    props: { widget },
    global: { plugins: [PlatformQueryPlugin] }
  })
  expect(
    JSON.parse(screen.getByTestId('data-bindings').textContent ?? '{}')
  ).toEqual({ images: [String(source.id), 0] })
  expect(graph.serialize()).toEqual(before)
  bypass.mode = LGraphEventMode.ALWAYS
  nativeApi.dispatchCustomEvent('graphChanged', null)
  await waitFor(() =>
    expect(
      JSON.parse(screen.getByTestId('data-bindings').textContent ?? '{}')
    ).toEqual({ images: [String(bypass.id), 0] })
  )
  expect(
    JSON.parse(screen.getByTestId('data-bindings').textContent ?? '{}')
  ).toEqual({ images: [String(bypass.id), 0] })
  view.unmount()
})

it('does not replace a reference edited while its import was being observed', async () => {
  let finish!: (value: unknown) => void
  api.importSubmit.mockResolvedValue({ task_id: id(90), status: 'queued' })
  api.importGet.mockImplementation(() => new Promise((done) => (finish = done)))
  api.prepare.mockResolvedValue({
    native_type: 'APF_DATA_REFERENCE',
    title: 'Imported',
    reference: {
      kind: 'asset',
      asset_id: id(49),
      selection: { kind: 'whole_file' }
    }
  })
  const { control, node } = mountWidget()
  await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.nodeUi.manualPath' }))
  await fireEvent.update(
    screen.getByRole('textbox', { name: 'astrophotoflow.imagePath' }),
    'C:/Images/new.fit'
  )
  await fireEvent.click(
    screen.getByRole('button', { name: 'astrophotoflow.importImage' })
  )
  await waitFor(() => expect(api.importGet).toHaveBeenCalledTimes(1))
  const changed = JSON.stringify({
    kind: 'asset',
    asset_id: id(3),
    selection: { kind: 'whole_file' }
  })
  control.value = changed
  nativeApi.dispatchCustomEvent('graphChanged', null)
  finish({
    id: id(90),
    status: 'running',
    items_total: 1,
    items: [
      {
        content_status: 'available',
        asset_id: id(49)
      }
    ]
  })
  await waitFor(() =>
    expect(screen.getByText('astrophotoflow.canvasChanged')).toBeVisible()
  )
  expect(control.value).toBe(changed)
  expect(node.title).not.toBe('Imported')
})
it('rejects mismatched inspected members and never prepares their preview', async () => {
  api.inspect.mockResolvedValue({ ...item(0), asset_id: id(99) })
  mountWidget()
  await screen.findByText('Canvas metadata does not match its selected member')
  expect(api.mediaPrepare).not.toHaveBeenCalled()
})

it('reports a missing cached thumbnail when the scientific original is unavailable',async()=>{
 api.inspect.mockResolvedValue({...item(0),availability:'missing'})
 api.mediaImage.mockRejectedValue(new Error('Thumbnail removed'))
 mountWidget()
 await screen.findByText('Thumbnail removed')
 expect(api.mediaPrepare).not.toHaveBeenCalled()
 expect(screen.queryByAltText('Scientific preview')).not.toBeInTheDocument()
})
