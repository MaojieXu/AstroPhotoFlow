import { fromPartial } from '@total-typescript/shoehorn'
import { nextTick } from 'vue'
import { render, screen } from '@testing-library/vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { mediaStateSchema } from '@astrophotoflow/ui'
import type { ComponentWidget } from '@/scripts/domWidget'
import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import DataRunWidget from './DataRunWidget.vue'

const state = vi.hoisted(() => ({ output: undefined as unknown, graph: undefined as unknown, handlers: new Map<string, (event: unknown) => void>(), prepare: vi.fn() }))
vi.mock('@/stores/nodeOutputStore', () => ({ useNodeOutputStore: () => ({ getNodeOutputs: () => state.output }) }))
vi.mock('@/scripts/appInstance', () => ({ useApp: () => ({ rootGraph: state.graph, graph: state.graph }) }))
vi.mock('@/scripts/api', () => ({ api: { addEventListener: (name: string, fn: (event: unknown) => void) => state.handlers.set(name, fn), removeEventListener: (name: string) => state.handlers.delete(name) } }))
vi.mock('vue-i18n', async original => ({ ...await original<typeof import('vue-i18n')>(), useI18n: () => ({ t: (key: string) => key }) }))
vi.mock(import('@astrophotoflow/ui'), async original => ({ ...await original(), createMediaClient: () => ({ prepare: state.prepare, status: state.prepare }) }))
vi.mock('./MediaViewer.vue', () => ({ default: { template: '<div />' } }))
vi.mock('./DataExportDialog.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/renderer/extensions/vueNodes/components/ImagePreview.vue', () => ({ default: { template: '<img alt="complete result" />' } }))

const id = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
function setup() {
  const graph = new LGraph()
  graph.id = id(1)
  state.graph = graph
  const node = new LGraphNode('Data')
  node.comfyClass = 'APF_DATA_REFERENCE'
  node.addWidget('text', 'reference', '', () => {})
  graph.add(node)
  const result = { run_id: id(2), execution_id: id(3), node_id: String(node.id), workflow_id: graph.id,
    state: 'completed', error: null, reference: { kind: 'run_output' }, input_bindings: { images: ['10', 0] },
    members: [{ name: 'Full FITS', view_base: '/result', selection: { hdu_index: 0 }, format: 'fits', metadata: {}, byte_size: 4096 }] }
  state.output = { apf_data: [result] }
  return { graph, node, result, widget: fromPartial<ComponentWidget<string | object>>({ node, name: 'display', value: '', options: {} }) }
}
beforeEach(() => {
  vi.clearAllMocks()
  state.handlers.clear()
  state.prepare.mockResolvedValue(mediaStateSchema.parse({ key: 'view', status: 'available', kind: 'image', width: 5, height: 4,
    max_level: 3, tile_size: 512, selection: {}, arrays: [], needs_selection: false, overview_url: null, tile_url: null,
    video_url: null, mime_type: null, proxy: false, frame_index: null, media_time: null, frame_count: null, duration: null, note: null, error: null }))
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })))
})
afterEach(() => { vi.unstubAllGlobals() })

it('uses the matching actual native result without writing the serialized reference', async () => {
  const { widget, node } = setup()
  const original = node.serialize().widgets_values
  render(DataRunWidget, { props: { widget, reference: '', bindings: { images: ['10', 0] } } })
  await nextTick()
  expect(screen.getByText('Full FITS')).toBeVisible()
  expect(screen.getByRole('button', { name: 'astrophotoflow.dataExport.saveLibrary' })).toBeVisible()
  expect(node.serialize().widgets_values).toEqual(original)
})

it('rejects a result for another connection instead of using the old local reference', async () => {
  const { widget } = setup()
  render(DataRunWidget, { props: { widget, reference: 'old local reference', bindings: { images: ['11', 0] } } })
  await nextTick()
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'astrophotoflow.dataExport.saveLibrary' })).not.toBeInTheDocument()
  expect(state.prepare).not.toHaveBeenCalled()
})

it('does not display an old result as the result of a newly failed execution', async () => {
  const { widget } = setup()
  render(DataRunWidget, { props: { widget, reference: '', bindings: { images: ['10', 0] } } })
  state.handlers.get('execution_start')?.({ detail: { prompt_id: id(9) } })
  state.handlers.get('execution_error')?.({ detail: { prompt_id: id(9), exception_message: 'Upstream failed' } })
  await nextTick()
  expect(screen.getByText('Upstream failed')).toBeVisible()
  expect(screen.queryByText('Full FITS')).not.toBeInTheDocument()
})
