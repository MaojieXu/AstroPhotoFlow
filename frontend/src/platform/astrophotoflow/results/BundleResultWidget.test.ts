import { fromPartial } from '@total-typescript/shoehorn'
import userEvent from '@testing-library/user-event'
import { fireEvent, render, screen, waitFor } from '@testing-library/vue'
import { ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import { executionIdToNodeLocatorId, getExecutionIdByNode } from '@/utils/graphTraversalUtil'
import type { ComponentWidget } from '@/scripts/domWidget'

import BundleResultWidget from './BundleResultWidget.vue'
import type {
  AnalysisResult,
  MediaSelection,
  MediaViewerRequest,
  NodeCapability,
  NodeParameter,
  SoftwareCallResult
} from '@astrophotoflow/ui'
import { PlatformQueryPlugin } from '@astrophotoflow/ui'
import { bundleCapabilities } from '../sidebar/bundleCatalog'
vi.mock('../useNativeWorkspace')
import { nativeWorkspace } from '../__mocks__/useNativeWorkspace'
afterEach(() => {
  nativeWorkspace.workspaceId.value = '/test-workspace'
  nativeWorkspace.ready.value = true
  bundleCapabilities.clear()
  f.failure.mockReset()
})

const f = vi.hoisted(() => ({
  result: vi.fn(),
  state: vi.fn(),
  get: vi.fn(),
  analysis: vi.fn(),
  open: vi.fn(),
  graph: vi.fn(),
  failure: vi.fn()
}))
vi.mock('@astrophotoflow/ui', async (original) => {
  const { defineComponent, h } = await import('vue')
  return {
    ...(await original<typeof import('@astrophotoflow/ui')>()),
    createRunResultClient: () => ({ get: f.get, analysis: f.analysis }),
    useCanvasInspection: () => ({
      data: ref({
        availability: 'available',
        view_base: '/fixed/input',
        content_hash: 'fixture-input'
      }),
      error: ref()
    }),
    BundleGeometryEditor: defineComponent({
      emits: ['edit'],
      setup(_, { emit }) {
        return () =>
          h(
            'button',
            { onClick: () => emit('edit', [[120, 60]]) },
            'Place sample'
          )
      }
    })
  }
})
vi.mock('@/scripts/appInstance', () => ({ useApp: f.graph }))
vi.mock('@/utils/litegraphUtil', async (original) => ({
  ...(await original<typeof import('@/utils/litegraphUtil')>()),
  isSelectOnly: () => false
}))
vi.mock('../media/MediaImagePreview.vue', async () => {
  const { defineComponent, h, onMounted } = await import('vue')
  return {
    default: defineComponent({
      props: ['base', 'title', 'selection'],
      emits: ['media', 'open'],
      setup(props, { emit, slots }) {
        const state = {
          width: 2000,
          height: 1000,
          channels: ['composite', 'red', 'green', 'blue'],
          frame_count: 4,
          selection: { hdu_index: 0 },
          frame_index: 0
        }
        onMounted(() => emit('media', state))
        return () =>
          slots.image?.({ image: 'blob:fixture', state }) ??
          h(
            'button',
            {
              'data-testid': 'fixture-media',
              'data-base': props.base,
              'data-frame': props.selection.frame_index,
              'data-channel': props.selection.channel,
              onClick: () => emit('open', props.selection)
            },
            props.title
          )
      }
    })
  }
})
vi.mock('../media/MediaViewer.vue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    default: defineComponent({
      props: ['request'],
      setup(props) {
        f.open(props.request)
        return () => h('div', { role: 'dialog' })
      }
    })
  }
})
vi.mock('@/stores/nodeOutputStore', () => ({
  useNodeOutputStore: () => ({ getNodeOutputs: f.result })
}))
vi.mock('@/stores/executionStore', () => ({
  useExecutionStore: () => ({ activeJobId: null })
}))
vi.mock('@/stores/executionErrorStore', () => ({
  useExecutionErrorStore: () => f.failure() ?? ({ lastExecutionErrorNodeLocatorId: null })
}))
vi.mock('@/platform/settings/settingStore', () => ({
  useSettingStore: () => ({ get: () => 1024 })
}))
vi.mock('./automatic', () => ({
  automaticResultState: f.state,
  setAutomaticResult: vi.fn(),
  retryAutomaticResult: vi.fn()
}))
vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key, locale: ref('en') })
}))

