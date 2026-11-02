import { expect, it, vi } from 'vitest'

import { createDataExportClient } from '@ui/modules/data/api/exports'
import type { ExportRequest } from '@ui/modules/data/api/exports'

const identity = '00000000-0000-4000-8000-000000000001'
const body: ExportRequest = {
  request_id: identity,
  source: { run_id: identity, execution_id: identity },
  member_indexes: [0],
  target: 'library'
}

it('does not replay an uncertain export and queries its original identity', async () => {
  const receipt = {
    ...body,
    state: 'queued',
    destination: null,
    settings: {},
    results: [],
    error: null
  }
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new TypeError('reply lost'))
    .mockResolvedValueOnce(Response.json(receipt))
  const client = createDataExportClient(fetch)
  await expect(client.submit(body)).rejects.toMatchObject({ kind: 'network' })
  expect(fetch).toHaveBeenCalledTimes(1)
  await expect(client.status(identity)).resolves.toMatchObject({
    request_id: identity,
    state: 'queued'
  })
  expect(fetch.mock.calls.map(([path]) => path)).toEqual([
    '/astrophotoflow/api/v1/exports',
    `/astrophotoflow/api/v1/exports/${identity}`
  ])
  expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'GET' })
})

it('preserves cancellation from the destination picker without submitting an export', async () => {
  const fetch = vi.fn().mockResolvedValue(Response.json({ path: null }))
  const client = createDataExportClient(fetch)
  await expect(
    client.choose({ mode: 'file', suggested_name: 'result.fits' })
  ).resolves.toEqual({ path: null })
  expect(fetch).toHaveBeenCalledTimes(1)
})
