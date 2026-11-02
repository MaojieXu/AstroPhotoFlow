import userEvent from '@testing-library/user-event'
import { render, screen, waitFor } from '@testing-library/vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, PlatformQueryPlugin } from '@astrophotoflow/ui'
import type { DataResult } from '@astrophotoflow/ui'
import DataExportDialog from './DataExportDialog.vue'
vi.mock('../useNativeWorkspace')

const client = vi.hoisted(() => ({
  result: vi.fn(),
  submit: vi.fn(),
  choose: vi.fn(),
  status: vi.fn(),
  cancel: vi.fn()
}))
vi.mock(import('@astrophotoflow/ui'), async (original) => ({
  ...(await original()),
  createDataExportClient: () => client
}))
vi.mock('vue-i18n', async (original) => ({
  ...(await original<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key })
}))
const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const source: DataResult = {output:{kind:'run_output',run_id:id(1),execution_id:id(2),output_index:0},
  run_id: id(1),
  execution_id: id(2),
  node_id: '7',
  workflow_id: id(3),
  state: 'completed',
  error: null,
  reference: null,
  input_bindings: {},
  members: [0, 1].map((index) => ({
    name: `frame-${index}.fits`,
    view_base: '/view',
    selection: { hdu_index: 0 },
    format: 'fits',
    metadata: {},
    byte_size: 4096
  }))
}
const key = (name: string) => 'astrophotoflow.dataExport.' + name
function show(target: 'library' | 'local' = 'local') {
  const wrapper = { template: '<div><slot /></div>' }
  return render(DataExportDialog, {
    props: { result: source, index: 1, target },
    global: {
      plugins: [PlatformQueryPlugin],
      stubs: {
        Dialog: wrapper,
        DialogPortal: wrapper,
        DialogOverlay: true,
        DialogContent: wrapper,
        DialogHeader: wrapper,
        DialogTitle: wrapper
      }
    }
  })
}
beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  client.result.mockResolvedValue(source)
  client.status.mockRejectedValue(
    new ApiClientError('No receipt', 'service', 404, 'RESOURCE_NOT_FOUND')
  )
  client.choose.mockResolvedValue({ path: null })
  client.submit.mockImplementation(async (body) => ({
    request_id: body.request_id,
    state: 'completed',
    source: body.source,
    target: body.target,
    destination: body.destination ?? null,
    member_indexes: body.member_indexes,
    settings: body.settings,
    results: [],
    error: null
  }))
})
afterEach(() => {
  sessionStorage.clear()
})

it('offers only precision combinations supported by the chosen format', async () => {
  show()
  const user = userEvent.setup()
  await user.selectOptions(
    screen.getByRole('combobox', { name: key('format') }),
    'jpeg'
  )
  const precision = screen.getByRole('combobox', {
    name: key('precision')
  }) as HTMLSelectElement
  expect([...precision.options].map((option) => option.value)).toEqual([
    'uint8'
  ])
  await user.selectOptions(
    screen.getByRole('combobox', { name: key('format') }),
    'png'
  )
  expect([...precision.options].map((option) => option.value)).toEqual([
    'uint8',
    'uint16'
  ])
})

it('does not submit any writes when the native destination chooser is cancelled', async () => {
  show()
  await userEvent
    .setup()
    .click(screen.getByRole('button', { name: key('start') }))
  await waitFor(() => expect(client.choose).toHaveBeenCalled())
  expect(client.submit).not.toHaveBeenCalled()
})

it('submits one explicit ordered group request and leaves graph processing to the native queue', async () => {
  client.choose.mockResolvedValue({ path: 'C:/Exports' })
  show()
  const user = userEvent.setup()
  await user.selectOptions(
    screen.getByRole('combobox', { name: key('scope') }),
    'all'
  )
  await user.selectOptions(
    screen.getByRole('combobox', { name: key('format') }),
    'png'
  )
  await user.click(screen.getByRole('button', { name: key('start') }))
  await waitFor(() => expect(client.submit).toHaveBeenCalledTimes(1))
  expect(client.choose).toHaveBeenCalledWith(
    expect.objectContaining({ mode: 'folder' }),
    expect.any(AbortSignal)
  )
  expect(client.submit.mock.calls[0]![0]).toEqual(
    expect.objectContaining({
      member_indexes: [0, 1],
      target: 'local',
      settings: expect.objectContaining({
        format: 'png',
        precision: 'uint16',
        conversion: 'preserve'
      }),
      source: { run_id: source.run_id, execution_id: source.execution_id }
    })
  )
})

it('recovers unknown acceptance using the identical request ID and frozen payload', async () => {
  client.submit.mockRejectedValueOnce(new Error('Unknown network result'))
  show('library')
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: key('start') }))
  await screen.findByRole('alert')
  await user.click(screen.getByRole('button', { name: key('recover') }))
  await waitFor(() => expect(client.submit).toHaveBeenCalledTimes(2))
  expect(client.status).toHaveBeenCalledWith(
    client.submit.mock.calls[0][0].request_id,
    expect.any(AbortSignal)
  )
  expect(client.submit.mock.calls[0]![0]).toEqual(
    client.submit.mock.calls[1]![0]
  )
  expect(client.choose).not.toHaveBeenCalled()
})
