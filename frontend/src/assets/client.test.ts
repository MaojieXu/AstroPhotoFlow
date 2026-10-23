import { describe, expect, it, vi } from 'vitest'
import { ApiClientError, createApiClient } from './client'
import { pageSchema, projectSchema } from './contracts'

const project = {
  id: '1f740b2c-75f3-4f76-8f85-f08ade40a33f',
  name: 'M31', target_name: null, notes: null, capture_profile_ids: [],
  status: 'active', revision: 1, created_at: '2026-10-22T20:00:00Z', updated_at: '2026-10-22T20:00:00Z'
}
const response = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

describe('AstroPhotoFlow API client', () => {
  it('accepts a real empty page response', async () => {
    const client = createApiClient(vi.fn().mockResolvedValue(response({ items: [], total: 0, limit: 50, offset: 0 })))
    await expect(client.get('/projects', pageSchema(projectSchema))).resolves.toEqual({ items: [], total: 0, limit: 50, offset: 0 })
  })

  it('keeps revision conflicts distinct', async () => {
    const fetchApi = vi.fn().mockResolvedValue(response({
      error: { code: 'REVISION_CONFLICT', message: '已被修改', fields: [] },
      request_id: 'ce88796a-b7bb-488d-9f15-645d04a87be5'
    }, 409))
    const client = createApiClient(fetchApi)
    await expect(client.get('/resource', projectSchema)).rejects.toMatchObject({
      kind: 'service', status: 409, code: 'REVISION_CONFLICT', requestId: 'ce88796a-b7bb-488d-9f15-645d04a87be5'
    })
  })

  it('does not convert malformed responses to empty data', async () => {
    const client = createApiClient(vi.fn().mockResolvedValue(response({ items: [], total: -1, limit: 50, offset: 0 })))
    await expect(client.get('/projects', pageSchema(projectSchema))).rejects.toBeInstanceOf(ApiClientError)
  })

  it('reports a network failure without fabricating a response', async () => {
    const client = createApiClient(vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(client.get('/projects', pageSchema(projectSchema))).rejects.toMatchObject({ kind: 'network' })
  })
})
