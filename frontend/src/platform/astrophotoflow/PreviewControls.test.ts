import { fireEvent, render, screen } from '@testing-library/vue'
import { describe, expect, it, vi } from 'vitest'

import PreviewControls from './PreviewControls.vue'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))

describe('preview display controls', () => {
  it('offers all resolutions and distinguishes original size from the default', async () => {
    const view = render(PreviewControls)
    const resolution = screen.getByRole('combobox', { name: 'astrophotoflow.media.previewResolution' })
    expect(screen.getAllByRole('option').slice(0, 4).map(option => option.textContent)).toEqual(['512 px', '1024 px', '2048 px', 'astrophotoflow.media.originalResolution'])
    ;(resolution as HTMLSelectElement).selectedIndex = 3
    await fireEvent.change(resolution)
    expect(view.emitted('update:maxEdge')?.at(-1)).toEqual([null])
    await fireEvent.update(screen.getByRole('combobox', { name: 'astrophotoflow.media.rgbDisplay' }), 'preserve')
    expect(view.emitted('update:balance')?.at(-1)).toEqual(['preserve'])
  })
})