describe('complete result ownership', () => {
  it.each([
    ['SoftwareCallBlocked', 'blocked'],
    ['SoftwareCallUnknown', 'unknown']
  ])('shows %s distinctly and prevents automatic replay', async (type, status) => {
    const graph = new LGraph()
    const node = new LGraphNode('Process')
    graph.add(node)
    f.failure.mockReturnValue({
      lastExecutionErrorNodeLocatorId: executionIdToNodeLocatorId(graph, getExecutionIdByNode(graph, node)!),
      lastExecutionError: { exception_type: 'astrophotoflow.interfaces.native.replies.' + type,
        exception_message: 'Inspect the original call' }
    })
    f.result.mockReturnValue(undefined)
    f.graph.mockReturnValue({ rootGraph: graph })
    f.state.mockReturnValue({ phase: 'failed', error: 'Inspect the original call', signature: 'fixture' })
    const view = render(BundleResultWidget, {
      props: { widget: fromPartial<ComponentWidget<string | object>>({ node }) },
      global: { plugins: [PlatformQueryPlugin] }
    })
    expect(await screen.findByRole('status')).toHaveTextContent('astrophotoflow.bundle.' + status)
    expect(screen.queryByRole('button', { name: 'g.retry' })).not.toBeInTheDocument()
    view.unmount()
  })
  it('retains the old result as stale and rejects other workflows and late signatures', async () => {
    const graph = new LGraph()
    const node = new LGraphNode('Process')
    graph.add(node)
    const automatic = ref({
      signature: 'old',
      submitted: 'old',
      phase: 'completed'
    })
    const result = (
      prompt: string,
      signature: string,
      workflow = graph.id
    ): SoftwareCallResult => ({
      log_url: `/astrophotoflow/api/v1/runs/${prompt}/calls/${'00000000-0000-4000-8000-000000000004'}/log`,
      prompt_id: prompt,
      call_id: '00000000-0000-4000-8000-000000000004',
      node_id: String(node.id),
      workflow_id: workflow,
      state: 'completed',
      calculation_signature: signature,
      ports: [],
      package_id: null,
      software_version: null,
      bundle_version: null,
      bundle_commit: null,
      development_source: null,
      operation_id: null,
      definition_token: null,
      preview_error: null,
      observation: null,
      error: null
    })
    f.get.mockImplementation(async (identity: { prompt_id: string }) => ({
      ...result(
        identity.prompt_id,
        identity.prompt_id === oldId ? 'old' : 'new'
      )
    }))
    const oldId = '11111111-1111-4111-8111-111111111111'
    const newId = '22222222-2222-4222-8222-222222222222'
    const output = ref({ apf_result: [result(oldId, 'old')] })
    f.result.mockImplementation(() => output.value)
    f.state.mockImplementation(() => automatic.value)
    const view = render(BundleResultWidget, {
      props: {
        widget: fromPartial<ComponentWidget<string | object>>({ node })
      },
      global: { plugins: [PlatformQueryPlugin] }
    })
    await waitFor(() => expect(f.get).toHaveBeenCalled())
    await waitFor(() => expect(f.get).toHaveBeenCalledWith(expect.objectContaining({ prompt_id: oldId }), expect.any(AbortSignal)))
    expect(await currentLog(oldId)).toContain(oldId)
    automatic.value = { signature: 'new', submitted: 'new', phase: 'running' }
    await screen.findByText('astrophotoflow.bundle.previousResult')
    output.value = {
      apf_result: [result(newId, 'new', '33333333-3333-4333-8333-333333333333')]
    }
    await waitFor(() =>
      expect(f.get).not.toHaveBeenCalledWith(expect.objectContaining({ prompt_id: newId }), expect.any(AbortSignal))
    )
    output.value = { apf_result: [result(newId, 'new')] }
    await waitFor(() => expect(f.get).toHaveBeenCalledWith(expect.objectContaining({ prompt_id: newId }), expect.any(AbortSignal)))
    expect(await currentLog(newId)).toContain(newId)
    output.value = { apf_result: [result(oldId, 'old')] }
    await waitFor(() =>
      expect(f.get).toHaveBeenCalledTimes(2)
    )
    expect(await currentLog(newId)).toContain(newId)
    nativeWorkspace.workspaceId.value = undefined
    nativeWorkspace.ready.value = false
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'astrophotoflow.nodeUi.more' })).not.toBeInTheDocument()
    )
    nativeWorkspace.workspaceId.value = '/test-workspace'
    nativeWorkspace.ready.value = true
    expect(await currentLog(newId)).toContain(newId)
    view.unmount()
  })
})

