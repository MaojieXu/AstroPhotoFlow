import { fromPartial } from '@total-typescript/shoehorn'
import { nextTick } from 'vue'
import { render, screen, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import {
  mediaStateSchema,
  dataResultSchema,
  PlatformQueryPlugin
} from '@astrophotoflow/ui'
import type { ComponentWidget } from '@/scripts/domWidget'
import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import DataRunWidget from './DataRunWidget.vue'
vi.mock('../useNativeWorkspace')
import { nativeWorkspace } from '../__mocks__/useNativeWorkspace'

const state = vi.hoisted(() => ({
  output: undefined as unknown,
  graph: undefined as unknown,
  handlers: new Map<string, (event: unknown) => void>(),
  prepare: vi.fn(),
  result: vi.fn(),
  release: vi.fn()
}))
vi.mock('@/stores/nodeOutputStore', () => ({
  useNodeOutputStore: () => ({ getNodeOutputs: () => state.output })
}))
vi.mock('@/scripts/appInstance', () => ({
  useApp: () => ({ rootGraph: state.graph, graph: state.graph })
}))
vi.mock('@/scripts/api', () => ({
  api: {
    addEventListener: (name: string, fn: (event: unknown) => void) =>
      state.handlers.set(name, fn),
    removeEventListener: (name: string) => state.handlers.delete(name)
  }
}))
vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key })
}))
vi.mock(import('@astrophotoflow/ui'), async (original) => ({
  ...(await original()),
  createMediaClient: () => ({
    prepare: state.prepare,
    status: state.prepare,
    release: state.release,
    image: vi.fn()
  }),
  createDataExportClient: () => ({ result: state.result, submit: vi.fn(), status: vi.fn(), cancel: vi.fn(), choose: vi.fn() })
}))
vi.mock('../media/MediaViewer.vue', () => ({ default: { template: '<div />' } }))
vi.mock('./DataExportDialog.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/renderer/extensions/vueNodes/components/ImagePreview.vue', () => ({
  default: { template: '<img alt="complete result" />' }
}))

const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
function setup() {
  const graph = new LGraph()
  graph.id = id(1)
  state.graph = graph
  const node = new LGraphNode('Data')
  node.comfyClass = 'APF_DATA_REFERENCE'
  node.addWidget('text', 'reference', '', () => {})
  graph.add(node)
  const result = {output:{kind:'run_output',run_id:id(2),execution_id:id(3),output_index:0},
    run_id: id(2),
    execution_id: id(3),
    node_id: String(node.id),
    workflow_id: graph.id,
    state: 'completed',
    error: null,
    reference: {
      kind: 'run_output',
      run_id: id(2),
      execution_id: '00000000-0000-4000-8000-000000000004',
      output_index: 0,
      member_index: 0
    },
    input_bindings: { images: ['10', 0] },
    members: [
      {
        name: 'Full FITS',
        view_base: '/result',
        selection: { hdu_index: 0 },
        format: 'fits',
        metadata: {},
        byte_size: 4096
      }
    ]
  }
  state.output = { apf_data: [result] }
  state.result.mockResolvedValue(dataResultSchema.parse(result))
  return {
    graph,
    node,
    result,
    widget: fromPartial<ComponentWidget<string | object>>({
      node,
      name: 'display',
      value: '',
      options: {}
    })
  }
}
beforeEach(() => {
  vi.clearAllMocks()
  state.handlers.clear()
  nativeWorkspace.workspaceId.value = '/test-workspace'
  nativeWorkspace.ready.value = true
  state.release.mockResolvedValue(undefined)
  state.prepare.mockResolvedValue(
    mediaStateSchema.parse({
      key: 'view',
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
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(null, { status: 204 }))
  )
})
afterEach(() => {
  vi.unstubAllGlobals()
})

it('uses the matching actual native result without writing the serialized reference', async () => {
  const { widget, node } = setup()
  const original = node.serialize().widgets_values
  render(DataRunWidget, {
    props: { widget, reference: '', bindings: { images: ['10', 0] } },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await nextTick()
  await waitFor(() => expect(screen.getByText('Full FITS')).toBeVisible())
  expect(
    screen.getByRole('button', {
      name: 'astrophotoflow.dataExport.saveLibrary'
    })
  ).toBeVisible()
  expect(node.serialize().widgets_values).toEqual(original)
  expect(state.result).toHaveBeenCalledWith(
    id(2),
    id(3),
    expect.any(AbortSignal)
  )
})

it('rejects a result for another connection instead of using the old local reference', async () => {
  const { widget } = setup()
  render(DataRunWidget, {
    props: {
      widget,
      reference: 'old local reference',
      bindings: { images: ['11', 0] }
    },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await nextTick()
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
  expect(
    screen.queryByRole('button', {
      name: 'astrophotoflow.dataExport.saveLibrary'
    })
  ).not.toBeInTheDocument()
  expect(state.prepare).not.toHaveBeenCalled()
})

it('does not display an old result as the result of a newly failed execution', async () => {
  const { widget } = setup()
  render(DataRunWidget, {
    props: { widget, reference: '', bindings: { images: ['10', 0] } },
    global: { plugins: [PlatformQueryPlugin] }
  })
  state.handlers.get('execution_start')?.({ detail: { prompt_id: id(9) } })
  state.handlers.get('execution_error')?.({
    detail: { prompt_id: id(9), exception_message: 'Upstream failed' }
  })
  await nextTick()
  expect(screen.getByText('Upstream failed')).toBeVisible()
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
})

it('rejects a backend result for another graph and never prepares its media', async () => {
  const { widget, result } = setup()
  state.result.mockResolvedValue({ ...result, workflow_id: id(99) })
  render(DataRunWidget, {
    props: { widget, reference: '', bindings: { images: ['10', 0] } },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await waitFor(() =>
    expect(
      screen.getByText('Data result does not match its native reference')
    ).toBeVisible()
  )
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
  expect(state.prepare).not.toHaveBeenCalled()
})
it('hides old native output on disconnect and verifies the result again in a new workspace', async () => {
  const { widget } = setup()
  render(DataRunWidget, {
    props: { widget, reference: '', bindings: { images: ['10', 0] } },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await waitFor(() => expect(screen.getByText('Full FITS')).toBeVisible())
  nativeWorkspace.workspaceId.value = undefined
  await nextTick()
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
  state.result.mockRejectedValue(new Error('Result absent in new workspace'))
  nativeWorkspace.workspaceId.value = '/another'
  await waitFor(() =>
    expect(screen.getByText('Result absent in new workspace')).toBeVisible()
  )
  expect(state.result).toHaveBeenCalledTimes(2)
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
})

it('shows an authoritative failed result reason without preparing a stale preview', async () => {
  const { widget, result } = setup()
  state.result.mockResolvedValue({ ...result, state: 'failed', error: 'Checked output unavailable' })
  render(DataRunWidget, { props: { widget, reference: '', bindings: { images: ['10', 0] } }, global: { plugins: [PlatformQueryPlugin] } })
  await waitFor(() => expect(screen.getByText('Checked output unavailable')).toBeVisible())
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
  expect(state.prepare).not.toHaveBeenCalled()
})
