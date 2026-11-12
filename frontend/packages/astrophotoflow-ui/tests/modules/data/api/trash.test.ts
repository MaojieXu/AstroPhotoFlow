import { expect, it, vi } from 'vitest'
import { createTrashClient } from '@ui/modules/data/api/trash'

const item = {
  entry_type: 'equipment' as const,
  id: '00000000-0000-4000-8000-000000000001',
  revision: 4
}

it('reads deletion impact without implicitly deleting and submits the same confirmed fingerprint', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      Response.json({
        items: [],
        dependencies: [],
        blocked: false,
        preview_fingerprint: 'observed-content'
      })
    )
    .mockResolvedValueOnce(
      Response.json({ deleted_count: 1, detached_material_count: 0 })
    )
  const client = createTrashClient(fetch)
  const preview = await client.equipmentPreview({ items: [item] })
  expect(fetch).toHaveBeenCalledTimes(1)
  await client.equipmentRemove({
    items: [item],
    preview_fingerprint: preview.preview_fingerprint
  })
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
    items: [item],
    preview_fingerprint: 'observed-content'
  })
})

it('does not replay a permanent deletion when its reply is lost', async () => {
  const fetch = vi.fn().mockRejectedValue(new TypeError('reply lost'))
  await expect(
    createTrashClient(fetch).equipmentRemove({
      items: [item],
      preview_fingerprint: 'observed-content'
    })
  ).rejects.toMatchObject({ kind: 'network' })
  expect(fetch).toHaveBeenCalledTimes(1)
})
