import { fireEvent, render, waitFor } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import WorkbenchSettingsPanel from './WorkbenchSettingsPanel.vue'

it('uses native settings controls and saves the complete workbench configuration', async () => {
  const values = {
    host: '127.0.0.1',
    service_port: 32690,
    data_dir: 'data',
    allowed_origins: ['http://127.0.0.1:32688'],
    import_roots: [{ id: 'night', path: 'D:/Images/原始素材' }],
    file_workers: 2,
    preview_workers: 1
  }
  const configuration = {
    config_path: 'C:/isolated/config.toml',
    data_dir_absolute: 'C:/isolated/data',
    default_workspace: null,
    saved: values,
    effective: values,
    config_token: 'current',
    restart_required: false
  }
  const fetchApi = vi
    .fn()
    .mockImplementation(async () => new Response(JSON.stringify(configuration)))
  vi.stubGlobal('fetch', fetchApi)
  const {
    container,
    unmount,
    getByTestId,
    findByRole,
    queryByRole,
    getByText
  } = render(WorkbenchSettingsPanel, {
    global: { plugins: [i18n] }
  })
  try {
    await waitFor(() =>
      expect(container.querySelector('input[role="spinbutton"]')).not.toBeNull()
    )
    expect(
      container.querySelector('button[data-variant="primary"]')
    ).not.toBeNull()
    const user = userEvent.setup()
    const hint = getByTestId('data-directory-hint')
    expect(queryByRole('tooltip')).toBeNull()
    await user.hover(hint)
    expect(await findByRole('tooltip')).toHaveTextContent(
      configuration.data_dir_absolute
    )
    await user.unhover(hint)
    await waitFor(() => expect(queryByRole('tooltip')).toBeNull())
    hint.focus()
    expect(await findByRole('tooltip')).toHaveTextContent(
      configuration.data_dir_absolute
    )
    hint.blur()
    await waitFor(() => expect(queryByRole('tooltip')).toBeNull())
    expect(fetchApi).toHaveBeenCalledTimes(1)
    expect(queryByRole('textbox', { name: i18n.global.t('apfWorkbench.rootId') })).toBeNull()
    expect(queryByRole('textbox', { name: i18n.global.t('apfWorkbench.rootPath') })).toBeNull()
    expect(queryByRole('button', { name: i18n.global.t('apfWorkbench.addRoot') })).toBeNull()
    const input = container.querySelector('input[role="spinbutton"]')!
    await fireEvent.input(input, { target: { value: '4' } })
    await fireEvent.blur(input)
    await fireEvent.submit(container.querySelector('form')!)
    await waitFor(() => expect(fetchApi).toHaveBeenCalledTimes(2))
    const [path, request] = fetchApi.mock.calls[1]
    expect(path).toBe('/astrophotoflow/api/v1/settings/workbench')
    expect(JSON.parse(request.body)).toEqual({
      config_token: 'current',
      values: { ...values, file_workers: 4 }
    })
    await waitFor(() =>
      expect(getByText(i18n.global.t('apfWorkbench.saved'))).toBeVisible()
    )
    await fireEvent.click(hint)
    expect(getByText(i18n.global.t('apfWorkbench.saved'))).toBeVisible()
    expect(fetchApi).toHaveBeenCalledTimes(2)
  } finally {
    unmount()
    vi.unstubAllGlobals()
  }
})