async function currentLog(expected: string) {
  await fireEvent.click(await screen.findByRole('button', { name: 'astrophotoflow.nodeUi.more' }))
  const link = await screen.findByRole('menuitem', { name: 'astrophotoflow.results.log' })
  await waitFor(() => expect(link).toHaveAttribute('href', expect.stringContaining(expected)))
  const href = link.getAttribute('href')
  await fireEvent.keyDown(link, { key: 'Escape' })
  await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument())
  return href
}

it('uses the checked member and log URLs from the response without reconstructing routes', async () => {
  const graph = new LGraph(),
    node = new LGraphNode('File result')
  graph.add(node)
  const record: SoftwareCallResult = {
    prompt_id: '11111111-1111-4111-8111-111111111111',
    call_id: '22222222-2222-4222-8222-222222222222',
    node_id: String(node.id),
    workflow_id: graph.id,
    log_url: '/opaque/call-log',
    calculation_signature: 'fixed',
    package_id: 'siril',
    software_version: '1.4.4',
    bundle_version: null,
    bundle_commit: null,
    development_source: null,
    operation_id: null,
    definition_token: null,
    state: 'completed',
    preview_error: null,
    observation: null,
    error: null,
    ports: [
      {
        name: 'report',
        type: 'APF_FILE',
        members: [
          {
            name: 'report.txt',
            format: 'other',
            view_base: '/opaque/member-view',
            file_url: '/opaque/download'
          }
        ]
      }
    ]
  }
  f.get.mockResolvedValue(record)
  f.result.mockReturnValue({ apf_result: [record] })
  f.state.mockReturnValue({
    signature: 'fixed',
    submitted: 'fixed',
    phase: 'completed'
  })
  const view = render(BundleResultWidget, {
    props: { widget: fromPartial<ComponentWidget<string | object>>({ node }) },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await screen.findByRole('button', { name: 'astrophotoflow.nodeUi.more' })
  expect(screen.queryByText('report.txt')).not.toBeInTheDocument()
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
  await fireEvent.click(screen.getByRole('button', { name: 'astrophotoflow.nodeUi.more' }))
  expect(screen.getByRole('menuitem', { name: 'astrophotoflow.results.fullFile' })).toHaveAttribute('href', '/opaque/download')
  expect(
    document.querySelector('a[href="/opaque/call-log"]')
  ).not.toBeNull()
  expect(screen.getByRole('menuitem', { name: 'astrophotoflow.results.fullFile' })).toHaveAttribute('title', 'report.txt')
  view.unmount()
})

function checkedCall(
  graph: LGraph,
  node: LGraphNode,
  id: string,
  ports: SoftwareCallResult['ports']
): SoftwareCallResult {
  return {
    prompt_id: id,
    call_id: id,
    log_url: '/log',
    workflow_id: graph.id,
    node_id: String(node.id),
    calculation_signature: null,
    package_id: 'fixture',
    software_version: '1',
    bundle_version: '1',
    bundle_commit: null,
    development_source: null,
    operation_id: 'transform',
    definition_token: 'v1',
    state: 'completed',
    ports,
    preview_error: null,
    observation: null,
    error: null,
    input_token: 'same-input'
  }
}
const rgb = {
  name: 'Result',
  format: 'fits' as const,
  view_base: '/media/primary',
  file_url: '/media/primary/file'
}
const reportPort = {
  name: 'analysis',
  type: 'APF_ANALYSIS',
  members: [
    {
      name: 'Report',
      format: 'other' as const,
      view_base: '/report',
      file_url: '/report/file'
    }
  ]
}
const firstId = '11111111-1111-4111-8111-111111111112'
const secondId = '22222222-2222-4222-8222-222222222223'

it('shows one channel-linked histogram and compares checked runs on the same bins', async () => {
  const graph = new LGraph()
  const node = new LGraphNode('Color')
  graph.add(node)
  const ports = [
    {
      name: 'image',
      type: 'APF_SCIENCE',
      data_kind: 'image' as const,
      members: [rgb]
    },
    reportPort
  ]
  const first = checkedCall(graph, node, firstId, ports)
  const second = checkedCall(graph, node, secondId, ports)
  const stream = ref({ apf_result: [first] })
  f.result.mockImplementation(() => stream.value)
  f.state.mockReturnValue(undefined)
  f.get.mockImplementation(async (value: SoftwareCallResult) => value)
  f.analysis.mockImplementation(
    async (value: SoftwareCallResult): Promise<AnalysisResult[]> =>
      (['composite', 'red'] as const).map((channel) => ({
        kind: 'histogram',
        title: 'Histogram',
        source: 'fixture',
        unit: 'px',
        columns: [],
        rows: [],
        values: {},
        text: null,
        sample: null,
        member_index: 0,
        output: 'image',
        histogram: {
          channel,
          intensity_unit: 'ADU',
          edges: [0, 1, 2],
          counts: [0, value.call_id === firstId ? 2 : 4]
        }
      }))
  )
  const view = render(BundleResultWidget, {
    props: { widget: fromPartial<ComponentWidget<string | object>>({ node }) },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await screen.findByText('Histogram')
  const saved = JSON.stringify(graph.serialize())
  const user = userEvent.setup()
  await user.click(await screen.findByRole('combobox', { name: 'astrophotoflow.bundle.channel' }))
  await user.click(await screen.findByRole('option', { name: 'astrophotoflow.bundle.channels.red' }))
  expect(screen.getByTestId('fixture-media')).toHaveAttribute(
    'data-channel',
    'red'
  )
  expect(screen.getAllByText('Histogram')).toHaveLength(1)
  await fireEvent.click(screen.getByTestId('fixture-media'))
  const request = f.open.mock.lastCall![0] as MediaViewerRequest
  const member = await request.member(0, new AbortController().signal)
  expect(member).toMatchObject({
    basePath: rgb.view_base,
    selection: { channel: 'red' } satisfies Partial<MediaSelection>
  })
  expect(request.fixedDisplay).toBe(true)
  expect(JSON.stringify(graph.serialize())).toBe(saved)
  stream.value = { apf_result: [second] }
  await screen.findByTestId('bundle-histogram-baseline')
  view.unmount()
})

it('follows a quality row to the exact member and switches to another product', async () => {
  const graph = new LGraph()
  const node = new LGraphNode('Sequence')
  graph.add(node)
  const record = checkedCall(graph, node, firstId, [
    {
      name: 'image',
      type: 'APF_SCIENCE',
      data_kind: 'sequence',
      role: 'result',
      members: [rgb, { ...rgb, view_base: '/media/second', frame_count: 4 }]
    },
    {
      name: 'mask',
      type: 'APF_SCIENCE',
      data_kind: 'image',
      role: 'mask',
      members: [{ ...rgb, view_base: '/media/mask' }]
    },
    reportPort
  ])
  f.result.mockReturnValue({ apf_result: [record] })
  f.get.mockResolvedValue(record)
  f.state.mockReturnValue(undefined)
  f.analysis.mockResolvedValue([
    {
      kind: 'table',
      title: 'Frame quality',
      source: 'fixture',
      unit: 'px',
      columns: ['FWHM'],
      rows: [[2.1]],
      values: {},
      text: null,
      sample: null,
      member_index: null,
      output: 'image',
      row_positions: [{ member_index: 1, frame_index: 2 }]
    } satisfies AnalysisResult
  ])
  const view = render(BundleResultWidget, {
    props: { widget: fromPartial<ComponentWidget<string | object>>({ node }) },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await fireEvent.click(await screen.findByRole('button', { name: '3' }))
  expect(screen.getByTestId('fixture-media')).toHaveAttribute(
    'data-base',
    '/media/second'
  )
  expect(screen.getByTestId('fixture-media')).toHaveAttribute('data-frame', '2')
  await fireEvent.update(
    screen.getByLabelText('astrophotoflow.results.output'),
    '1'
  )
  expect(screen.getByTestId('fixture-media')).toHaveAttribute(
    'data-base',
    '/media/mask'
  )
  expect(screen.queryByText('Frame quality')).not.toBeInTheDocument()
  view.unmount()
})

it('writes an edited point into the native parameter bound to the full input', async () => {
  const graph = new LGraph()
  const source = new LGraphNode('Fixed image')
  const node = new LGraphNode('Samples')
  const type = 'APF_00000000000040008000000000000011'
  source.comfyClass = 'APF_DATA_REFERENCE'
  node.comfyClass = type
  source.addOutput('image', 'APF_SCIENCE')
  node.addInput('image', 'APF_SCIENCE')
  source.addWidget(
    'text',
    'reference',
    JSON.stringify({
      kind: 'asset',
      asset_id: firstId,
      selection: { kind: 'whole_file' }
    }),
    () => {}
  )
  const field = node.addWidget('text', 'samples', '', () => {})
  graph.add(source)
  graph.add(node)
  source.connect(0, node, 0)
  const parameter: NodeParameter = {
    name: 'samples',
    kind: 'string',
    default: '',
    editor: { kind: 'points', input: 'image' }
  }
  bundleCapabilities.set(
    type,
    fromPartial<NodeCapability>({
      operation: { parameters: [parameter] },
      node: {
        definition: {
          parameters: [parameter],
          execution: {
            package_id: 'fixture',
            operation_id: 'samples',
            parameters: { samples: { kind: 'parameter', name: 'samples' } },
            inputs: { image: 'image' },
            outputs: {}
          }
        }
      }
    })
  )
  f.graph.mockReturnValue({
    rootGraph: graph,
    canvas: {
      emitBeforeChange: vi.fn(),
      emitAfterChange: vi.fn(),
      setDirty: vi.fn()
    }
  })
  f.result.mockReturnValue(undefined)
  f.state.mockReturnValue(undefined)
  const view = render(BundleResultWidget, {
    props: { widget: fromPartial<ComponentWidget<string | object>>({ node }) },
    global: { plugins: [PlatformQueryPlugin] }
  })
  await fireEvent.click(screen.getByRole('button', { name: 'samples' }))
  await fireEvent.click(
    await screen.findByRole('button', { name: 'Place sample' })
  )
  expect(JSON.parse(String(field.value))).toEqual({
    source_token: 'fixture-input',
    member_index: 0,
    frame_index: 0,
    hdu_index: 0,
    width: 2000,
    height: 1000,
    points: [[120, 60]]
  })
  expect(graph.links.size).toBe(1)
  view.unmount()
})
