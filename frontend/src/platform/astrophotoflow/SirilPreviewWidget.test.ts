import { bundleCapabilities } from './bundleCatalog'
import type { NodeCapability } from '@astrophotoflow/ui'
import { fromPartial } from '@total-typescript/shoehorn'
import { fireEvent, render, screen } from '@testing-library/vue'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest'

import type { ComponentWidget } from '@/scripts/domWidget'
import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import { api } from '@/scripts/api'
import SirilPreviewWidget from './SirilPreviewWidget.vue'

const service = vi.hoisted(() => ({ render: vi.fn(), release: vi.fn().mockResolvedValue(undefined) }))
vi.mock('@astrophotoflow/ui', async importOriginal => ({
  ...await importOriginal<typeof import('@astrophotoflow/ui')>(),
  createBundlePreviewClient: () => service
}))
vi.mock('vue-i18n', async original => ({ ...await original<typeof import('vue-i18n')>(), useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/stores/workspace/sidebarTabStore', () => ({ useSidebarTabStore: () => ({ activeSidebarTabId: 'library' }) }))
vi.mock('@/renderer/extensions/vueNodes/components/ImagePreview.vue', () => ({
  default: { props: ['imageUrls'], template: '<div data-testid="preview">{{ imageUrls[0] }}</div>' }
}))

function setup(expand = true) {
  const graph = new LGraph()
  const source = new LGraphNode('Data')
  source.comfyClass = 'APF_DATA_REFERENCE'
  source.addWidget('text', 'reference', JSON.stringify({ kind: 'asset_version', asset_version_id: '00000000-0000-4000-8000-000000000001', selection: { kind: 'whole_file' } }), () => {})
  source.addOutput('science', 'APF_SCIENCE')
  bundleCapabilities.set('APF_169de0837f814cdea3295541ecacf463', fromPartial<NodeCapability>({
      available: true,
      node: { native_type: 'APF_169de0837f814cdea3295541ecacf463', definition: { parameters: [
        { name: 'linked', default: false }, { name: 'shadowsclip', default: -2.8 }, { name: 'targetbg', default: 0.25 }
      ] } }, operation: { package_id: 'siril', operation_id: 'autostretch' }, preview: { kind: 'science-image', input: 'image', max_edge: 1024 }
    }))
    const node = new LGraphNode('Siril Auto Stretch')
    node.comfyClass = 'APF_169de0837f814cdea3295541ecacf463'
  node.addInput('image', 'APF_SCIENCE')
  const values = [node.addWidget('toggle', 'linked', true, () => {}), node.addWidget('number', 'shadowsclip', 0, () => {}), node.addWidget('number', 'targetbg', 0, () => {})]
  graph.add(source)
  graph.add(node)
  source.connect(0, node, 0)
  const widget = fromPartial<ComponentWidget<string | object>>({ node })
  const wrapper = render(SirilPreviewWidget, { props: { widget }, global: { mocks: { $t: (key: string) => key } } })
  if (expand) wrapper.container.querySelector('button')?.click()
  return { wrapper, values }
}

describe('Siril live preview', () => {
  it('does not calculate the optional sample preview until expanded', async () => {
    vi.useFakeTimers()
    const { wrapper } = setup(false)
    onTestFinished(() => { wrapper.unmount(); vi.useRealTimers() })
    await vi.advanceTimersByTimeAsync(1000)
    expect(service.render).not.toHaveBeenCalled()
  })
  it('regenerates the preview when resolution or RGB display changes', async () => {
    vi.useFakeTimers()
    service.render.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:current')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const { wrapper } = setup()
    onTestFinished(() => { wrapper.unmount(); vi.useRealTimers() })
    await vi.advanceTimersByTimeAsync(350)
    await fireEvent.update(screen.getByRole('combobox', { name: 'astrophotoflow.media.previewResolution' }), '2048')
    await vi.advanceTimersByTimeAsync(350)
    expect(service.render).toHaveBeenLastCalledWith(expect.objectContaining({ preview_max_edge: 2048 }), expect.any(AbortSignal))
    await fireEvent.update(screen.getByRole('combobox', { name: 'astrophotoflow.media.rgbDisplay' }), 'preserve')
    await vi.advanceTimersByTimeAsync(350)
    expect(service.render).toHaveBeenLastCalledWith(expect.objectContaining({ display_balance: 'preserve' }), expect.any(AbortSignal))
  })
  beforeEach(() => { service.release.mockResolvedValue(undefined) })
  it('refreshes a preview when only the development source fingerprint changes', async () => {
    vi.useFakeTimers()
    service.render.mockResolvedValue(new Blob(['png']))
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:development')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const { wrapper } = setup()
    onTestFinished(() => { wrapper.unmount(); vi.useRealTimers() })
    const type = 'APF_169de0837f814cdea3295541ecacf463'
    const capability = bundleCapabilities.get(type)!
    const development = { root: 'C:/feature/Siril', head: 'a'.repeat(40), dirty: true, fingerprint: 'before',
      state: 'ready' as const, error: null, software_version: '1.4.4', bundle_version: '0.2.0-dev.2' }
    bundleCapabilities.set(type, { ...capability, development_source: development })
    await nextTick()
    await vi.advanceTimersByTimeAsync(350)
    expect(service.render).toHaveBeenCalledTimes(1)
    bundleCapabilities.set(type, { ...capability, development_source: { ...development, fingerprint: 'after' } })
    await nextTick()
    await vi.advanceTimersByTimeAsync(350)
    expect(service.render).toHaveBeenCalledTimes(2)
    expect(service.render.mock.calls[1][0].parameters).toEqual(service.render.mock.calls[0][0].parameters)
  })
  it('debounces parameter edits, preserves zero, and releases requests on unmount', async () => {
    vi.useFakeTimers()
    service.render.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:current')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const { wrapper, values } = setup()
    values[2].value = 0.2
    api.dispatchCustomEvent('graphChanged', null)
    await nextTick()
    values[2].value = 0.3
    api.dispatchCustomEvent('graphChanged', null)
    await nextTick()
    expect(service.render).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(350)
    expect(service.render).toHaveBeenCalledTimes(1)
    expect(service.render.mock.calls[0][0]).toMatchObject({ parameters: { linked: true, shadowsclip: 0, targetbg: 0.3 }, member_index: 0 })
    expect(screen.getByTestId('preview').textContent).toContain('blob:current')
    const signal = service.render.mock.calls[0][1] as AbortSignal
    wrapper.unmount()
    expect(signal.aborted).toBe(true)
    expect(service.release).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('does not replace the current image with a late old result', async () => {
    vi.useFakeTimers()
    let old: ((blob: Blob) => void) | undefined
    service.render.mockImplementationOnce(() => new Promise<Blob>(resolve => { old = resolve }))
      .mockResolvedValueOnce(new Blob(['latest']))
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:latest')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const { wrapper, values } = setup()
    await vi.advanceTimersByTimeAsync(350)
    values[2].value = 0.4
    api.dispatchCustomEvent('graphChanged', null)
    await nextTick()
    await vi.advanceTimersByTimeAsync(350)
    old?.(new Blob(['old']))
    await vi.advanceTimersByTimeAsync(0)
    expect(create).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('preview').textContent).toContain('blob:latest')
    wrapper.unmount()
    vi.useRealTimers()
  })

  it('shows a removed bundle and resumes after it becomes available again', async () => {
    vi.useFakeTimers()
    service.render.mockResolvedValue(new Blob(['png']))
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:reinstalled')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const { wrapper } = setup()
    const type = 'APF_169de0837f814cdea3295541ecacf463'
    const capability = bundleCapabilities.get(type)!
    bundleCapabilities.set(type, { ...capability, available: false, reason: 'Bundle removed' })
    await nextTick()
    expect(screen.getByRole('alert').textContent).toContain('Bundle removed')
    expect(service.render).not.toHaveBeenCalled()
    bundleCapabilities.set(type, { ...capability, available: true })
    await nextTick()
    await vi.advanceTimersByTimeAsync(350)
    expect(screen.getByTestId('preview').textContent).toContain('blob:reinstalled')
    wrapper.unmount()
    vi.useRealTimers()
  })
})
