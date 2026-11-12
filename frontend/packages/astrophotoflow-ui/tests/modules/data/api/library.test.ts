import { expect, it, vi } from 'vitest'
import {
  createLibraryClient,
  parseLibraryQuery
} from '@ui/modules/data/library/client'

it('serializes repeated filters and numeric zero through the generated query contract', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      Response.json({ items: [], total: 0, limit: 10, offset: 20 })
    )
  const client = createLibraryClient(fetch)
  await client.search(
    parseLibraryQuery({
      frame_type: ['light', 'dark'],
      gain_min: '0',
      exposure_max: '30',
      limit: 10,
      offset: 20,
      q: 'M 31',
      sort_by: 'name',
      order: 'asc'
    })
  )
  const url = new URL(fetch.mock.calls[0][0], window.location.origin)
  expect(url.pathname).toBe('/astrophotoflow/api/v1/library/items')
  expect(url.searchParams.getAll('frame_type')).toEqual(['light', 'dark'])
  expect(url.searchParams.get('gain_min')).toBe('0')
  expect(url.searchParams.get('offset')).toBe('20')
  expect(url.searchParams.get('q')).toBe('M 31')
})

it('rejects invalid dataset identities before transport', async () => {
  const fetch = vi.fn()
  await expect(
    createLibraryClient(fetch).members('invalid', {
      limit: 1,
      offset: 0
    })
  ).rejects.toMatchObject({ kind: 'contract' })
  expect(fetch).not.toHaveBeenCalled()
})
