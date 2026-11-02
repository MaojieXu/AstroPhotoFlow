import { fromPartial } from '@total-typescript/shoehorn'
import { expect, it, vi } from 'vitest'

import { LGraph, LGraphNode } from '@/lib/litegraph/src/litegraph'
import { useExtensionStore } from '@/stores/extensionStore'
import type { ComfyApp } from '@/types/comfy'

import { registerBundleResultDisplay } from './bundleDisplay'

it('refreshes an existing display extension after its module is replaced', async () => {
  const previous = vi.fn()
  const extensions = useExtensionStore()
  extensions.registerExtension({ name: 'AstroPhotoFlow.BundleResults', nodeCreated: previous })
  const app = fromPartial<ComfyApp>({
    rootGraph: new LGraph(),
    isGraphReady: false,
    registerExtension: () => { throw new Error('Extension already registered') }
  })
  registerBundleResultDisplay(app)
  const active = extensions.extensions.find(value => value.name === 'AstroPhotoFlow.BundleResults')
  const node = new LGraphNode('Bundle result')
  node.comfyClass = 'APF_169de0837f814cdea3295541ecacf463'
  await active?.nodeCreated?.(node, app)
  expect(node.widgets?.filter(widget => widget.name === 'apf_result_view')).toHaveLength(1)
  expect(node.hideOutputImages).toBe(true)
  expect(previous).not.toHaveBeenCalled()
})
