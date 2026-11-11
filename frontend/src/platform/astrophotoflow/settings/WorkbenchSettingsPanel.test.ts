import { render, screen, waitFor, within } from '@testing-library/vue'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { i18n } from '@/i18n'
import WorkbenchSettingsPanel from './WorkbenchSettingsPanel.vue'
import { PlatformQueryPlugin } from '@astrophotoflow/ui'

it('shows directory fields immediately and saves workbench configuration', async () => {
  const values = {
    host: '127.0.0.1', service_port: 32690, data_dir: 'data',
    allowed_origins: ['http://127.0.0.1:32688'],
    import_roots: [{ id: 'night', path: 'D:/Images/原始素材' }],
    file_workers: 2, preview_workers: 1
  }
  const configuration = {
    config_path: 'C:/isolated/config.toml', data_dir_absolute: 'C:/isolated/data',
    default_workspace: null, saved: values, effective: values,
    config_token: 'current', restart_required: false
  }
  vi.mocked(fetch).mockImplementation(async () => new Response(JSON.stringify(configuration)))
  render(WorkbenchSettingsPanel, { global: { plugins: [i18n, PlatformQueryPlugin] } })
  const user = userEvent.setup()
  const input = await screen.findByRole('spinbutton', { name: i18n.global.t('apfWorkbench.fileWorkers') })
  const workspace = screen.getByRole('region', {
    name: i18n.global.t('apfWorkbench.advanced')
  })
  expect(
    within(workspace).getByRole('textbox', {
      name: i18n.global.t('apfWorkbench.defaultWorkspace')
    })
  ).toBeVisible()
  expect(
    within(workspace).getByRole('textbox', {
      name: i18n.global.t('apfWorkbench.dataDir')
    })
  ).toBeVisible()
  const hint = screen.getByTestId('data-directory-hint')
  await user.hover(hint)
  expect(await screen.findByRole('tooltip')).toHaveTextContent(configuration.data_dir_absolute)
  await user.unhover(hint)
  await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
  hint.focus()
  expect(await screen.findByRole('tooltip')).toHaveTextContent(configuration.data_dir_absolute)
  hint.blur()
  await waitFor(() => expect(screen.queryByRole('tooltip')).toBeNull())
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('textbox', { name: i18n.global.t('apfWorkbench.rootId') })).toBeNull()
  expect(screen.queryByRole('textbox', { name: i18n.global.t('apfWorkbench.rootPath') })).toBeNull()
  await user.clear(input)
  await user.type(input, '4')
  await user.tab()
  await user.click(screen.getByRole('button', { name: i18n.global.t('apfWorkbench.save') }))
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
  expect(vi.mocked(fetch).mock.calls[1][0]).toBe('/astrophotoflow/api/v1/settings/workbench')
  expect(JSON.parse(String(vi.mocked(fetch).mock.calls[1][1]?.body))).toEqual({
    config_token: 'current', values: { ...values, file_workers: 4 }
  })
  expect(await screen.findByText(i18n.global.t('apfWorkbench.saved'))).toBeVisible()
  await user.click(hint)
  expect(screen.getByText(i18n.global.t('apfWorkbench.saved'))).toBeVisible()
  expect(fetch).toHaveBeenCalledTimes(2)
})
