import { expect, it, vi } from 'vitest'
import { createCanvasDataClient } from '@ui/modules/data/api/canvas'

const id = (value: number) => `00000000-0000-4000-8000-${String(value).padStart(12, '0')}`
const timestamp = '2026-10-30T00:00:00Z'
const task = {
  id: id(1), status: 'running', sources: [], storage_mode: 'managed',
  classification: {}, parameters: {}, notes: null, dataset_name: null, target_dataset_id: null,
  dataset_base_revision: null, dataset_id: null, enumeration_completed: true, retry_of_task_id: null,
  report: {}, error: null, created_at: timestamp, updated_at: timestamp,
  items_total: 1, items_completed: 0, items_limit: 20, items_offset: 0,
  items: [{ id: id(2), task_id: id(1), root_item_id: id(2), retry_of_item_id: null,
    root_id: '', source_path: 'C:/Images/source.fit', position: 0, status: 'running',
    content_status: 'available', metadata_status: 'pending', preview_status: 'pending',
    asset_id: id(3), asset_version_id: id(4), error: null, created_at: timestamp, updated_at: timestamp }]
}

it('binds the imported fixed version before preview generation finishes', async () => {
  const prepared = { native_type: 'APF_DATA_REFERENCE', title: 'source.fit', reference: {
    kind: 'asset_version', asset_version_id: id(4), selection: { kind: 'whole_file' }
  } }
  const fetch = vi.fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockResolvedValueOnce(Response.json(task))
    .mockResolvedValueOnce(Response.json(prepared))
  expect(await createCanvasDataClient(fetch).importPath('C:/Images/source.fit')).toEqual(prepared)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ sources: [{ path: 'C:/Images/source.fit' }], storage_mode: 'managed' })
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ entry_type: 'asset', id: id(3), version_id: id(4) })
})

it('reports an import failure without submitting another import', async () => {
  const fetch = vi.fn()
    .mockResolvedValueOnce(Response.json({ task_id: id(1), status: 'queued' }))
    .mockResolvedValueOnce(Response.json({ ...task, status: 'failed', items: [], error: { message: 'Source unavailable' } }))
  await expect(createCanvasDataClient(fetch).importPath('C:/Images/missing.fit')).rejects.toThrow('Source unavailable')
  expect(fetch).toHaveBeenCalledTimes(2)
})
