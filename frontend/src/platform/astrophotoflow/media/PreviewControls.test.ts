import { render, screen } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import { mediaStateSchema } from '@astrophotoflow/ui'
import { describe, expect, it, vi } from 'vitest'

import PreviewControls from './PreviewControls.vue'

vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({
    t: (key: string, values?: { mode: string }) =>
      values ? `${key} ${values.mode}` : key
  })
}))

describe('preview display controls', () => {
  it('offers all resolutions and distinguishes original size from the default', async () => {
    const view = render(PreviewControls)
    const user = userEvent.setup()
    const resolution = screen.getByRole('combobox', {
      name: 'astrophotoflow.media.previewResolution'
    })
    await user.click(resolution)
    expect(
      screen.getAllByRole('option').map((option) => option.textContent?.trim())
    ).toEqual([
      '512 px',
      '1024 px',
      '2048 px',
      'astrophotoflow.media.originalResolution'
    ])
    await user.click(
      screen.getByRole('option', {
        name: 'astrophotoflow.media.originalResolution'
      })
    )
    expect(view.emitted('update:maxEdge')?.at(-1)).toEqual([null])
    await user.click(
      screen.getByRole('combobox', { name: 'astrophotoflow.media.rgbDisplay' })
    )
    await user.click(
      screen.getByRole('option', { name: 'astrophotoflow.media.preserveRgb' })
    )
    expect(view.emitted('update:balance')?.at(-1)).toEqual(['preserve'])
    expect(view.emitted('change')).toHaveLength(2)
  })

  it.each([
    [[1, 1, 1], 'preserveRgb'],
    [[1.2, 1, 0.8], 'balanceRgb']
  ])(
    'shows the applied RGB display for automatic selection with gains %s',
    (gains, mode) => {
      const media = mediaStateSchema.parse({
        key: 'view',
        status: 'available',
        phase: null,
        selection: {},
        arrays: [],
        hdus: [],
        overview_url: null,
        tile_url: null,
        video_url: null,
        mime_type: null,
        frame_index: null,
        media_time: null,
        frame_count: null,
        duration: null,
        note: null,
        error: null,
        display_recipe: { auto_stretch: { white_balance: gains } }
      })
      render(PreviewControls, { props: { media } })
      expect(screen.getByRole('status').textContent).toContain(
        `astrophotoflow.media.${mode}`
      )
    }
  )
})
