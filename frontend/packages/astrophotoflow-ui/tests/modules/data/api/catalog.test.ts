import { expect, it, vi } from 'vitest'
import { createCatalogClient } from '@ui/modules/data/api/catalog'

it('uses generated status, order and pagination for registered equipment', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      Response.json({ items: [], total: 0, limit: 200, offset: 0 })
    )
  await createCatalogClient(fetch).equipment({
    status: 'all',
    sort_by: 'name',
    order: 'asc',
    limit: 200,
    offset: 0
  })
  const url = new URL(fetch.mock.calls[0][0], window.location.origin)
  expect(url.pathname).toBe('/astrophotoflow/api/v1/equipment')
  expect(url.searchParams.get('status')).toBe('all')
  expect(url.searchParams.get('sort_by')).toBe('name')
  expect(url.searchParams.get('offset')).toBe('0')
})

it('reads references in the exact project scope and rejects an invalid identity before transport', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      Response.json({ items: [], total: 0, limit: 10, offset: 0 })
    )
  const client = createCatalogClient(fetch)
  const project = '00000000-0000-4000-8000-000000000001'
  await client.projectDatasets(project, { limit: 10, offset: 0 })
  expect(new URL(fetch.mock.calls[0][0], window.location.origin).pathname).toBe(
    `/astrophotoflow/api/v1/projects/${project}/datasets`
  )
  await expect(client.projectAssets('invalid', {})).rejects.toMatchObject({
    kind: 'contract'
  })
  expect(fetch).toHaveBeenCalledTimes(1)
})
